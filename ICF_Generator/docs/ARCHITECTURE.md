# AI-Assisted Informed Consent Form (ICF) Generator — System Architecture & Technical Manual

---

## 1. System Architecture Overview

The **AI-Assisted ICF Generator** is a hybrid clinical document processing and compliance automation platform built to translate complex clinical trial protocols into grounded, participant-facing Informed Consent Forms (ICF).

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             REACT + VITE FRONTEND                                │
│  ┌───────────────────────────────┐     ┌──────────────────────────────────────┐  │
│  │ Study Selection & Protocol    │     │ Live Workflow Pipeline Status        │  │
│  │ Ingestion Dashboard           │     │ Progress Tracker                     │  │
│  └───────────────┬───────────────┘     └──────────────────┬───────────────────┘  │
│                  │                                        │                      │
│  ┌───────────────▼───────────────┐     ┌──────────────────▼───────────────────┐  │
│  │ Human Review & Regeneration   │     │ Final DOCX Document Export           │  │
│  │ Workspace                     │     │ Generator                            │  │
│  └───────────────────────────────┘     └──────────────────────────────────────┘  │
└──────────────────────────────────────────┬───────────────────────────────────────┘
                                           │ HTTP REST / JSON
┌──────────────────────────────────────────▼───────────────────────────────────────┐
│                              FASTAPI BACKEND                                     │
│  ┌───────────────────────────────┐     ┌──────────────────────────────────────┐  │
│  │ Ingestion & File Validator    │     │ Canonicalization & Chunking Engine   │  │
│  └───────────────┬───────────────┘     └──────────────────┬───────────────────┘  │
│                  │                                        │                      │
│  ┌───────────────▼───────────────┐     ┌──────────────────▼───────────────────┐  │
│  │ Semantic Embedding Service    │     │ FAISS Local Vector Database &        │  │
│  │ (sentence-transformers)       │     │ Similarity Search                    │  │
│  └───────────────┬───────────────┘     └──────────────────┬───────────────────┘  │
│                  │                                        │                      │
│  ┌───────────────▼───────────────┐     ┌──────────────────▼───────────────────┐  │
│  │ Grounded RAG Context          │     │ Protocol Analysis Agent              │  │
│  │ Assembler Service             │     │ (Structured Facts Extractor)         │  │
│  └───────────────┬───────────────┘     └──────────────────┬───────────────────┘  │
│                  │                                        │                      │
│  ┌───────────────▼───────────────┐     ┌──────────────────▼───────────────────┐  │
│  │ ICF Content Generation        │     │ Compliance & Safety Validation       │  │
│  │ & Patient-Friendly Service    │     │ Agent                                │  │
│  └───────────────┬───────────────┘     └──────────────────┬───────────────────┘  │
│                  │                                        │                      │
│  ┌───────────────▼───────────────┐     ┌──────────────────▼───────────────────┐  │
│  │ Human Review Workflow         │     │ Formatted Word (.docx) Document      │  │
│  │ Repository                    │     │ Generator Service                    │  │
│  └───────────────────────────────┘     └──────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Comprehensive Module & Agent Specifications

### 2.1 Protocol File Validator & Document Processor
- **Module Path:** [`backend/app/services/file_validator.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator/backend/app/services/file_validator.py), [`backend/app/services/document_processing/document_processor.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator/backend/app/services/document_processing/document_processor.py)
- **Input:** Raw file uploads (`.pdf`, `.docx`, `.txt`, `.json`).
- **Output:** `ExtractedTextResponse` containing normalized full text, page/section breakdowns, and character counts.
- **Error Handling:** Validates file magic headers, enforces a 50 MB size limit, rejects 0-byte uploads, and flags image-only PDFs with `status="no_extractable_text"` without crashing the server.

### 2.2 Canonicalization Engine
- **Module Path:** [`backend/app/services/canonicalization/canonicalization_engine.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator/backend/app/services/canonicalization/canonicalization_engine.py)
- **Input:** Document text, page structures, or preloaded study JSON objects.
- **Output:** `CanonicalProtocolResponse` mapping raw content into a standardized schema (`study_id`, `title`, `phase`, `eligibility`, `interventions`, `objectives`, `outcomes`, `risks`, `benefits`).

### 2.3 Section-Aware Chunker & Local Vector Database (FAISS)
- **Module Path:** [`backend/app/services/chunking/chunker.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator/backend/app/services/chunking/chunker.py), [`backend/app/services/vector_store.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator/backend/app/services/vector_store.py)
- **Embedding Model:** Local `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional dense vectors).
- **Vector Index:** Local FAISS `IndexFlatIP` with L2-normalized vectors enabling exact inner-product cosine similarity search and persistent disk caching (`data/vector_store/index.faiss`).

