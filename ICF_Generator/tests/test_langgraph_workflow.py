import os
import sys
import pytest

sys.path.insert(0, os.path.abspath("backend"))

from app.services.langgraph_workflow import (
    ICFWorkflowState,
    compiled_icf_workflow,
    node_ingest_protocol,
    node_analyze_protocol,
    node_generate_icf,
    node_validate_icf,
    node_human_review_checkpoint,
    node_handle_revision,
    node_prepare_export,
    route_human_review,
    DEFAULT_MAX_REVISIONS
)
from app.services.human_review_service import human_review_service


def test_langgraph_workflow_state_schema():
    state: ICFWorkflowState = {
        "job_id": "test_job_123",
        "study_id": "NCT00081328",
        "revision": 1,
        "max_revisions": 3,
        "review_status": "PENDING",
        "workflow_status": "queued"
    }
    assert state["study_id"] == "NCT00081328"
    assert state["revision"] == 1
    assert state["max_revisions"] == 3


def test_langgraph_workflow_nodes_ingest_and_analyze():
    initial_state: ICFWorkflowState = {
        "job_id": "test_job_nodes",
        "study_id": "NCT00081328",
        "revision": 1,
        "max_revisions": 3,
    }
    ingested = node_ingest_protocol(initial_state)
    assert ingested["workflow_status"] == "ingested"
    assert ingested.get("canonical_protocol") is not None

    analyzed = node_analyze_protocol(ingested)
    assert analyzed["workflow_status"] == "analyzed"
    assert analyzed.get("facts") is not None
    assert analyzed["facts"]["study_id"] == "NCT00081328"


def test_langgraph_workflow_end_to_end_execution():
    initial_state: ICFWorkflowState = {
        "job_id": "test_job_e2e",
        "study_id": "NCT00081328",
        "revision": 1,
        "max_revisions": 3,
    }
    config = {"configurable": {"thread_id": "test_job_e2e"}}
    final_state = compiled_icf_workflow.invoke(initial_state, config=config)

    assert final_state["study_id"] == "NCT00081328"
    assert final_state["workflow_status"] == "awaiting_review"
    assert final_state.get("icf_draft") is not None
    assert final_state.get("validation_report") is not None
    assert final_state.get("revision") == 1


def test_langgraph_workflow_conditional_routing_and_stopping_conditions():
    # 1. PENDING status -> stops at await_review (END)
    state_pending: ICFWorkflowState = {"review_status": "PENDING", "revision": 1, "max_revisions": 3}
    assert route_human_review(state_pending) == "await_review"

    # 2. APPROVED status -> routes to prepare_export
    state_approved: ICFWorkflowState = {"review_status": "APPROVED", "revision": 1, "max_revisions": 3}
    assert route_human_review(state_approved) == "prepare_export"

    # 3. CHANGES_REQUESTED under max_revisions -> routes to handle_revision
    state_changes: ICFWorkflowState = {"review_status": "CHANGES_REQUESTED", "revision": 1, "max_revisions": 3}
    assert route_human_review(state_changes) == "handle_revision"

    # 4. CHANGES_REQUESTED at max_revisions -> stops at await_review (prevents infinite loop)
    state_max_changes: ICFWorkflowState = {"review_status": "CHANGES_REQUESTED", "revision": 3, "max_revisions": 3}
    assert route_human_review(state_max_changes) == "await_review"


def test_langgraph_workflow_human_review_and_revision_loop():
    initial_state: ICFWorkflowState = {
        "job_id": "test_job_rev",
        "study_id": "NCT00081328",
        "revision": 1,
        "max_revisions": 3,
        "review_status": "CHANGES_REQUESTED",
        "reviewer_feedback": "Please clarify visit schedule."
    }
    revised_state = node_handle_revision(initial_state)
    assert revised_state["revision"] == 2
    assert revised_state["review_status"] == "PENDING"
    assert revised_state["workflow_status"] == "revising"


def test_langgraph_workflow_approval_gated_export():
    unapproved_state: ICFWorkflowState = {
        "study_id": "NCT00081328",
        "review_status": "PENDING",
        "revision": 1
    }
    with pytest.raises(ValueError, match="Cannot prepare export for unapproved consent drafts"):
        node_prepare_export(unapproved_state)

    approved_state: ICFWorkflowState = {
        "study_id": "NCT00081328",
        "review_status": "APPROVED",
        "revision": 1
    }
    result = node_prepare_export(approved_state)
    assert result["workflow_status"] == "completed"


def test_langgraph_workflow_deterministic_fallback_in_nodes():
    initial_state: ICFWorkflowState = {
        "job_id": "test_job_fallback",
        "study_id": "NCT00081328",
        "revision": 1,
        "max_revisions": 3,
    }
    # Run nodes sequentially in keyless offline environment
    s1 = node_ingest_protocol(initial_state)
    s2 = node_analyze_protocol(s1)
    s3 = node_generate_icf(s2)
    s4 = node_validate_icf(s3)

    assert s4.get("icf_draft") is not None
    assert s4.get("validation_report") is not None
    assert s4["validation_report"]["overall_score"] >= 0.0
