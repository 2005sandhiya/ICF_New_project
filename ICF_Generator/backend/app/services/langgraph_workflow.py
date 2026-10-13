import logging
from typing import TypedDict, Optional, List, Dict, Any, cast
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.models.icf import ICFGenerationRequest, ICFDraft, ICFGenerationResponse
from app.models.protocol_facts import ProtocolFacts
from app.models.validation import ICFValidationRequest, ICFValidationReport, ValidationCheckResult
from app.services.study_loader import study_loader_service
from app.services.protocol_ingestion_service import protocol_ingestion_service
from app.services.vector_store import vector_store_service
from app.services.protocol_analysis_agent import protocol_analysis_agent
from app.services.icf_generation_service import icf_generation_service
from app.services.validation_agent import validation_agent
from app.services.human_review_service import human_review_service
from app.services.template_service import MAX_TEMPLATE_BYTES, template_service
from app.services.docx_generation_service import docx_generation_service
from app.services.workflow_lock import study_lock

logger = logging.getLogger("icf_generator.langgraph_workflow")

DEFAULT_MAX_REVISIONS = 3


class ICFWorkflowState(TypedDict, total=False):
    job_id: str
    study_id: str
    filename: Optional[str]
    protocol_content: Optional[bytes]
    template_filename: Optional[str]
    template_content: Optional[bytes]
    preferred_length: Optional[str]
    custom_instructions: Optional[str]

    canonical_protocol: Optional[Dict[str, Any]]
    facts: Optional[Dict[str, Any]]
    icf_draft: Optional[Dict[str, Any]]
    patient_friendly_icf: Optional[Dict[str, Any]]
    template: Optional[Dict[str, Any]]
    validation_report: Optional[Dict[str, Any]]

    review_status: str       # "PENDING", "APPROVED", "CHANGES_REQUESTED"
    reviewer_feedback: Optional[str]
    revision: int            # Current revision number (starts at 1)
    max_revisions: int       # Bounded revision limit (default: 3)

    workflow_status: str     # "queued", "ingesting", "analyzing", "generating", "validating", "awaiting_review", "approved", "completed", "failed"
    error: Optional[str]
    step_progress: List[Dict[str, Any]]


def node_ingest_protocol(state: ICFWorkflowState) -> ICFWorkflowState:
    logger.info(f"[LangGraph Node] Ingesting protocol for study '{state.get('study_id')}'...")
    study_id = state.get("study_id")
    content = state.get("protocol_content")
    filename = state.get("filename")

    canonical = None
    stage_noop = lambda _n, _s, _m: None
    if content is not None:
        canonical = protocol_ingestion_service.canonicalize_upload(filename or "uploaded_protocol", content, on_stage=stage_noop)
        if not study_id:
            study_id = canonical.protocol.study_id
        if not study_id:
            raise ValueError("Could not determine study ID from protocol content.")
        canonical, _ = protocol_ingestion_service.index_canonical(canonical, on_stage=stage_noop)
    else:
        if not study_id:
            raise ValueError("Study ID is required when no protocol content is provided.")
        if not study_loader_service.get_study_detail(study_id):
            raise ValueError("The selected study is no longer available.")
        canonical = study_loader_service.get_study_as_canonical_protocol(study_id)
        if study_id not in vector_store_service.get_studies_indexed():
            chunks = study_loader_service.get_study_chunks(study_id)
            if not chunks or not chunks.total_chunks:
                raise ValueError("No readable protocol evidence was found for this study.")
            from app.services.embedding_service import embedding_service
            embedded = embedding_service.embed_chunking_response(chunks)
            vector_store_service.add_embeddings(embedded)

    template_content = state.get("template_content")
    if template_content is not None:
        if len(template_content) > MAX_TEMPLATE_BYTES:
            raise ValueError("DOCX templates must be no larger than 10 MB.")
        template_service.upload(study_id, state.get("template_filename") or "custom.docx", template_content)

    return {
        **state,
        "study_id": study_id,
        "canonical_protocol": canonical.model_dump(mode="json") if canonical else None,
        "workflow_status": "ingested",
    }


