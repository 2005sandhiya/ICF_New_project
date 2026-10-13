# Implementation Documentation: AI-Assisted Patient-Facing Informed Consent Form (ICF) Generator

---

## Executive Summary
This document provides a comprehensive, beginner-friendly technical explanation of the **AI-Assisted Patient-Facing Informed Consent Form (ICF) Generator** project. It is written from the perspective of a Senior Software Engineer to help a final-year engineering student thoroughly understand, present, and defend the complete system architecture, data processing workflows, AI integrations, validation safeguards, testing results, and code implementation.

---

# Chapter 1: Project Overview

### 1.1 Project Title
**AI-Assisted Patient-Facing Informed Consent Form (ICF) Generator**

### 1.2 Problem Statement
In clinical research, **Informed Consent Forms (ICFs)** are legally required documents that explain study purpose, procedures, risks, benefits, confidentiality, and participant rights. Traditional clinical protocol consent forms are typically 25 to 45 pages long, filled with complex medical jargon, dense legal phrasing, and high-level scientific descriptions. Research shows that over **70% of clinical trial participants** do not fully comprehend the procedures, risks, or voluntary nature of trials due to readability barriers.

Manual drafting of patient-friendly ICFs by clinical trial coordinators requires tens of hours per protocol, is prone to inconsistent section coverage, and risks omitting critical safety warnings or duplicating multi-paragraph medical descriptions across visit tables.

### 1.3 Motivation
Recent advancements in **Generative AI** and **Retrieval-Augmented Generation (RAG)** enable automated extraction of clinical facts from study protocols and translation into patient-friendly language (Target: Flesch-Kincaid Grade Level ≤ 8.0). However, deploying LLMs in clinical research presents strict safety requirements:
1. **Zero Clinical Hallucination:** Missing clinical facts (e.g., optional biological sample storage) must never be fabricated.
2. **Template Parity:** Built-in templates and user-uploaded custom Word templates must receive equal evidence and content completeness without arbitrary section stripping.
3. **Traceability:** Every generated statement must trace directly back to verifiable protocol source evidence.
4. **Human-in-the-Loop Safeguards:** Clinical trial coordinators must review and approve generated drafts before document export.

### 1.4 Objectives
- Automate ingestion and canonicalization of unstructured study protocols (PDF, DOCX, TXT, JSON).
- Build a vector index using **FAISS** and **Sentence-Transformers** for semantic evidence retrieval.
- Orchestrate a deterministic multi-stage LLM generation workflow using **LangGraph** and **Google Gemini** (`gemini-3.8-flash` primary, `gemini-3.5-flash` fallback).
- Standardize patient-facing text across 13 core ICF sections while simplifying medical jargon.
- Provide a common content-generation and rendering pipeline for both built-in templates (`standard_v1`) and user-uploaded custom templates.
- Enforce automated quality controls, evidence grounding verification, cross-study contamination audits, and duplicate content detection via a dedicated `ValidationAgent`.
- Support an interactive human-in-the-loop review workflow in a modern React frontend.

### 1.5 Proposed Solution
The system implements a dual-tier web application architecture:
- **Frontend:** A React 18 single-page application built with Vite, offering real-time progress indicators, intelligence panels, template previewing, side-by-side clinical draft review, and one-click DOCX/PDF export.
- **Backend:** A FastAPI high-performance Python application organizing document parsing, RAG vector indexing, LangGraph workflow execution, Gemini LLM generation, validation auditing, and Word/PDF document rendering.

### 1.6 Intended Users
- **Clinical Research Coordinators (CRCs):** Draft, review, and export patient-facing ICFs for upcoming clinical trials.
- **Institutional Review Boards (IRBs) / Ethics Committees:** Inspect validation reports, readability metrics, and evidence grounding sources.
- **Clinical Trial Sponsors:** Standardize consent form branding and formatting across multi-center trials using custom Word templates.

### 1.7 Input and Output
- **Inputs:**
  1. Clinical Protocol Document: JSON (`NCT00081328.json`), PDF, DOCX, or TXT.
  2. Selected ICF Template: Built-in standard template or uploaded custom Word document (`.docx`).
  3. Generation Preferences: Target reading grade level (default: 8.0), jargon simplification toggle, template selection.
- **Outputs:**
  1. Structured ICF Draft (JSON representation with section-level grounding and confidence scores).
  2. Patient-Facing ICF Document: Exported Word (`.docx`) or Adobe PDF (`.pdf`) preserving template styles.
  3. Validation & Compliance Audit Report (Readability score, evidence coverage %, missing information flags, approval status).

### 1.8 Scope and Limitations
- **In Scope:** Protocol ingestion, RAG indexing, 13 standard section generations, patient-friendly translation, built-in & custom Word template population, validation checks, human review workflow, Pytest suite (303 passed tests), DOCX export, PDF export.
- **Out of Scope / Limitations:** Automated IRB submission integration, multi-language translation (currently English-only), direct EHR integration.

---

# Chapter 2: Technology Stack

The following table details every technology and library implemented in the project, verified directly from [`backend/requirements.txt`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/requirements.txt) and [`frontend/package.json`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/frontend/package.json):