### 2.4 Grounded RAG Context Assembler
- **Module Path:** [`backend/app/services/context_assembler.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator/backend/app/services/context_assembler.py)
- **Input:** `RAGRetrieveRequest` (`query`, `study_id`, `top_k`, `min_score_threshold`, `enable_diversity`).
- **Output:** `RAGContextResponse` containing grounded evidence chunks with unique IDs (`source_evidence_ids`).

### 2.5 Protocol Analysis Agent
- **Module Path:** [`backend/app/services/protocol_analysis_agent.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator/backend/app/services/protocol_analysis_agent.py)
- **Purpose:** Extracts structured clinical facts (`ProtocolFacts`) strictly grounded in RAG evidence.
- **Input:** `RAGContextResponse` package.
- **Output:** `ProtocolFacts` schema containing traceable facts with explicit grounding status (`SUPPORTED`, `NOT_FOUND`, `UNCERTAIN`).
- **Execution Mode:** Uses Anthropic Claude (`claude-3-5-sonnet-20241022`) when configured; automatically falls back to a deterministic grounded extractor when offline or API keyless.

### 2.6 ICF Content Generation & Patient-Friendly Service
- **Module Path:** [`backend/app/services/icf_generation_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator/backend/app/services/icf_generation_service.py)
- **Purpose:** Generates a structured 13-section baseline ICF draft and optional patient-friendly plain-language version.
- **Revision Control:** Auto-increments draft revision numbers (`v1` $\rightarrow$ `v2`) upon receiving human reviewer feedback.
- **Auto-Reset:** Automatically resets backend human review status for the study to `PENDING` upon revision.

### 2.7 Compliance & Safety Validation Agent
- **Module Path:** [`backend/app/services/validation_agent.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator/backend/app/services/validation_agent.py)
- **Purpose:** Performs multi-dimensional audit across 5 compliance dimensions:
  1. Groundedness & Hallucination Check (30% weight)
  2. Fact Completeness & Coverage Check (25% weight)
  3. NOT_FOUND Integrity Check (20% weight)
  4. Source Evidence Traceability Check (15% weight)
  5. Readability & Health Literacy Check (10% weight)
- **Output:** `ICFValidationReport` with overall compliance score (0-100%), status (`PASSED`, `REQUIRES_REVIEW`, `FAILED`), and revision number.

### 2.8 Human Review Workflow Service
- **Module Path:** [`backend/app/services/human_review_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator/backend/app/services/human_review_service.py)
- **States:** `PENDING`, `APPROVED`, `CHANGES_REQUESTED`.
- **Validation:** Requires non-empty reviewer comment when status is set to `CHANGES_REQUESTED`.

### 2.9 Formatted DOCX Document Export Service
- **Module Path:** [`backend/app/services/docx_generation_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator/backend/app/services/docx_generation_service.py)
- **Purpose:** Generates formatted Word (`.docx`) documents using `python-docx`.
- **Security Check:** Strictly enforces `APPROVED` human review state on the backend (`HTTP 409 Conflict` if unapproved).
- **Metadata Table:** Includes study ID, document type, revision version (`v1`, `v2`), generation timestamp, and explicit internal workflow disclaimer.

---

## 3. Data Flow & Traceability Matrix

```text
Protocol Document / JSON
        ↓
Text Extraction & Canonicalization
        ↓
Section-Aware Chunks (Attached chunk_id: e.g. "NCT00081328_eligibility_014")
        ↓
Dense Vectors (FAISS Vector Index)
        ↓
RAG Context Retrieval
        ↓
Protocol Analysis Agent (Facts tagged with source_evidence_ids)
        ↓
ICF Content Generation (13 Sections preserving source_evidence_ids)
        ↓
Compliance & Safety Validation Agent (Traceability & Groundedness Audit)
        ↓
Human Review Decision Workspace
        ↓ (If CHANGES_REQUESTED -> Targeted Regeneration -> Revision v2 -> Auto Reset to PENDING)
        ↓ (If APPROVED)
Formatted DOCX Export with Metadata & Signature Block
```

---

## 4. Known Limitations & Technical Boundaries

1. **In-Memory Volatility:** Active study drafts, revision histories, and review decisions reside in FastAPI memory. Server restarts restore studies to initial preloaded state.
2. **OCR Requirement for Scanned Documents:** Image-only or scanned PDF documents return `status="no_extractable_text"`. Full text conversion requires an external OCR pipeline (e.g. Tesseract).
3. **Execution Modes:** Demonstrates production LLM orchestration with Claude Sonnet when `ANTHROPIC_API_KEY` is present, while providing deterministic fallback execution for keyless offline evaluation.
4. **Internal Workflow Disclaimer:** Exported consent documents are intended for internal workflow and research review. They do NOT constitute regulatory, IRB, or legal approval.