def node_analyze_protocol(state: ICFWorkflowState) -> ICFWorkflowState:
    study_id = state.get("study_id")
    if not study_id:
        raise ValueError("Study ID is required for protocol analysis.")
    logger.info(f"[LangGraph Node] Analyzing protocol facts for study '{study_id}'...")
    facts = protocol_analysis_agent.assemble_comprehensive_facts(study_id)
    if hasattr(facts, "study_id") and facts.study_id != study_id:
        facts.study_id = study_id

    facts_dump = facts.model_dump(mode="json") if hasattr(facts, "model_dump") else (facts if isinstance(facts, dict) else {})

    return {
        **state,
        "facts": facts_dump,
        "workflow_status": "analyzed",
    }


def node_generate_icf(state: ICFWorkflowState) -> ICFWorkflowState:
    study_id = state.get("study_id")
    if not study_id:
        raise ValueError("Study ID is required for ICF generation.")
    revision = state.get("revision", 1)
    logger.info(f"[LangGraph Node] Generating dual ICF drafts for study '{study_id}' (revision {revision})...")
    
    facts_dict = state.get("facts")
    facts = ProtocolFacts.model_validate(facts_dict) if facts_dict else None

    req = ICFGenerationRequest(
        study_id=study_id,
        analysis_facts=facts,
        generate_patient_friendly=True,
        reviewer_feedback=state.get("reviewer_feedback"),
        preferred_length=state.get("preferred_length"),
        custom_instructions=state.get("custom_instructions"),
        revision=revision,
    )
    generated: ICFGenerationResponse = icf_generation_service.generate_icf(req)

    draft_obj = getattr(generated, "icf_draft", None) if generated else None
    if not generated or not draft_obj:
        raise ValueError("ICF generation failed: invalid response object or missing icf_draft.")

    patient_obj = getattr(generated, "patient_friendly_icf", None) or draft_obj
    rev_val = getattr(generated, "revision", revision)
    template_obj = getattr(generated, "template", None)
    template_dict = (
        template_obj.model_dump(mode="json")
        if (template_obj is not None and hasattr(template_obj, "model_dump"))
        else (template_obj if isinstance(template_obj, dict) else None)
    )

    return {
        **state,
        "template": template_dict,
        "icf_draft": draft_obj.model_dump(mode="json") if hasattr(draft_obj, "model_dump") else (draft_obj if isinstance(draft_obj, dict) else None),
        "patient_friendly_icf": patient_obj.model_dump(mode="json") if hasattr(patient_obj, "model_dump") else (patient_obj if isinstance(patient_obj, dict) else None),
        "revision": rev_val,
        "workflow_status": "generated",
    }


def node_validate_icf(state: ICFWorkflowState) -> ICFWorkflowState:
    study_id = state.get("study_id")
    if not study_id:
        raise ValueError("Study ID is required for ICF validation.")
    logger.info(f"[LangGraph Node] Auditing ICF validation for study '{study_id}'...")
    
    raw_draft = state.get("icf_draft")
    icf_draft = ICFDraft.model_validate(raw_draft) if isinstance(raw_draft, dict) else (raw_draft if isinstance(raw_draft, ICFDraft) else None)
    if not icf_draft:
        raise ValueError("ICF draft is missing or invalid for validation.")
    
    raw_pf = state.get("patient_friendly_icf")
    patient_friendly = ICFDraft.model_validate(raw_pf) if isinstance(raw_pf, dict) else (raw_pf if isinstance(raw_pf, ICFDraft) else icf_draft)
    
    raw_facts = state.get("facts")
    facts = ProtocolFacts.model_validate(raw_facts) if isinstance(raw_facts, dict) else (raw_facts if isinstance(raw_facts, ProtocolFacts) else None)

    req = ICFValidationRequest(
        study_id=study_id,
        icf_draft=icf_draft,
        patient_friendly_icf=patient_friendly,
        protocol_facts=facts,
    )
    report: ICFValidationReport = validation_agent.validate_icf(req)
    if hasattr(report, "revision"):
        report.revision = state.get("revision", 1)

    report_dump = report.model_dump(mode="json") if hasattr(report, "model_dump") else (report if isinstance(report, dict) else {})

    return {
        **state,
        "validation_report": report_dump,
        "workflow_status": "validated",
    }