| Technology / Library | Version | Category | Purpose & Implementation Location | Evidence in Codebase |
| :--- | :--- | :--- | :--- | :--- |
| **Python** | `3.12.0` | Backend Language | Core application runtime for FastAPI backend, RAG pipeline, and document processing. | [`backend/app/main.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/main.py) |
| **FastAPI** | `>=0.100.0` | Web Framework | Asynchronous HTTP REST API routing, request validation, and OpenAPI documentation. | [`backend/app/api/`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/api) |
| **Uvicorn** | `>=0.22.0` | ASGI Server | High-performance asynchronous web server hosting the FastAPI application on port 8001. | [`backend/app/main.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/main.py#L38) |
| **Pydantic** | `>=2.0.0` | Data Validation | Strongly-typed schema definitions for protocol facts, ICF drafts, validation reports, and requests. | [`backend/app/models/`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/models) |
| **React** | `^18.2.0` | Frontend Framework | Component-based interactive UI for protocol upload, workflow tracking, review, and export. | [`frontend/src/App.jsx`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/frontend/src/App.jsx) |
| **Vite** | `^5.0.0` | Frontend Build Tool | Blazing-fast development server and module bundler hosting frontend on port 5173. | [`frontend/vite.config.js`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/frontend/vite.config.js) |
| **Sentence-Transformers** | `>=3.0.0` | Embeddings | Generates 384-dimensional dense vector embeddings using `all-MiniLM-L6-v2`. | [`backend/app/services/embedding_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/embedding_service.py#L18) |
| **FAISS (faiss-cpu)** | `>=1.8.0` | Vector Database | Performs fast L2-distance similarity search over protocol text chunks. | [`backend/app/services/vector_store.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/vector_store.py#L24) |
| **Google GenAI SDK** | `>=2.0.0` | LLM API Client | Primary LLM engine invoking `gemini-3.8-flash` and fallback `gemini-3.5-flash`. | [`backend/app/services/llm/gemini_provider.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/llm/gemini_provider.py#L12) |
| **LangChain Core** | `>=0.2.0` | AI Abstractions | Provides prompt templates and LLM adapter interfaces across providers. | [`backend/app/services/langchain_adapters.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/langchain_adapters.py) |
| **LangGraph** | `>=0.1.0` | State Orchestration | Multi-node state graph orchestrating parsing, retrieval, generation, and validation. | [`backend/app/services/langgraph_workflow.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/langgraph_workflow.py#L30) |
| **python-docx** | `>=1.2.0` | DOCX Engine | Reads custom Word templates, populates slot tokens (`{{STUDY_TITLE}}`), and exports DOCX. | [`backend/app/services/template_renderer.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/template_renderer.py#L15) |
| **PyPDF (pypdf)** | `>=5.0.0` | PDF Engine | Extracts raw text from uploaded PDF clinical protocol documents. | [`backend/app/services/document_processing/parsers/pdf_parser.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/document_processing/parsers/pdf_parser.py) |
| **Pytest** | `>=7.0.0` | Test Framework | Executes unit, integration, and regression test suites (303 passed tests). | [`tests/`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/tests) |
| **DeepEval** | `^4.2.8` | Evaluation Framework | Evaluates LLM metrics (faithfulness, relevancy, precision) on evaluation datasets. | [`evaluation/deepeval_evaluation.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/evaluation/deepeval_evaluation.py) |

---

# Chapter 3: Complete Project Structure

```
ICF_Generator/
├── IMPLEMENTATION_DOCUMENTATION.md  # Main technical documentation
├── README.md                         # Project setup overview
├── backend/                          # FastAPI Backend Application
│   ├── app/
│   │   ├── main.py                   # Application entry point & CORS configuration
│   │   ├── api/                      # REST API Endpoint Routers
│   │   │   ├── icf_routes.py         # Generation, revision & export routes
│   │   │   ├── protocol_routes.py    # Protocol upload & parsing routes
│   │   │   ├── study_routes.py       # Study selection & study metadata routes
│   │   │   ├── template_routes.py    # Built-in & custom template upload routes
│   │   │   ├── review_routes.py      # Human review & approval routes
│   │   │   ├── validation_routes.py  # Quality control & validation audit routes
│   │   │   └── workflow_routes.py    # LangGraph execution & step status routes
│   │   ├── models/                   # Pydantic Data Models
│   │   │   ├── canonical_protocol.py # Standardized protocol representation
│   │   │   ├── icf.py                # ICF draft & section models
│   │   │   ├── protocol_facts.py     # Extracted clinical facts model
│   │   │   ├── validation.py         # Validation report models
│   │   │   └── human_review.py       # Review state & approval models
│   │   └── services/                 # Core Business Logic & Services
│   │       ├── icf_generation_service.py # Core LLM ICF generation service
│   │       ├── template_renderer.py  # Word DOCX placeholder population & pruning
│   │       ├── validation_agent.py   # Compliance & evidence grounding auditor
│   │       ├── langgraph_workflow.py # LangGraph state machine orchestrator
│   │       ├── vector_store.py       # FAISS vector store service
│   │       ├── embedding_service.py  # Sentence-Transformers embedding generator
│   │       └── human_review_service.py # Human review & revision persistence
│   └── requirements.txt              # Backend Python dependencies
├── frontend/                         # React + Vite Frontend Web Application
│   ├── src/
│   │   ├── App.jsx                   # Main React application component
│   │   ├── config.js                 # API base URL configuration
│   │   ├── api/                      # Axios HTTP client wrappers
│   │   └── components/               # UI Components
│   │       ├── AppShell.jsx          # Navigation header & main container layout
│   │       ├── IntelligencePanels.jsx # Readability, validation & review UI
│   │       ├── SourcePanels.jsx      # Protocol text & facts inspector
│   │       ├── TemplatePanel.jsx     # Template selection & upload UI
│   │       └── ui.jsx                # Reusable badges, buttons, cards & modals
│   └── package.json                  # Frontend dependencies
├── data/                             # Data Storage Directory
│   ├── protocols/                    # Preloaded study protocols (NCT00081328.json)
│   ├── uploads/                      # User-uploaded files directory
│   └── vector_store/                 # FAISS index files (index.faiss, metadata.json)
├── evaluation/                       # DeepEval & Latency Evaluation Benchmarks
│   ├── deepeval_evaluation.py        # DeepEval metric evaluation runner
│   ├── latency_benchmark.py          # End-to-end latency benchmark tool
│   └── results/                      # Raw JSON, CSV & PDF evaluation reports
└── tests/                            # Pytest Automated Test Suite (303 passed)
```

---

# Chapter 4: System Architecture

The ICF Generator follows a **Layered Microservices Architecture** consisting of four distinct layers:

```
[ React 18 Frontend ] <---> [ FastAPI REST API Layer ] <---> [ LangGraph Workflow Engine ] <---> [ Gemini LLM / FAISS RAG ]
```

### 4.1 Frontend Layer (React 18 + Vite)
- Serves as the user interface on `http://localhost:5173`.
- Communicates asynchronously with the backend via REST endpoints using `fetch`/`axios`.
- Manages local UI state for active study selection, active revision index, validation error lists, and draft approval status.

### 4.2 API Layer (FastAPI)
- Listens on `http://localhost:8001`.
- Provides CORS-enabled endpoints under `/api/v1` for protocol ingestion, RAG search, ICF generation, template management, human review, and file exports.
- Enforces Pydantic request/response schema validation.

### 4.3 Workflow Orchestration Layer (LangGraph)
- Coordinates a 7-node state graph ([`LangGraphICFWorkflow`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/langgraph_workflow.py#L30)).
- Maintains an in-memory `ICFWorkflowState` object capturing study facts, retrieved chunks, generated draft sections, validation reports, human review status, and revision history.

### 4.4 Data & AI Core Layer
- **Ingestion & Processing:** Custom parsers for PDF ([`PyPDF`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/document_processing/parsers/pdf_parser.py)), DOCX ([`docx_parser.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/document_processing/parsers/docx_parser.py)), and JSON ([`json_parser.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/document_processing/parsers/json_parser.py)).
- **RAG Vector Store:** `SentenceTransformers` (`all-MiniLM-L6-v2`) generating 384-dimensional embeddings indexed in a CPU-optimized `FAISS` vector store.
- **LLM Provider:** `GeminiProvider` wrapping Google GenAI SDK with automatic failover between `gemini-3.8-flash` (Primary) and `gemini-3.5-flash` (Fallback).
- **Validation Engine:** `ValidationAgent` enforcing 13-section completeness, evidence grounding, cross-study contamination audits, and duplicate content detection.
- **Document Renderer:** `DocumentTemplateRenderer` injecting populated slot tokens into Word templates (`.docx`) with uniform section pruning.

---

# Chapter 5: End-to-End Execution Flow

The complete execution lifecycle for generating a patient-facing ICF spans 9 distinct steps:

```mermaid
sequenceDiagram
    autonumber
    actor User as Clinical Coordinator
    participant FE as React Frontend
    participant API as FastAPI Backend
    participant LG as LangGraph Workflow
    participant RAG as FAISS Vector Store
    participant LLM as Gemini LLM Engine
    participant VAL as Validation Agent
    participant DOC as Template Renderer

    User->>FE: Select Study (NCT00081328) & Template
    FE->>API: POST /api/icf/generate
    API->>LG: Execute Workflow (study_id, template_id)
    LG->>RAG: Retrieve Evidence Chunks for 13 Sections
    RAG-->>LG: Return Top-3 Evidence Chunks per Section
    LG->>LLM: Generate 13 Section Drafts (Grade <= 8.0)
    LLM-->>LG: Return Patient-Friendly Text & Status
    LG->>VAL: Audit Completeness, Grounding & Duplication
    VAL-->>LG: Return Validation Report (Pass/Fail)
    LG-->>API: Return ICF Draft & Review Status
    API-->>FE: Render Draft, Validation & Review Panels
    User->>FE: Click "Approve Draft" (template_reviewed=True)
    FE->>API: POST /api/icf/review/{study_id}/approve
    API-->>FE: Update Status to APPROVED
    User->>FE: Click "Export DOCX"
    FE->>API: POST /api/icf/export/docx
    API->>DOC: Render Populated DOCX File
    DOC-->>API: Return DOCX Binary Stream
    API-->>FE: Trigger File Download (.docx)
```

### Step 1: Protocol Upload & Selection
- **User Action:** Selects preloaded study `NCT00081328` or uploads a custom protocol PDF/JSON file in the UI.
- **File Involved:** [`frontend/src/components/SourcePanels.jsx`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/frontend/src/components/SourcePanels.jsx)
- **API Endpoint:** `POST /api/protocol/upload` or `GET /api/study/{study_id}`

### Step 2: Protocol Parsing & Canonicalization
- **Action:** Extracts raw protocol text, normalizes headers, and parses structured fields (Interventions, Eligibility, Risks, Objectives).
- **Files Involved:** [`protocol_ingestion_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/protocol_ingestion_service.py), [`canonicalization_engine.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/canonicalization/canonicalization_engine.py)

### Step 3: Chunking & FAISS Vector Indexing
- **Action:** Splits raw text into 500-character chunks with 50-character overlap. Computes 384-dimensional embeddings via `Sentence-Transformers` (`all-MiniLM-L6-v2`) and builds an in-memory `FAISS` L2 index.
- **Files Involved:** [`chunker.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/chunking/chunker.py), [`vector_store.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/vector_store.py)

### Step 4: RAG Context Retrieval
- **Action:** For each of the 13 standard ICF sections, queries the FAISS index for top-3 relevant study evidence chunks.
- **Files Involved:** [`context_assembler.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/context_assembler.py)

### Step 5: LLM Patient-Friendly Draft Generation
- **Action:** Invokes `GeminiProvider` (`gemini-3.8-flash`) to generate patient-friendly text (Target Flesch-Kincaid Grade ≤ 8.0) using retrieved evidence chunks. If evidence is missing, returns explicit `NOT_FOUND` status and grounded notice (`"Not provided in the study protocol."`).
- **Files Involved:** [`icf_generation_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/icf_generation_service.py), [`gemini_provider.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/llm/gemini_provider.py)

### Step 6: Automated Validation Audit
- **Action:** `ValidationAgent` audits the draft for 13-section completeness, evidence grounding, cross-study chunk leakage (checking chunk `study_id` prefix), duplicate content blocks (>50 chars), and template compatibility.
- **Files Involved:** [`validation_agent.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/validation_agent.py)

### Step 7: Human Review & Template Matching Gate
- **Action:** Draft status is set to `PENDING_REVIEW`. The UI displays validation warnings, readability grade, and section text. Clinical coordinator reviews the draft and approves it.
- **Files Involved:** [`human_review_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/human_review_service.py), [`IntelligencePanels.jsx`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/frontend/src/components/IntelligencePanels.jsx)

### Step 8: Document Template Population
- **Action:** `DocumentTemplateRenderer` maps generated draft section values into standard slot tokens (`{{STUDY_TITLE}}`, `{{TREATMENT_DESCRIPTION}}`, etc.) for both built-in templates (`standard_v1`) and user-uploaded custom Word templates. Applies uniform section pruning for ungrounded optional sections.
- **Files Involved:** [`template_renderer.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/template_renderer.py)

### Step 9: DOCX / PDF Document Export
- **Action:** Generates final formatted `.docx` file using `python-docx` or converts to PDF stream, triggering a direct file download in the browser.
- **Files Involved:** [`docx_generation_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/docx_generation_service.py), [`pdf_generation_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/pdf_generation_service.py)

---

# Chapter 6: Frontend Implementation

The frontend is a modern React 18 single-page application built with Vite and Tailwind CSS.

### 6.1 Main Components & File Locations
1. **`App.jsx` ([`frontend/src/App.jsx`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/frontend/src/App.jsx)):** Application root component managing top-level state: `activeStudyId`, `selectedTemplateId`, `icfDraft`, `validationReport`, `reviewStatus`, `isGenerating`.
2. **`AppShell.jsx` ([`frontend/src/components/AppShell.jsx`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/frontend/src/components/AppShell.jsx)):** Shell layout header containing study selector, template selector, generation preferences toggle, and progress bar.
3. **`SourcePanels.jsx` ([`frontend/src/components/SourcePanels.jsx`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/frontend/src/components/SourcePanels.jsx)):** Protocol source viewer displaying raw protocol text, extracted clinical facts, and retrieved vector evidence chunks.
4. **`IntelligencePanels.jsx` ([`frontend/src/components/IntelligencePanels.jsx`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/frontend/src/components/IntelligencePanels.jsx)):** Central workspace displaying the 13 generated ICF sections, readability grade badges (Flesch-Kincaid), validation check warnings, human review approval buttons, and export buttons.
5. **`TemplatePanel.jsx` ([`frontend/src/components/TemplatePanel.jsx`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/frontend/src/components/TemplatePanel.jsx)):** Custom template management modal allowing users to upload `.docx` Word templates and inspect placeholder token mappings.
6. **`client.js` ([`frontend/src/api/client.js`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/frontend/src/api/client.js)):** Axios HTTP client configured with base URL `http://localhost:8001/api`.

---

# Chapter 7: Backend Implementation & REST API Reference

The backend is built with FastAPI and organized into modular API routers in `backend/app/api/`.

### 7.1 API Endpoint Reference Table

| HTTP Method | Route Endpoint | Router File | Purpose | Request Body | Response Payload |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GET** | `/api/health` | [`main.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/main.py) | Server health check | None | `{ status: "ok" }` |
| **GET** | `/api/study/list` | [`study_routes.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/api/study_routes.py) | List preloaded study IDs | None | `[ "NCT00081328", ... ]` |
| **GET** | `/api/study/{study_id}` | [`study_routes.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/api/study_routes.py) | Fetch study facts & protocol metadata | Path param | `StudyFacts` JSON |
| **POST** | `/api/protocol/upload` | [`protocol_routes.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/api/protocol_routes.py) | Upload new protocol file | `multipart/form-data` | `UploadResponse` JSON |
| **POST** | `/api/icf/generate` | [`icf_routes.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/api/icf_routes.py) | Generate complete ICF draft | `ICFGenerationRequest` | `ICFGenerationResponse` |
| **POST** | `/api/icf/review/{study_id}/approve` | [`review_routes.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/api/review_routes.py) | Approve generated ICF draft | `{ template_reviewed: true }` | `HumanReviewState` |
| **POST** | `/api/icf/review/{study_id}/request-changes` | [`review_routes.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/api/review_routes.py) | Request changes & trigger revision | `{ notes: "string" }` | `HumanReviewState` |
| **POST** | `/api/icf/export/docx` | [`icf_routes.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/api/icf_routes.py) | Export populated Word document | `ExportRequest` | `.docx` Binary File Stream |
| **POST** | `/api/icf/export/pdf` | [`icf_routes.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/api/icf_routes.py) | Export PDF document | `ExportRequest` | `.pdf` Binary File Stream |
| **POST** | `/api/template/upload` | [`template_routes.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/api/template_routes.py) | Upload custom Word template | `multipart/form-data` | `TemplateMetadata` JSON |

---

# Chapter 8: AI and LLM Integration

### 8.1 LLM Service Provider Architecture
LLM operations are encapsulated in `GeminiProvider` ([`backend/app/services/llm/gemini_provider.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/llm/gemini_provider.py#L12)).
- **Primary Model:** `gemini-3.8-flash` (Configured via `GEMINI_PRIMARY_MODEL` in `.env`).
- **Fallback Model:** `gemini-3.5-flash` (Configured via `GEMINI_FALLBACK_MODEL` in `.env`).
- **Automatic Failover:** When a `429 RESOURCE_EXHAUSTED` or `503 SERVICE_UNAVAILABLE` error occurs on the primary model, `GeminiProvider` automatically catches the exception, logs a warning, and retries the request using the fallback model.

### 8.2 Prompt Engineering & Grounding Constraints
Generation prompts enforce strict clinical grounding guidelines:
1. **Target Readability:** Plain English suitable for a 14-year-old reader (Flesch-Kincaid Grade Level ≤ 8.0).
2. **Missing Facts Rule:** If the provided evidence chunks do not contain sufficient facts for a required section, the model MUST output: `"Not provided in the study protocol."` and set section status to `"NOT_FOUND"`.
3. **No Clinical Invention:** The prompt explicitly forbids fabricating drug doses, visit numbers, side effect frequencies, or contact phone numbers.

---

# Chapter 9: RAG (Retrieval-Augmented Generation) Pipeline

The RAG pipeline provides evidence-backed context for all 13 standard ICF sections:

```
[ Protocol Document ] -> [ Parsers ] -> [ Text Normalizer ] -> [ Chunker ] -> [ SentenceTransformers ] -> [ FAISS Vector Store ]
```

### 9.1 Technical Specification Table

| Parameter | Configuration / Specification | Implementation Source File |
| :--- | :--- | :--- |
| **Supported Input Formats** | PDF, DOCX, TXT, JSON | [`parsers/`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/document_processing/parsers) |
| **Chunking Strategy** | `RecursiveCharacterTextSplitter` | [`chunker.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/chunking/chunker.py) |
| **Chunk Size** | 500 characters | [`chunker.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/chunking/chunker.py#L15) |
| **Chunk Overlap** | 50 characters | [`chunker.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/chunking/chunker.py#L16) |
| **Embedding Model** | `sentence-transformers/all-MiniLM-L6-v2` | [`embedding_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/embedding_service.py#L18) |
| **Vector Dimensions** | 384 dimensions | [`embedding_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/embedding_service.py#L22) |
| **Vector Index Type** | `faiss.IndexFlatL2` (L2 Euclidean distance) | [`vector_store.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/vector_store.py#L24) |
| **Top-K Retrieval** | K = 3 evidence chunks per section query | [`context_assembler.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/context_assembler.py#L32) |
| **Storage Location** | `data/vector_store/index.faiss` | [`vector_store.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/vector_store.py#L12) |

---

# Chapter 10: LangChain and LangGraph Workflow Orchestration

The application uses **LangGraph** ([`langgraph_workflow.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/langgraph_workflow.py)) to manage multi-step state transitions during document generation.

### 10.1 Graph Structure & Node Responsibilities

```
[ START ] 
    │
    ▼
1. node_parse_protocol ──────► 2. node_analyze_facts ──────► 3. node_index_vectorstore
                                                                      │
                                                                      ▼
6. node_validate_icf ◄─────── 5. node_generate_icf ◄───────── 4. node_retrieve_context
        │
        ├─── (Pass) ─────────► 7. node_human_review ───────► [ END ]
        │
        └─── (Validation Fail / Re-revision Loop) ─────────► 5. node_generate_icf
```

1. **`node_parse_protocol`:** Extracts raw text from the protocol file.
2. **`node_analyze_facts`:** Normalizes protocol text into a structured `ProtocolFacts` object.
3. **`node_index_vectorstore`:** Chunks text and updates the FAISS vector index.
4. **`node_retrieve_context`:** Queries top-3 evidence chunks for all 13 standard sections.
5. **`node_generate_icf`:** Calls Gemini LLM to produce patient-friendly draft sections.
6. **`node_validate_icf`:** Runs `ValidationAgent` compliance audit. If critical validation errors are detected, routes back to node 5 for re-revision (Up to 3 iterations max).
7. **`node_human_review`:** Sets draft review status to `PENDING_REVIEW` and waits for clinical approval.

---

# Chapter 11: Validation and Quality Controls

The [`ValidationAgent`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/validation_agent.py) executes 5 automated quality checks on every generated draft:

1. **Section Completeness Check:** Verifies that all 13 required standard sections are present in `draft.sections`.
2. **Evidence Grounding Audit:** Computes evidence overlap between generated text and retrieved study chunks. Flags sections with low confidence (<0.70).
3. **Cross-Study Contamination Audit ([`_check_traceability`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/validation_agent.py#L95)):** Inspects chunk `study_id` prefixes to ensure evidence from another study (e.g. `NCT02563067`) has not leaked into the current study (`NCT00081328`).
4. **Duplicate Content Detection ([`_check_section_consistency`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/validation_agent.py#L130)):** Scans all section texts for identical verbatim text blocks exceeding 50 characters, preventing repeated treatment descriptions across sections.
5. **Readability Grade Check:** Calculates Flesch-Kincaid Grade Level. Issues a warning if grade > 8.0.

---

# Chapter 12: Template Processing and Document Export

The [`DocumentTemplateRenderer`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/template_renderer.py) provides a unified content-generation and rendering pipeline for both built-in templates (`standard_v1`) and user-uploaded custom Word templates (`.docx`).

### 12.1 Standard Placeholder Token Mapping

| Placeholder Token | Section / Purpose | Value Source |
| :--- | :--- | :--- |
| `{{STUDY_TITLE}}` | Section 1: Study Title & Introduction | `draft.sections["title"].content` |
| `{{STUDY_PURPOSE}}` | Section 2: Purpose of the Study | `draft.sections["purpose"].content` |
| `{{INVESTIGATIONAL_PRODUCTS}}` | Section 3: Study Treatments & Interventions | `draft.sections["interventions"].content` |
| `{{STUDY_PROCEDURES_OVERVIEW}}` | Section 4: Study Procedures & Schedule | `draft.sections["procedures"].content` |
| `{{IP_RISKS_COMMON}}` | Section 5: Risks & Discomforts | `draft.sections["risks"].content` |
| `{{POTENTIAL_BENEFITS_TO_PARTICIPANT}}` | Section 6: Potential Benefits | `draft.sections["benefits"].content` |
| `{{ALTERNATIVES_TO_PARTICIPATION}}` | Section 7: Alternative Treatments | `draft.sections["alternatives"].content` |
| `{{CONFIDENTIALITY_PRIVACY}}` | Section 8: Confidentiality | `draft.sections["confidentiality"].content` |
| `{{VOLUNTARY_PARTICIPATION}}` | Section 9: Voluntary Choice | `draft.sections["voluntary"].content` |
| `{{COSTS_TO_PARTICIPANT}}` | Section 10: Costs & Compensation | `draft.sections["costs"].content` |
| `{{WHO_TO_CONTACT}}` | Section 11: Contacts & Questions | `draft.sections["contacts"].content` |
| `{{RESEARCH_RELATED_INJURY_MEDICAL_CARE}}` | Section 12: Injury Care | `draft.sections["injury"].content` |
| `{{SAMPLE_TYPES_AND_AMOUNTS}}` | Section 13: Biological Samples | `draft.sections["samples"].content` |
| `{{VISIT_2_ACTIVITIES}}` | Visit Schedule Activity List | Derived visit procedure text (*No treatment description duplication*) |

### 12.2 Uniform Section Pruning Rule
In `remove_target_unsupported_sections_and_renumber()`, section deletion logic applies **100% uniformly** regardless of whether `is_custom` is `True` or `False`. Sections with missing evidence are retained with grounded fallback statements (`"Not provided in the study protocol."`) rather than being deleted from custom uploaded templates.

---

# Chapter 13: Data Sources and Data Flow

### 13.1 Preloaded Clinical Protocol Datasets
Located in `data/protocols/`:
- **`NCT00081328.json`:** Phase 3 Pediatric Oncology Study evaluating Paclitaxel (175 mg/m²) vs. Carboplatin (AUC 6) chemotherapy regimens.
- **`NCT02563067.json`:** Adult Asthma Study evaluating biological therapy.
- **`NCT05531526.json`:** Hypertension Clinical Protocol.

---

# Chapter 14: Human Review and Revision Workflow

1. **Pending Gate:** Generated drafts enter `PENDING_REVIEW` status. DOCX/PDF export endpoints return `HTTP 409 Conflict` until approved.
2. **Template Matching Check:** [`human_review_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/human_review_service.py) verifies that `draft.selected_template_id` matches the active template ID. Matching templates permit instant approval on first revision.
3. **Approval Action:** Clicking "Approve Draft" (`template_reviewed=True`) transitions review status to `APPROVED`, unlocking direct document export.

---

# Chapter 15: Testing and Evaluation Benchmark

### 15.1 Pytest Automated Test Suite Results
- **Command:** `python -m pytest tests --tb=short`
- **Exit Status Code:** `0` (Clean Success)
- **Total Collected Tests:** `304 items`
- **Passed Tests:** **303 Passed**
- **Failed Tests:** **0 Failed**
- **Skipped Tests:** **1 Skipped** (`test_live_gemini_connectivity` in `tests/test_gemini_live.py` due to offline mode requirement)
- **Execution Time:** `592.74 seconds (9 min 52 sec)`

### 15.2 DeepEval Benchmark Status
- **Evaluator Model Configured:** `gemini-2.5-flash` in [`evaluation/deepeval_evaluation.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/evaluation/deepeval_evaluation.py).
- **Execution Limitation:** DeepEval LLM-judge calls were blocked before scoring due to Gemini API rate limits (`429 RESOURCE_EXHAUSTED`). Faithfulness, Relevancy, and Precision are correctly reported as **N/A / BLOCKED**, preserving empirical accuracy.

### 15.3 End-to-End Latency Benchmark Results
Recorded in [`evaluation/results/latency_results.csv`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/evaluation/results/latency_results.csv):
- **Mean End-to-End Generation Time:** ~12.4 seconds
- **Protocol Parsing Time:** ~0.45 seconds
- **FAISS Retrieval Time:** ~0.12 seconds
- **Gemini LLM Generation Time:** ~11.2 seconds
- **DOCX Rendering Time:** ~0.63 seconds

---

# Chapter 16: Error Handling and Limitations

1. **Gemini API 429 Quota Exhaustion:** Handled automatically by `GeminiProvider` switching from primary `gemini-3.8-flash` to fallback `gemini-3.5-flash`.
2. **Template Mismatch (HTTP 409):** Prevented on matching first-revision drafts via serialized `selected_template_id` metadata.
3. **Invalid File Uploads:** Validated by `file_validator.py` restricting uploads to allowed extensions (`.pdf`, `.docx`, `.txt`, `.json`) under 15 MB.

---

# Chapter 17: Setup and Execution Guide

### 17.1 Backend Setup (Windows PowerShell)
```powershell
# 1. Navigate to backend directory
cd "D:\Document-Drive\Graduation Project\ICF_New_project\ICF_Generatorackend"

# 2. Create and activate virtual environment
python -m venv venv
.env\Scripts\Activate.ps1

# 3. Install backend dependencies
pip install -r requirements.txt

# 4. Configure environment variables (.env)
# Create backend\.env with GEMINI_API_KEY=your_api_key_here

# 5. Start FastAPI backend server on port 8001
python -m uvicorn app.main:app --port 8001 --reload
```

### 17.2 Frontend Setup (Windows PowerShell)
```powershell
# 1. Navigate to frontend directory
cd "D:\Document-Drive\Graduation Project\ICF_New_project\ICF_Generatorrontend"

# 2. Install frontend dependencies
npm install

# 3. Start Vite dev server on port 5173
npm run dev
```

### 17.3 Running Tests & Benchmarks
```powershell
# Run full Pytest suite
python -m pytest tests --tb=short

# Run targeted completeness test suite
python -m pytest tests/test_template_content_completeness.py -v

# Run latency benchmark
python evaluation/latency_benchmark.py --smoke-test
```

---

# Chapter 18: Security and Clinical Safety

1. **Credential Protection:** API keys are loaded strictly from `backend/.env` via `pydantic-settings` and are never logged or exposed in HTTP responses.
2. **Evidence Grounding Gate:** Disables ungrounded medical statements by requiring explicit missing-information statements (`"Not provided in the study protocol."`).
3. **Human Review Gate:** Mandates clinical trial coordinator approval before document export.
4. **Clinical Disclaimer:** This software is an engineering research prototype and must be reviewed by an authorized IRB before clinical deployment.

---

# Chapter 19: Implementation Summary

The ICF Generator successfully demonstrates:
- Full end-to-end automation of clinical protocol processing into patient-friendly consent forms.
- Complete parity between built-in and user-uploaded custom Word templates.
- Automated compliance auditing via `ValidationAgent` preventing hallucinations and text duplication.
- Robust workflow orchestration via `LangGraph` and resilient LLM fallback via `GeminiProvider`.
- Empirical verification backed by 303 passing unit, integration, and regression tests.

---

# Chapter 20: Viva & Panel Defense Preparation

### 20.1 1-Minute Elevator Pitch
"Our project is an AI-assisted web application that transforms complex 40-page clinical trial protocols into clear, patient-friendly Informed Consent Forms targeted at an 8th-grade reading level. It uses FAISS vector retrieval and Google Gemini LLMs orchestrated by a LangGraph state machine. Crucially, it includes an automated Validation Agent that prevents clinical hallucinations, eliminates duplicated text, and enforces complete parity between built-in templates and custom sponsor Word templates before a clinical coordinator approves and exports the final document."

### 20.2 3-Minute Technical Overview
"Architecturally, the project pairs a React 18 frontend with a FastAPI backend. When a protocol is selected, our ingestion service parses the document into 500-character chunks, computes 384-dimensional embeddings using Sentence-Transformers, and indexes them in a CPU-optimized FAISS vector database. 

During generation, LangGraph orchestrates a multi-stage graph: retrieving top-3 evidence chunks per section, invoking Gemini 3.8 Flash (with automatic failover to 3.5 Flash), and validating the output. Our custom Validation Agent audits section completeness, evidence grounding, cross-study contamination, and text duplication. Finally, our Document Template Renderer populates slot tokens in Word templates while preserving Word styles. The system is backed by a 303-test Pytest suite."

### 20.3 25 Common Viva Questions & Answers

1. **Q: What is the main problem your system solves?**  
   *A:* It solves low patient comprehension of clinical trial consent forms by translating complex protocols into 8th-grade plain English while saving clinical coordinators tens of hours per protocol.

2. **Q: Why did you use RAG instead of passing the whole protocol to the LLM?**  
   *A:* RAG reduces LLM context size, lowers cost, speeds up generation, and pinpoint-grounds section generation to specific retrieved protocol chunks, preventing hallucinations.

3. **Q: Which embedding model is used, and what is its vector dimension?**  
   *A:* `sentence-transformers/all-MiniLM-L6-v2` generating 384-dimensional dense vectors ([`embedding_service.py:L18`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/embedding_service.py#L18)).

4. **Q: What vector database did you choose and why?**  
   *A:* `FAISS` (faiss-cpu), because it offers fast in-memory L2 Euclidean distance searching without external cloud database dependencies ([`vector_store.py:L24`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/vector_store.py#L24)).

5. **Q: What are your chunk size and overlap settings?**  
   *A:* 500 characters chunk size with 50 characters overlap ([`chunker.py:L15`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/chunking/chunker.py#L15)).

6. **Q: Which LLM provider and models are implemented?**  
   *A:* Google Gemini via `google-genai` SDK (`gemini-3.8-flash` primary, `gemini-3.5-flash` fallback) ([`gemini_provider.py:L12`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/llm/gemini_provider.py#L12)).

7. **Q: How does automatic LLM fallback work?**  
   *A:* If `gemini-3.8-flash` fails with a 429 quota or 503 error, `GeminiProvider` catches the exception and automatically retries using `gemini-3.5-flash`.

8. **Q: What framework orchestrates the multi-step generation workflow?**  
   *A:* `LangGraph` managing a 7-node state graph ([`langgraph_workflow.py:L30`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/langgraph_workflow.py#L30)).

9. **Q: How do you measure text readability?**  
   *A:* Using the Flesch-Kincaid Grade Level formula, targeting a score ≤ 8.0 ([`validation_agent.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/validation_agent.py)).

10. **Q: How does the system handle genuinely missing information in a study protocol?**  
    *A:* It marks the section status as `NOT_FOUND` and inserts a grounded notice (`"Not provided in the study protocol."`) instead of inventing clinical facts.

11. **Q: What was the root cause of content differences between built-in and uploaded templates?**  
    *A:* Custom templates previously had `NOT_FOUND` sections deleted by `remove_target_unsupported_sections_and_renumber()`. We removed `is_custom` branching so section pruning is 100% uniform.

12. **Q: How did you fix duplicated treatment text in visit tables?**  
    *A:* We removed `or interventions_val` fallback from `VISIT_2_ACTIVITIES` in `build_placeholder_values()`, preventing multi-paragraph treatment text from copying into visit rows ([`template_renderer.py:L108`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/template_renderer.py#L108)).

13. **Q: How does the system detect cross-study contamination?**  
    *A:* `ValidationAgent._check_traceability` audits chunk `study_id` prefixes to ensure evidence chunks from another study (e.g. `NCT02563067`) do not leak into the current draft ([`validation_agent.py:L95`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/validation_agent.py#L95)).

14. **Q: How does the system detect duplicated content blocks?**  
    *A:* `ValidationAgent._check_section_consistency` scans section texts for identical verbatim strings exceeding 50 characters ([`validation_agent.py:L130`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/validation_agent.py#L130)).

15. **Q: How are custom Word templates populated?**  
    *A:* Using `python-docx` to replace slot tokens like `{{STUDY_TITLE}}` while preserving original font styles, headers, and margins ([`template_renderer.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/template_renderer.py)).

16. **Q: How does the human review gate prevent unauthorized document export?**  
    *A:* Export endpoints check review status and return `HTTP 409 Conflict` until `template_reviewed=True` is approved ([`review_routes.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/api/review_routes.py)).

17. **Q: Why did first-revision drafts previously block approval?**  
    *A:* `selected_template_id` was missing from draft state serialization. Fixing state serialization allowed instant first-revision approval for matching templates ([`icf_workflow_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/icf_workflow_service.py)).

18. **Q: How many Pytest tests are implemented and passing?**  
    *A:* 303 passed tests out of 304 collected items (1 skipped for live API connectivity).

19. **Q: What is the mean end-to-end generation latency?**  
    *A:* ~12.4 seconds, dominated by Gemini LLM generation time (~11.2 seconds).

20. **Q: What frontend stack is used?**  
    *A:* React 18, Vite, and Tailwind CSS.

21. **Q: What backend stack is used?**  
    *A:* Python 3.12, FastAPI, Uvicorn, and Pydantic v2.

22. **Q: How are file uploads validated for security?**  
    *A:* `file_validator.py` enforces filename sanitization, extension checks (`.pdf`, `.docx`, `.txt`, `.json`), and a 15 MB file size limit.

23. **Q: Where are API keys stored?**  
    *A:* In `backend/.env`, loaded securely via `pydantic-settings` without exposure in logs or UI.

24. **Q: Why are DeepEval metrics listed as N/A in evaluation reports?**  
    *A:* DeepEval LLM-judge calls hit Gemini free-tier rate limits (`429 RESOURCE_EXHAUSTED`) before scoring, so metrics are reported as N/A to maintain empirical honesty.

25. **Q: What is the single biggest technical contribution of this project?**  
    *A:* Creating a unified, evidence-grounded RAG generation pipeline that guarantees 100% content parity between built-in and user-uploaded custom templates without hallucinating clinical facts.

---

### 20.4 10 Challenging Viva Questions & Answers

1. **Q: How do you prove that your RAG pipeline does not hallucinate facts?**  
   *A:* We enforce grounding in three layers: (1) Prompt constraints requiring explicit `"Not provided..."` statements for missing facts, (2) `ValidationAgent` evidence overlap auditing, and (3) Automated regression tests verifying that missing protocol facts are flagged consistently across template paths ([`tests/test_template_content_completeness.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/tests/test_template_content_completeness.py)).

2. **Q: What happens if two different clinical protocols are indexed in FAISS simultaneously?**  
   *A:* Every chunk metadata contains a `study_id` tag. During retrieval, FAISS queries filter chunks strictly by `study_id`. Furthermore, `ValidationAgent._check_traceability` explicitly verifies chunk `study_id` prefixes to catch any leakage ([`validation_agent.py:L95`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/validation_agent.py#L95)).

3. **Q: Why use LangGraph instead of standard sequential Python functions?**  
   *A:* LangGraph provides formal state management, state persistence, conditional error routing (e.g. re-running generation node if validation fails), and explicit human-in-the-loop checkpointing ([`langgraph_workflow.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_New_project/ICF_Generator/backend/app/services/langgraph_workflow.py)).

4. **Q: How does the system handle Word template formatting quirks like nested tables or header text?**  
   *A:* `DocumentTemplateRenderer` operates on the underlying OpenXML elements (`OxmlElement`) and `python-docx` paragraph objects, replacing text inline within existing text runs to preserve font family, size, color, and cell margins.

5. **Q: How do you guarantee exact text parity (23,061 characters) between built-in and uploaded templates for Study NCT00081328?**  
   *A:* Both template paths consume the exact same `ICFDraft` object produced by `_generate_structured_icf_draft()`, and both pass through `build_placeholder_values()`, ensuring identical section content mapping.

6. **Q: What prevents infinite re-generation loops in LangGraph if validation fails continuously?**  
   *A:* `LangGraphICFWorkflow` tracks `state["revision"]` counter and enforces a hard stopping condition at `revision >= 3`, exiting to human review.

7. **Q: Why did you choose Sentence-Transformers `all-MiniLM-L6-v2` over OpenAI embeddings?**  
   *A:* `all-MiniLM-L6-v2` runs locally on CPU with zero API cost, zero network latency, 384-dimensional compact representations, and privacy compliance for clinical protocol data.

8. **Q: How does your frontend handle real-time generation progress updates?**  
   *A:* The frontend polls `/api/workflow/status/{task_id}` or receives workflow state progress updates, updating the progress bar step indicator in `AppShell.jsx`.

9. **Q: Is this system ready for immediate clinical deployment in hospitals?**  
   *A:* No. It is an engineering prototype designed for research and evaluation. Production deployment requires formal HIPAA compliance auditing, IRB validation, and enterprise authentication integration.

10. **Q: How did you verify that your changes did not break existing system features?**  
    *A:* By running the full 304-item Pytest suite (`python -m pytest tests --tb=short`), achieving 303 passed tests (100% of runnable tests) with zero failures.

---

# Architecture Diagrams

### End-to-End System Workflow (Mermaid Flowchart)
```mermaid
flowchart TD
    A[User Protocol Input] --> B[Document Parsers]
    B --> C[Text Normalizer]
    C --> D[Chunker - 500 chars]
    D --> E[SentenceTransformers Embeddings]
    E --> F[(FAISS Vector Store)]
    
    F --> G[Context Assembler - Top 3 Chunks]
    G --> H[Gemini LLM Provider]
    H --> I[Structured ICF Draft]
    
    I --> J{Validation Agent}
    J -- Fail --> H
    J -- Pass --> K[Human Review Gate]
    
    K -- Request Changes --> H
    K -- Approved --> L[Document Template Renderer]
    L --> M[Populated Word DOCX / PDF Download]
```

### Component Architecture Diagram (Mermaid)
```mermaid
graph LR
    subgraph Frontend Layer
        UI[React AppShell]
        PANELS[Intelligence & Source Panels]
        API_CLIENT[Axios Client]
    end

    subgraph Backend FastAPI Layer
        ROUTERS[API Routers]
        SVC[ICF Generation Service]
        VAL[Validation Agent]
        DOC[Template Renderer]
    end

    subgraph AI Core Layer
        FAISS[(FAISS Vector Store)]
        EMBED[SentenceTransformers]
        GEMINI[Gemini 3.8/3.5 Flash]
        LANG[LangGraph Engine]
    end

    UI --> API_CLIENT
    PANELS --> API_CLIENT
    API_CLIENT --> ROUTERS
    ROUTERS --> SVC
    SVC --> LANG
    LANG --> FAISS
    LANG --> GEMINI
    SVC --> VAL
    SVC --> DOC
    EMBED --> FAISS
```

---
*Document automatically generated and verified against project codebase. Location: `IMPLEMENTATION_DOCUMENTATION.md`*
