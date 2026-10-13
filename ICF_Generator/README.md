# AI-Assisted Informed Consent Form (ICF) Generator

An AI-assisted workflow designed to extract structured clinical-trial protocol data, retrieve relevant source evidence using RAG, generate standard and patient-friendly Informed Consent Forms (ICF), run automated validation, support human review and revisions, and export the approved revision as PDF or editable Word (`.docx`).

The normal workspace has four user-facing milestones: choose a study or upload a protocol, click **Generate informed consent form**, review both versions, and export after approval. Generation automatically prepares protocol evidence, retrieves study information, creates both drafts, validates them and prepares the documents while showing progress in the existing workspace. Requesting changes saves reviewer feedback and starts the next revision automatically. Use the built-in layout or upload an optional study-specific DOCX template. See [Templates, review and PDF export](docs/TEMPLATE_PDF_WORKFLOW.md) for template preparation, LibreOffice setup, API details, tests and limitations.

---

## 1. Problem Statement

Clinical trial Informed Consent Forms (ICFs) are critical ethical and regulatory documents required to protect study participants. However, traditional manual ICF drafting suffers from several key challenges:
- **Complexity & Jargon:** Clinical trial protocols are lengthy, highly technical, and difficult for non-expert participants to comprehend.
- **Human Error & Omissions:** Important protocol details (eligibility criteria, visit schedules, specific risks) can be accidentally omitted or inaccurately stated.
- **Hallucination Risk in AI:** Unconstrained LLM generation can invent non-existent hospital contacts, compensation claims, or medical guarantees.
- **Version Control & Iteration Overhead:** Managing reviewer feedback and maintaining section-by-section traceability across revisions is labor-intensive.

---

## 2. Project Objectives

The **AI-Assisted ICF Generator** addresses these challenges by providing an end-to-end clinical software solution:
1. **Automated Fact Extraction:** Map protocol content into structured, standardized representations (`CanonicalProtocol` and `ProtocolFacts`).
2. **Strict Evidence Grounding:** Use Retrieval-Augmented Generation (RAG) to ensure every generated statement maintains chunk-level traceability (`source_evidence_ids`).
3. **Dual-Draft Generation:** Produce both a 13-section standard baseline ICF and a patient-friendly plain-language simplification.
4. **Automated Validation:** Audit ICF drafts across 5 compliance dimensions (Groundedness, Completeness, NOT_FOUND Integrity, Readability, Traceability).
5. **Human-in-the-Loop Review:** Enable clinical reviewers to approve or request changes with targeted feedback that drives version-controlled regeneration (`v1` $\rightarrow$ `v2`).
6. **Template-Based PDF and DOCX Export:** Populate the default or custom DOCX layout and export the exact approved study revision. PDF is the primary UI option; editable Word remains available.

---

## 3. Workflow & Solution Overview

```text
┌─────────────────┐     ┌─────────────────────────────┐     ┌───────────────────┐
│ Study & protocol│ ──▶ │ Generate ICF                │ ──▶ │ Human review      │
└─────────────────┘     │ Automatically prepares      │     │ Review both drafts│
                        │ evidence, both drafts,      │     └─────────┬─────────┘
                        │ validation and documents    │               │
                        └─────────────────────────────┘      ┌────────┴────────┐
                                                          Request changes   Approve
                                                                │              │
                                           New revision and validation ──┐    ▼
                                                                └────▶ Review   Export
```

---

## 4. Key Features

- **Multi-Format Protocol Processing:** Parses `.pdf`, `.docx`, `.txt`, and `.json` protocol documents.
- **Section-Aware RAG Retrieval:** Uses dense vector embeddings (`all-MiniLM-L6-v2`) and FAISS to retrieve grounded protocol evidence.
- **Strict Fact Traceability:** Fact-level and section-level chunk ID tracking (`["NCT00081328_eligibility_014"]`).
- **Patient-Friendly Health Literacy Transformation:** Simplifies medical jargon into plain English.
- **Multi-Dimensional Validation Agent:** Calculates an overall compliance score (0-100%) and evaluates Groundedness, Completeness, NOT_FOUND Integrity, Traceability, and Readability.
- **Version-Controlled Human Review & Regeneration:** Supports `PENDING`, `APPROVED`, and `CHANGES_REQUESTED` review states, auto-incrementing revisions (`v1`, `v2`) upon regeneration with reviewer feedback.
- **Optional Custom Templates:** Upload, replace, view or remove a study-specific DOCX template. The template supplies layout; protocol facts remain the clinical evidence source.
- **Revision-Bound Export:** PDF and DOCX downloads require approval of the current study, revision, template and draft content. New generation or a template change requires review again.

---

## 5. Technology Stack

- **Backend:** Python 3.12, FastAPI, Uvicorn, Pydantic v2, `python-docx`, `pypdf`, `sentence-transformers`, `faiss-cpu`, `httpx`
- **Frontend:** React 18, Vite, Vanilla CSS (existing consent workspace design)
- **PDF conversion:** LibreOffice installed on the backend host
- **Testing:** Pytest, FastAPI TestClient
- **Data Formats Supported:** `.pdf`, `.docx`, `.txt`, `.json`

---

## 6. System Requirements & Prerequisites

- **Python:** Python 3.10+ (Python 3.12 recommended)
- **Node.js:** Node.js 18+ and npm
- **OS:** Windows, macOS, or Linux
- **PDF export:** LibreOffice on PATH or configured through `LIBREOFFICE_PATH`. DOCX export works without it.

---

## 7. Installation Instructions

### Step 1: Clone or Open Workspace
Navigated to workspace directory `ICF_Generator`.

### Step 2: Install Backend Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Step 3: Install Frontend Dependencies
```bash
cd ../frontend
npm ci
```

---