def node_human_review_checkpoint(state: ICFWorkflowState) -> ICFWorkflowState:
    study_id = state.get("study_id")
    if not study_id:
        raise ValueError("Study ID is required for human review checkpoint.")
    logger.info(f"[LangGraph Node] Checking human review status for study '{study_id}'...")
    review_record = human_review_service.get_review(study_id)
    if review_record and hasattr(review_record.review_status, "value"):
        status = str(review_record.review_status.value)
    elif review_record:
        status = str(review_record.review_status)
    else:
        status = "PENDING"
    comment = review_record.reviewer_comment if review_record else None

    return {
        **state,
        "review_status": status,
        "reviewer_feedback": comment,
        "workflow_status": "awaiting_review" if status == "PENDING" else ("approved" if status == "APPROVED" else "changes_requested"),
    }


def node_handle_revision(state: ICFWorkflowState) -> ICFWorkflowState:
    current_rev = state.get("revision", 1)
    new_rev = current_rev + 1
    logger.info(f"[LangGraph Node] Preparing revision v{new_rev} for study '{state.get('study_id')}'...")
    return {
        **state,
        "revision": new_rev,
        "review_status": "PENDING",
        "workflow_status": "revising",
    }


def node_prepare_export(state: ICFWorkflowState) -> ICFWorkflowState:
    study_id = state.get("study_id")
    if not study_id:
        raise ValueError("Study ID is required to prepare export.")
    logger.info(f"[LangGraph Node] Finalizing export readiness for approved study '{study_id}'...")
    if state.get("review_status") != "APPROVED":
        raise ValueError("Cannot prepare export for unapproved consent drafts.")
    
    return {
        **state,
        "workflow_status": "completed",
    }


def route_human_review(state: ICFWorkflowState) -> str:
    status = state.get("review_status", "PENDING")
    rev = state.get("revision", 1)
    max_rev = state.get("max_revisions", DEFAULT_MAX_REVISIONS)

    if status == "APPROVED":
        return "prepare_export"
    elif status == "CHANGES_REQUESTED" and rev < max_rev:
        return "handle_revision"
    else:
        return "await_review"


def create_icf_langgraph_workflow():
    workflow = StateGraph(cast(type, ICFWorkflowState))

    workflow.add_node("ingest_protocol", node_ingest_protocol)
    workflow.add_node("analyze_protocol", node_analyze_protocol)
    workflow.add_node("generate_icf", node_generate_icf)
    workflow.add_node("validate_icf", node_validate_icf)
    workflow.add_node("human_review_checkpoint", node_human_review_checkpoint)
    workflow.add_node("handle_revision", node_handle_revision)
    workflow.add_node("prepare_export", node_prepare_export)

    workflow.add_edge(START, "ingest_protocol")
    workflow.add_edge("ingest_protocol", "analyze_protocol")
    workflow.add_edge("analyze_protocol", "generate_icf")
    workflow.add_edge("generate_icf", "validate_icf")
    workflow.add_edge("validate_icf", "human_review_checkpoint")

    workflow.add_conditional_edges(
        "human_review_checkpoint",
        route_human_review,
        {
            "prepare_export": "prepare_export",
            "handle_revision": "handle_revision",
            "await_review": END,
        }
    )

    workflow.add_edge("handle_revision", "generate_icf")
    workflow.add_edge("prepare_export", END)

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


compiled_icf_workflow = create_icf_langgraph_workflow()