## 8. Startup Instructions

### 1. Start FastAPI Backend Server
Open Terminal 1:
```bash
cd backend
python -m uvicorn app.main:app --reload --port 8001
```
Backend API will be running at: `http://127.0.0.1:8001`

### 2. Start React Frontend Development Server
Open Terminal 2:
```bash
cd frontend
npm run dev
```
Frontend Web UI will be running at: `http://localhost:5173`

---

## 9. Environment Variable Configuration

Configure optional variables in the backend process environment (the application does not automatically load `.env` files):

```env
# Optional LLM Provider Configuration
LLM_PROVIDER=gemini                     # Options: 'gemini', 'anthropic', 'openai', 'mock', 'auto'
GEMINI_API_KEY=your_gemini_key_here      # Required for live Gemini API calls
GEMINI_PRIMARY_MODEL=gemini-3.8-flash   # Primary Gemini model
GEMINI_FALLBACK_MODEL=gemini-2.5-flash  # Fallback Gemini model if primary fails
ANTHROPIC_API_KEY=your_api_key_here      # Required for live Anthropic API calls
OPENAI_API_KEY=your_api_key_here    # Required if LLM_PROVIDER=openai
# Optional if LibreOffice is not discoverable in a standard location:
# LIBREOFFICE_PATH=C:\Program Files\LibreOffice\program\soffice.com
```
*Note: If no API key is set, the system automatically runs using its deterministic grounded extraction and generation engine.*
*Live Gemini Connectivity Test:* Set `GEMINI_API_KEY` and run `pytest tests/test_gemini_live.py`.


---

## 10. API Endpoint Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Backend service health check |
| `GET` | `/api/studies` | Lists preloaded study summaries |
| `GET` | `/api/studies/{study_id}` | Fetches raw study JSON details |
| `GET` | `/api/studies/{study_id}/canonical` | Converts study to `CanonicalProtocol` representation |
| `GET` | `/api/studies/{study_id}/chunks` | Generates section-aware chunks |
| `GET` | `/api/studies/{study_id}/embed` | Generates semantic embeddings for chunks |
| `POST/GET` | `/api/studies/{study_id}/index` | Indexes study embeddings into local FAISS vector store |
| `POST` | `/api/protocol/upload` | Validates uploaded file and stores safely |
| `POST` | `/api/protocol/process` | Extracts page-by-page normalized text |
| `POST` | `/api/protocol/canonicalize` | Canonicalizes uploaded protocol document |
| `POST` | `/api/protocol/chunk` | Splits protocol document into chunks |
| `POST` | `/api/protocol/embed` | Generates embeddings for protocol chunks |
| `POST` | `/api/protocol/index` | Indexes uploaded protocol chunks into FAISS store |
| `GET` | `/api/vector-store/status` | Returns FAISS vector store status and indexed study count |
| `POST` | `/api/search` | Executes semantic vector similarity search against FAISS store |
| `POST` | `/api/rag/retrieve` | Assembles grounded RAG context with evidence chunk traceability |
| `POST` | `/api/protocol/analyze` | Protocol Analysis Agent extracts structured study facts (`ProtocolFacts`) |
| `POST` | `/api/icf/generate` | Generates or revises structured baseline ICF draft and patient-friendly version |
| `POST` | `/api/icf/workflow` | Starts the automatic workflow; multipart `study_id` for a preloaded study, or `protocol` for an uploaded source, plus optional `template` DOCX |
| `GET` | `/api/icf/workflow/{job_id}` | Reads workflow status, user-facing progress and completed result |
| `POST` | `/api/icf/validate` | Validation Agent executes multi-dimensional compliance and safety audit |
| `GET` | `/api/icf/review/{study_id}` | Fetches current human review status for a study |
| `POST/PUT`| `/api/icf/review/{study_id}` | Updates human review status (`PENDING`, `APPROVED`, `CHANGES_REQUESTED`) and comments |
| `GET/POST/DELETE` | `/api/icf/template/{study_id}` | Inspect, upload/replace or remove the study template |
| `GET` | `/api/icf/template/{study_id}/file` | Download the custom reference template |
| `GET` | `/api/icf/revisions/{study_id}` | Revision snapshots and review decisions |
| `GET` | `/api/icf/export-capabilities` | PDF converter availability |
| `POST` | `/api/icf/export/{study_id}?format=pdf&export_type=standard&revision=1` | Export the approved current revision; use `docx` for editable output or `patient_friendly` for the simplified version |

---

## 11. How to Run Automated Test Suites

### Backend Pytest Execution
From the project root directory:
```bash
python -m pytest tests/
```
Configure LibreOffice to include the real PDF conversion integration tests. Those tests skip when the converter is unavailable.
The automatic source-to-consent orchestration is covered by `tests/test_icf_workflow.py`.

### Frontend Production Build Execution
From the `frontend/` directory:
```bash
npm run build
node tests/workflow.test.mjs
node --test tests/template-export.test.mjs
```

---

## 12. Known Limitations & Technical Boundaries

1. **In-Memory Store Persistence:** Generated drafts and review state reside in FastAPI memory and will reset upon restarting the backend server.
2. **OCR for Scanned Documents:** Image-only or scanned PDFs return `status="no_extractable_text"` without calling an external OCR engine.
3. **Internal Workflow Disclaimer:** Exported consent documents are intended for internal workflow and research review. They do NOT constitute regulatory, IRB, or legal approval.
4. **Deployment:** Run one backend worker. Existing in-memory state and study locks do not coordinate multiple workers. The local workflow does not provide authenticated reviewer roles.
5. **Custom Layouts:** Unsupported DOCX features are rejected; font availability and long content can change pagination. Review retained template wording and the rendered PDF before use. See the detailed workflow guide for supported placeholders and restrictions.
