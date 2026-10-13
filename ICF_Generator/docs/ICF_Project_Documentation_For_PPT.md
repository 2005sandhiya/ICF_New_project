# AI-Assisted Informed Consent Form (ICF) Generator
## Comprehensive Project Documentation & Technical Report for Final Presentation and Viva

---

## 1. Project Overview

### 1.1 Project Title
**AI-Assisted Informed Consent Form (ICF) Generator**

### 1.2 Project Objective
The primary objective of this project is to develop an end-to-end, AI-assisted software system that automates the extraction of structured clinical-trial protocol data, retrieves grounded evidence using Retrieval-Augmented Generation (RAG), generates both standard and patient-friendly Informed Consent Form (ICF) drafts, performs multi-dimensional compliance and safety validation, supports version-controlled human review and targeted revisions (`v1` $\rightarrow$ `v2`), and exports approved consent documents as formatted Word (`.docx`) or PDF files.

### 1.3 Problem Statement
Informed Consent Forms (ICFs) are ethically mandatory and legally regulated documents that inform clinical trial participants about study procedures, potential risks, benefits, and their rights. However, traditional manual ICF drafting faces critical bottlenecks:
1. **High Complexity & Technical Jargon:** Clinical protocols are highly technical, lengthy documents (often 50–150+ pages). Translating them into plain language accessible to non-expert patients is difficult and error-prone.
2. **Human Error & Critical Omissions:** Manual copy-pasting from protocol documents frequently leads to omitted eligibility rules, visit schedules, or drug side-effects.
3. **Hallucination Risk in Generic AI:** Unconstrained Large Language Models (LLMs) can invent non-existent hospital phone numbers, false compensation claims, or ungrounded medical guarantees.
4. **Version Control & Revision Friction:** Incorporating clinical reviewer feedback and maintaining auditability across multiple document revisions requires substantial manual effort.

### 1.4 Proposed Solution
The **AI-Assisted ICF Generator** addresses these challenges by introducing a grounded, transparent, human-in-the-loop workflow:
* **Structured Protocol Canonicalization:** Converts heterogeneous clinical protocols (`.pdf`, `.docx`, `.txt`, `.json`) into standardized representations (`CanonicalProtocol` and `ProtocolFacts`).
* **Section-Aware RAG with Chunk Traceability:** Uses dense vector embeddings (`sentence-transformers/all-MiniLM-L6-v2`) and local FAISS vector indexing to retrieve relevant protocol sections. Every extracted fact retains explicit chunk IDs (`source_evidence_ids`).
* **Dual ICF Generation:** Produces a 13-section standard baseline ICF and a patient-friendly plain-language simplification.
* **Automated Compliance Validation Agent:** Evaluates drafts across 6 dimensions (Groundedness, Fact Completeness, NOT_FOUND Integrity, Readability, Traceability, and Section Parity), scoring compliance from 0 to 100%.
* **Human-in-the-Loop Review Workspace:** Allows clinical reviewers to inspect validation results, approve drafts, or request changes with targeted feedback that drives version-controlled regeneration (`v1` $\rightarrow$ `v2`).
* **Custom Template & Multi-Format Export:** Populates either the built-in default layout or a user-uploaded custom DOCX template, with server-side PDF conversion powered by headless LibreOffice.

### 1.5 Intended Users & Business Use Cases
* **Clinical Research Coordinators (CRCs):** Rapidly generate initial consent drafts from new protocols.
* **Principal Investigators (PIs) & Medical Writers:** Review drafts alongside source evidence citations and refine document wording.
* **Institutional Review Boards (IRBs) & Ethics Committees:** Perform pre-review compliance audits using the automated validation scoring report.
* **Clinical Trial Sponsors & CROs:** Standardize consent form formats across multi-center global clinical trials using custom institutional DOCX templates.

---

## 2. Existing System vs. Proposed System

| Dimension | Existing / Manual Approach | Proposed AI-Assisted System |
|---|---|---|
| **Drafting Speed** | Days to weeks of manual typing and copy-pasting from protocol PDFs | Automated protocol parsing and initial dual-draft generation in under 1 minute |
| **Language Simplification** | Manual rewriting to plain English; inconsistent reading levels | Automated health-literacy transformation targeting patient-friendly readability |
| **Evidence Grounding** | Manual reference checking across multi-page protocol documents | Strict RAG context retrieval; every section cites specific protocol chunk IDs |
| **Hallucination Protection** | Vulnerable to generic LLM memory leakage or ungrounded assertions | Strict `NOT_FOUND` fallback engine and automated hallucination pattern auditor |
| **Validation & Audit** | Manual checklist reviews subject to fatigue and human oversight | Multi-dimensional Validation Agent providing a 0–100% compliance audit score |
| **Version Control** | Manual filename tracking (`ICF_v1_draft_final_v2.docx`) | Automated state machine handling `v1` $\rightarrow$ `v2` revisions linked to reviewer comments |
| **Template Customization** | Re-formatting documents manually for different hospital/IRB templates | Automated placeholder and heading mapping for uploaded custom `.docx` templates |
| **Document Export** | Manual formatting in Microsoft Word | Server-side verified PDF rendering via LibreOffice with approval checks |

---

## 3. Complete System Architecture

### 3.1 Component Architecture Overview
The system follows a modular microservice-style layout separating the React frontend workspace, the FastAPI backend core, RAG/Embedding services, LLM abstraction layers, validation agent, and document export engines.

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             REACT + VITE FRONTEND                                │
│  ┌───────────────────────────────┐     ┌──────────────────────────────────────┐  │
│  │ Study Selection & Ingestion   │     │ 10-Stage Pathway & Workflow          │  │
│  │ Dashboard                     │     │ Progress Tracker                     │  │
│  └───────────────┬───────────────┘     └──────────────────┬───────────────────┘  │
│                  │                                        │                      │
│  ┌───────────────▼───────────────┐     ┌──────────────────▼───────────────────┐  │
│  │ Human Review & Revisions      │     │ DOCX & PDF Export Workspace          │  │
│  │ Workspace                     │     │                                      │  │
│  └───────────────────────────────┘     └──────────────────────────────────────┘  │
└──────────────────────────────────────────┬───────────────────────────────────────┘
                                           │ HTTP REST / JSON APIs
┌──────────────────────────────────────────▼───────────────────────────────────────┐
│                              FASTAPI BACKEND CORE                                │
│  ┌───────────────────────────────┐     ┌──────────────────────────────────────┐  │
│  │ Protocol Ingestion & Parser   │     │ Canonicalization & Section-Aware     │  │
│  │ (PDF, DOCX, TXT, JSON)        │     │ Chunker Engine                       │  │
│  └───────────────┬───────────────┘     └──────────────────┬───────────────────┘  │
│                  │                                        │                      │
│  ┌───────────────▼───────────────┐     ┌──────────────────▼───────────────────┐  │
│  │ Dense Embedding Service       │     │ FAISS Local Vector Store             │  │
│  │ (all-MiniLM-L6-v2)            │     │ (IndexFlatIP Cosine Similarity)      │  │
│  └───────────────┬───────────────┘     └──────────────────┬───────────────────┘  │
│                  │                                        │                      │
│  ┌───────────────▼───────────────┐     ┌──────────────────▼───────────────────┐  │
│  │ Grounded RAG Context          │     │ Protocol Analysis Agent              │  │
│  │ Assembler                    │     │ (Structured Facts Extractor)         │  │
│  └───────────────┬───────────────┘     └──────────────────┬───────────────────┘  │
│                  │                                        │                      │
│  ┌───────────────▼───────────────┐     ┌──────────────────▼───────────────────┐  │
│  │ Dual ICF Generation Service   │     │ Multi-Dimensional Compliance &      │  │
│  │ (Standard & Patient-Friendly) │     │ Safety Validation Agent              │  │
│  └───────────────┬───────────────┘     └──────────────────┬───────────────────┘  │
│                  │                                        │                      │
│  ┌───────────────▼───────────────┐     ┌──────────────────▼───────────────────┐  │
│  │ Template Renderer Engine      │     │ PDF Export Service (LibreOffice) &   │  │
│  │ (python-docx + Placeholders)  │     │ Revision Approval Gatekeeper         │  │
│  └───────────────────────────────┘     └──────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Inter-Component Communication & Data Flow
1. **Frontend $\rightarrow$ Ingestion API:** The React UI sends study selection (`study_id`) or uploads a protocol document (`POST /api/protocol/upload` or `POST /api/icf/workflow`).
2. **Document Processing $\rightarrow$ Canonicalization:** `DocumentProcessor` parses raw files into `ExtractedTextResponse`, which `CanonicalizationEngine` transforms into a standardized `CanonicalProtocolResponse`.
3. **Chunking $\rightarrow$ FAISS Store:** `Chunker` splits protocol text into overlapping chunks, `EmbeddingService` generates 384-dimensional dense vectors using `sentence-transformers/all-MiniLM-L6-v2`, and `VectorStore` indexes them in local FAISS `IndexFlatIP`.
4. **FAISS Store $\rightarrow$ Context Assembler $\rightarrow$ Analysis Agent:** `ContextAssembler` retrieves relevant evidence chunks by cosine similarity search. `ProtocolAnalysisAgent` extracts structured `ProtocolFacts` with grounded citation tags (`source_evidence_ids`).
5. **Analysis Agent $\rightarrow$ ICF Generation Service:** `ICFGenerationService` builds the standard 13-section draft and patient-friendly simplification, taking into account user preferences (`preferred_length`, `custom_instructions`).
6. **ICF Generation $\rightarrow$ Validation Agent:** `ValidationAgent` audits both drafts against the `ProtocolFacts`, computing scores across 6 checks.
7. **ICF Generation $\rightarrow$ Template Renderer:** `TemplateRenderer` maps section content to default or custom `.docx` template placeholders/headings.
8. **Human Review $\rightarrow$ Revision Gatekeeper $\rightarrow$ PDF Service:** Clinical reviewer inspects drafts and validation scores. If approved, `PDFGenerationService` invokes headless LibreOffice (`soffice.com`) to generate the approved PDF document for export.

---

## 4. End-to-End Workflow

The application supports a seamless 10-step automated workflow, tracked live in the UI via the **Pathway Tracker**:

```text
[1. Study Loaded] ──▶ [2. Protocol Parsed] ──▶ [3. Text Chunking] ──▶ [4. Embedding Gen]
                                                                            │
[8. ICF Gen] ◄── [7. Protocol Analysis] ◄── [6. RAG Retrieval] ◄── [5. FAISS Indexing]
     │
     ▼
[9. Validation Audit] ──▶ [10. Template Rendering & PDF Export]
```

1. **Study / Protocol Selection:** Select a preloaded study (e.g. `NCT00081328`) or upload a protocol file (`.pdf`, `.docx`, `.txt`, `.json`).
2. **Text Parsing & Normalization:** Extract raw text and structural page breakdown (`DocumentProcessor`).
3. **Protocol Canonicalization:** Map protocol fields into standardized schema (`study_id`, `phase`, `title`, `eligibility`, `interventions`, `objectives`, `risks`).
4. **Section-Aware Chunking:** Split protocol content into semantic chunks (default 500 characters, 150 character overlap) and assign unique chunk IDs (e.g., `NCT00081328_eligibility_014`).
5. **Dense Vector Embedding & FAISS Indexing:** Compute 384-dim embeddings via `all-MiniLM-L6-v2` and store in local FAISS vector index.
6. **RAG Context Assembly:** Retrieve top-$k$ relevant chunks for key consent topics via vector cosine similarity.
7. **Structured Protocol Fact Extraction:** Extract traceable clinical facts (`ProtocolFacts`) with grounding statuses (`SUPPORTED`, `NOT_FOUND`, `UNCERTAIN`).
8. **Dual ICF Generation:** Generate both standard 13-section ICF and plain-language patient-friendly version, applying custom instructions or page-length preferences.
9. **Automated Validation Audit:** Execute 6 compliance checks to generate an overall audit score (0–100%) and recommendations.
10. **Human Review & Approved Export:** Present drafts to reviewer. Upon approval, populate the target DOCX template and convert to verified PDF via LibreOffice.

---

## 5. Technology Stack

### 5.1 Actual Technologies Used in the Codebase

| Layer | Framework / Library / Tool | Version | Purpose in Project |
|---|---|---|---|
| **Backend Framework** | FastAPI | 0.110+ | High-performance asynchronous REST API backend |
| **ASGI Web Server** | Uvicorn | 0.28+ | ASGI web server running FastAPI on port 8001 |
| **Data Schema Validation** | Pydantic | v2.6+ | Data validation, settings management, and API serialization |
| **Document Processing** | `python-docx` | 1.1.0+ | Parsing and populating Word (`.docx`) document templates |
| **PDF Parser** | `pypdf` | 4.1.0+ | Parsing PDF protocol text and verifying exported PDF structures |
| **Embedding Model** | `sentence-transformers` | 2.5.1+ | Generating 384-dim dense vectors using `all-MiniLM-L6-v2` |
| **Vector Database** | `faiss-cpu` | 1.8.0+ | In-memory & disk-cached vector similarity indexing (`IndexFlatIP`) |
| **Vector Computations** | `numpy` | 1.26.4+ | Array operations for vector normalization and distance calculations |
| **HTTP Client** | `httpx` | 0.27+ | Async HTTP client for communicating with external LLM APIs |
| **PDF Conversion Tool** | LibreOffice | External CLI | Headless document converter (`soffice.com`) for PDF rendering |
| **Frontend Core** | React | 18.2 | Component-based interactive user interface |
| **Frontend Build Tool** | Vite | 5.1 | Fast frontend dev server and bundle manager |
| **Frontend Styling** | Vanilla CSS | Custom | Custom light-theme design system (Forest Grove, Pine Shadow, Ink Black) |
| **AI LLM API Models** | Google Gemini API | 3.8 / 2.5 Flash | Primary LLM provider for analysis and generation (`gemini-3.8-flash`) |
| **AI LLM Fallback APIs**| Anthropic / OpenAI | Claude / GPT | Optional secondary providers (`claude-3-5-sonnet-20241022`, GPT-4o) |
| **Automated Testing** | Pytest & Node `--test` | Native | Backend unit/integration tests and frontend workflow test scripts |

---

## 6. Data and Protocol Processing

### 6.1 Clinical Study Data Sources & Upload Formats
* **Preloaded Dataset:** 30 clinical trial study protocols sourced from ClinicalTrials.gov stored as structured JSON files in `data/studies/` (e.g., `NCT00081328.json` for a Phase 3 non-small cell lung cancer trial).
* **Supported Upload Formats:** `.pdf`, `.docx`, `.txt`, and `.json`.

### 6.2 Parsing & Validation Pipeline ([`file_validator.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/file_validator.py), [`document_processor.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/document_processing/document_processor.py))
* **File Validation:** Checks file headers, enforces a 50 MB size limit, rejects 0-byte uploads, and verifies readable text.
* **Scanned PDF Safeguard:** Scanned or image-only PDFs without text return `status="no_extractable_text"` without crashing the server.

### 6.3 Canonicalization Engine ([`canonicalization_engine.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/canonicalization/canonicalization_engine.py))
Normalizes multi-format input into a single internal schema (`CanonicalProtocol`):
* `study_id`, `title`, `phase`, `sponsor`, `condition`
* `eligibility_criteria` (inclusion/exclusion criteria breakdown)
* `objectives` & `outcomes` (primary and secondary endpoints)
* `interventions` (investigational drugs, dosages, arm details)
* `risks_and_side_effects` (known adverse events and severity)

### 6.4 Section-Aware Chunking ([`chunker.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/chunking/chunker.py))
* Splits protocol text into discrete chunks (default target length: 500 characters, overlap: 150 characters).
* Attaches persistent chunk metadata: `chunk_id` (e.g. `NCT00081328_eligibility_014`), `section_name`, `page_number`, and `source_document`.

### 6.5 Dense Embeddings & FAISS Vector Indexing ([`embedding_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/embedding_service.py), [`vector_store.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/vector_store.py))
* Uses local model `sentence-transformers/all-MiniLM-L6-v2` producing 384-dimensional dense vectors.
* Employs FAISS `IndexFlatIP` (Inner Product) with L2 vector normalization for exact cosine similarity search.
* Persists indexed vector indices locally under `data/vector_store/index.faiss`.

---

## 7. RAG and AI Generation

### 7.1 Retrieval Pipeline ([`context_assembler.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/context_assembler.py))
Given a targeted consent query (e.g., *"What are the risks and side effects of the investigational drug?"*):
1. Generates 384-dim query vector using `EmbeddingService`.
2. Queries FAISS vector index for top-$k$ nearest neighbor chunks ($k=5$ by default).
3. Applies a minimum similarity score threshold (default $0.3$).
4. Packages matching chunks into a structured `RAGContextResponse` containing full chunk texts and their associated `source_evidence_ids`.

### 7.2 LLM Integration & Provider Architecture ([`llm_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/llm/llm_service.py))
The backend features an extensible provider abstraction:
* **Google Gemini Provider ([`gemini_provider.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/llm/gemini_provider.py)):** Configured as primary (`gemini-3.8-flash`) with fallback to `gemini-2.5-flash`.
* **Anthropic Provider ([`anthropic_provider.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/llm/anthropic_provider.py)):** Integrates Claude 3.5 Sonnet (`claude-3-5-sonnet-20241022`).
* **OpenAI Provider ([`openai_provider.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/llm/openai_provider.py)):** Integrates OpenAI models.
* **Deterministic Grounded Fallback Engine:** If no API key is set or external APIs are unreachable, the system automatically uses its local deterministic extraction engine, ensuring full functionality without external cloud dependencies.

### 7.3 Grounded Evidence Generation & `NOT_FOUND` Safeguard ([`icf_generation_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/icf_generation_service.py))
* Standard ICF drafts comprise 13 mandatory sections:
  1. Title & Study Information
  2. Purpose of the Study
  3. Why You Are Invited
  4. Study Procedures & Visit Schedule
  5. Study Duration
  6. Interventions & Investigational Drugs
  7. Potential Risks & Discomforts
  8. Potential Direct & Indirect Benefits
  9. Alternative Treatments
  10. Voluntary Participation & Withdrawal
  11. Confidentiality of Records
  12. Questions & Contact Information
  13. Signatures & Consent Agreement
* **Grounding Rule:** Every generated section references specific `source_evidence_ids`.
* **`NOT_FOUND` Integrity Safeguard:** If a protocol lacks required information (e.g., missing specific compensation details or 24/7 emergency contacts), the system strictly outputs:
  > *"Not provided in the study protocol."*
  with `status=NOT_FOUND` and empty evidence IDs `[]`. The system never invents phone numbers, compensation sums, or medical guarantees.

---

## 8. ICF Generation Features

### 8.1 Production Default Template vs. Custom DOCX Templates
* **Default Production Layout:** Built-in 13-section formatted Word document structure generated via `python-docx` in `docx_generation_service.py`.
* **Custom DOCX Templates ([`template_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/template_service.py)):** Users can upload institution-specific `.docx` files (up to 10 MB). Stored per study under `data/templates/custom/<hash-of-study-id>/`.

### 8.2 Template Placeholder & Heading Mapping ([`template_renderer.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/template_renderer.py))
The template engine populates custom Word documents via two mechanisms:
1. **Explicit Placeholders:** E.g., `{{icf.purpose}}`, `{{icf.procedures}}`, `{{icf.risks}}`, `{{icf.benefits}}`, `{{study_id}}`, `{{revision}}`. Handles placeholders split across multiple OpenXML Word runs.
2. **Standard Section Heading Matching:** Exact matching against common consent headings (e.g., *"Purpose of the Study"*, *"Risks and Discomforts"*). Body text following a matched heading is populated with generated content while preserving paragraph fonts and table structures.
3. **Unmapped Retained Template Text:** Retained template boilerplate is preserved as *"unverified template wording"* and highlighted for explicit human review.

### 8.3 Generation Preferences
The API (`ICFGenerationRequest`) accepts user-defined preferences:
* `preferred_length`: Preferred page range (e.g., `"4–6 pages"`, `"6–8 pages"`).
* `custom_instructions`: Formatting or tone guidelines (e.g., *"Use bullet points for visit schedules"*).

### 8.4 Handling Unmapped Protocol Topics
Protocol topics not mapped to specific template placeholders are automatically appended under an **"Additional required consent sections"** heading at the document end to prevent clinical omissions.

### 8.5 Human Review Loop & Revision Control ([`human_review_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/human_review_service.py))
* **Review States:** `PENDING`, `APPROVED`, `CHANGES_REQUESTED`.
* **Targeted Regeneration (`v1` $\rightarrow$ `v2`):** When a reviewer submits feedback with `CHANGES_REQUESTED`, the service increments the revision number, regenerates content addressing the feedback, reruns validation, and resets review state to `PENDING`.
* **Revision-Bound Export Gatekeeper:** Exporting DOCX or PDF requires an explicit `APPROVED` status matching the current study, revision version, template ID, and content hash.

---

## 9. Validation and Safety

### 9.1 Implemented Multi-Dimensional Validation Checks ([`validation_agent.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/validation_agent.py))
The Validation Agent executes 6 automated auditing checks, producing an overall compliance score (0–100%):

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         MULTI-DIMENSIONAL VALIDATION AGENT                       │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 1. Groundedness & Hallucination Check (25% Weight): Regex & pattern scan for     │
│    invented 1-800/555 numbers, ungrounded $ amounts, or cure guarantees.          │
│ 2. Fact Completeness & Coverage Check (25% Weight): Verifies presence of core    │
│    facts (title, phase, eligibility, interventions, duration).                   │
│ 3. NOT_FOUND Integrity Check (15% Weight): Asserts NOT_FOUND sections strictly   │
│    use boilerplate text with empty evidence IDs.                                 │
│ 4. Source Evidence Traceability Check (15% Weight): Verifies SUPPORTED sections  │
│    maintain non-empty source_evidence_ids.                                       │
│ 5. Readability & Health Literacy Check (10% Weight): Assesses plain-language     │
│    readability for patient-friendly drafts.                                      │
│ 6. Section Parity Check (10% Weight): Verifies section alignment between         │
│    standard and patient-friendly drafts.                                         │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 What Validation Does vs. Does Not Guarantee
* **What Validation Guarantees:**
  * Zero hallucinated contact numbers or fake compensation claims.
  * 100% traceability of supported facts back to protocol chunk IDs.
  * Enforcement of explicit `NOT_FOUND` placeholders when evidence is absent.
  * Correct template placeholder substitution and section completeness.
* **What Validation Does NOT Guarantee:**
  * Absolute clinical or medical accuracy (requires qualified human investigator oversight).
  * Legal enforceability or IRB regulatory approval.
  * Perfect visual rendering across all third-party Word processors.

### 9.3 Why Human Review is Mandatory
Automated AI validation is a compliance aid, not a replacement for medical professionals. A qualified clinical investigator or IRB reviewer must review and approve every consent form before participant distribution to ensure patient safety and ethical compliance.

---

## 10. Testing Status

### 10.1 Verified Automated Test Counts
* **Backend Pytest Suite:** **196 passing tests** across 35 test files (`pytest tests/`).
* **Frontend Test Suite:** **32 passing tests** (23 workflow tests in `workflow.test.mjs` + 9 template/export tests in `template-export.test.mjs`).

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              VERIFIED TEST SUITE SUMMARY                         │
├──────────────────────────────────────┬───────────────────────────────────────────┤
│ Test Suite Category                  │ Passing Test Count / Status               │
├──────────────────────────────────────┼───────────────────────────────────────────┤
│ Backend Pytest Suite                 │ 196 Passed (0 Failed, 0 Skipped)          │
│ Frontend Workflow Tests              │ 23 Passed                                 │
│ Frontend Template & Export Tests     │ 9 Passed                                  │
│ Live Gemini API Integration Test     │ Verified (`tests/test_gemini_live.py`)    │
│ LibreOffice PDF Conversion Suite     │ Verified (`test_template_pdf_workflow.py`)│
└──────────────────────────────────────┴───────────────────────────────────────────┘
```

### 10.2 Test Suite Categorization
1. **Unit Tests:** Tested individual modules including LLM providers (`test_gemini_provider.py`), chunker, file validator, template renderer (`test_template_rendering.py`), and validation agent (`test_phase5_part4.py`).
2. **Integration Tests:** Tested protocol-to-consent pipeline (`test_icf_workflow.py`), custom template mapping (`test_custom_template_placeholders.py`), and headless LibreOffice PDF conversion (`test_template_pdf_workflow.py`).
3. **Frontend Regression Tests:** Verified state transitions, source switching, error handling, review comments, and approval export blocks (`workflow.test.mjs`, `template-export.test.mjs`).

### 10.3 Pending Testing Activities
* Large-scale benchmark testing across 500+ heterogeneous multi-center protocols.
* User study and usability evaluation with IRB members and clinical research coordinators.
* Multi-worker concurrent load testing (current system is single-worker in-memory).
* OCR evaluation on scanned or handwritten PDF documents.

---

## 11. Evaluation Plan

To evaluate the system rigorously in future studies, the following measurable evaluation metrics and methodologies are established:

| Evaluation Metric | Target Objective | Proposed Evaluation Methodology |
|---|---|---|
| **Fact Extraction Accuracy** | $\ge 95\%$ | Compare extracted `ProtocolFacts` against expert-annotated gold-standard protocol facts. |
| **Retrieval Relevance (RAG)** | MRR $\ge 0.85$, Precision@5 $\ge 0.80$ | Measure Mean Reciprocal Rank of retrieved chunks for standard consent queries. |
| **Grounding / Faithfulness** | $100\%$ grounded claims | RAGAS / ROUGE score comparison between generated text and retrieved protocol chunks. |
| **Hallucination Rate** | $0\%$ ungrounded claims | Automated scan for fake contact numbers, $ amounts, or medical cure guarantees. |
| **Readability Score** | Grade 6–8 level | Flesch-Kincaid Grade Level assessment on patient-friendly drafts. |
| **Template Preservation** | $100\%$ style retention | Structural DOM / OpenXML diff comparing template formatting before and after rendering. |
| **End-to-End Latency** | $< 45$ seconds | Benchmark execution time from protocol upload to final PDF generation. |
| **Reviewer Efficiency** | $\ge 60\%$ time saved | Measure time required for CRCs to produce an IRB-ready draft using AI vs. manually. |

---

## 12. Current Limitations and Future Improvements

### 12.1 Current System Limitations
1. **In-Memory Store Persistence:** ICF drafts, workflow job statuses, and human review states reside in backend memory (FastAPI process memory) and reset when the backend restarts. (Custom templates persist on disk under `data/templates/custom/`).
2. **Absence of OCR Engine:** Scanned or image-only PDFs return `status="no_extractable_text"` as OCR (e.g., Tesseract) is not integrated.
3. **Page-Length Feasibility Notification:** While `preferred_length` (e.g. `"4–6 pages"`) is incorporated into LLM generation prompts, dynamic page-budget estimation and hard page-limit truncation warnings prior to rendering are partially implemented / prompt-guided.
4. **Single-Worker Execution:** Process-local locks and in-memory stores require running a single Uvicorn worker process.
5. **Unauthenticated Local Workflow:** Human review approval restrictions are workflow-enforced rather than identity-authenticated (no multi-role JWT login).

### 12.2 Future Enhancements
1. **Database Persistence:** Integrate PostgreSQL / SQLite with SQLAlchemy for persistent study records, revision histories, and audit logs.
2. **OCR Integration:** Incorporate Tesseract OCR or AWS Textract to parse scanned protocol PDFs.
3. **Dynamic Page-Budget Engine:** Implement exact character-to-page rendering calculations with proactive visual warnings if requested page ranges are unrealistically tight.
4. **Role-Based Access Control (RBAC):** Implement authenticated user roles (Investigator, IRB Reviewer, Admin) with digital signatures.
5. **Biomedical LLM Fine-Tuning:** Fine-tune open-weight medical LLMs (e.g., BioMistral, Llama-3-Med) for offline clinical document processing.

---

## 13. Demonstration Guide for Presentation

### 13.1 Live Demonstration Sequence for Viva Panel
1. **Startup Verification:**
   * Terminal 1 (Backend): `python -m uvicorn app.main:app --port 8001`
   * Terminal 2 (Frontend): `npm run dev` (Open `http://localhost:5173`)
2. **Milestone 1: Study Ingestion & Processing:**
   * Select preloaded study `NCT00081328` (Phase 3 Lung Cancer Trial) or upload a protocol file (`.pdf` / `.json`).
   * Show extracted protocol text and structured `CanonicalProtocol` fields.
3. **Milestone 2: Vector Search & RAG Retrieval:**
   * View FAISS vector store status (384-dim embeddings indexed).
   * Execute a semantic search query (e.g., *"What are the eligibility criteria and risks?"*). Show retrieved chunks with similarity scores and `source_evidence_ids`.
4. **Milestone 3: Protocol Fact Extraction:**
   * Show extracted `ProtocolFacts` table with grounding statuses (`SUPPORTED` vs. `NOT_FOUND`).
5. **Milestone 4: ICF Generation & Preferences:**
   * Navigate to **Generate ICF**. Set preferences (`preferred_length`: `"6–8 pages"`, custom instructions).
   * Click **Generate informed consent form**. Highlight the **10-Stage Pathway Tracker** updating live.
6. **Milestone 5: Dual Draft Preview & Validation Audit:**
   * Compare standard 13-section draft alongside simplified patient-friendly draft. Show citation tags (`[NCT00081328_eligibility_014]`).
   * Open **Validation Report** tab. Show overall score (e.g., $95/100$), Groundedness score, and Completeness check.
7. **Milestone 6: Human Review & Targeted Regeneration (`v1` $\rightarrow$ `v2`):**
   * Go to **Human Review**. Enter reviewer feedback (e.g., *"Include 24/7 emergency contact line for Dr. Smith"*).
   * Click **Request changes & regenerate**. Point out how revision increments (`v1` $\rightarrow$ `v2`) and review state resets to `PENDING`.
8. **Milestone 7: Approval & Server-Side PDF Export:**
   * Select **Approve revision**. Navigate to **Export Documents**.
   * Download PDF. Open exported PDF to demonstrate LibreOffice rendering, document metadata header, signature blocks, and exact section formatting.

### 13.2 Recommended Screenshots for Presentation Slides
1. **Slide 1 (Architecture):** React UI AppShell showing the 10-Stage Pathway Tracker.
2. **Slide 2 (Ingestion & RAG):** FAISS Vector Store Search results showing retrieved chunk evidence with similarity scores.
3. **Slide 3 (Structured Analysis):** `ProtocolFacts` extracted table with `source_evidence_ids`.
4. **Slide 4 (Generation & Preferences):** Dual-draft preview (Standard 13-Section vs. Patient-Friendly simplification).
5. **Slide 5 (Validation):** Multi-Dimensional Validation Agent audit dashboard with compliance scores.
6. **Slide 6 (Review & Export):** Human Review Workspace showing revision history (`v1` vs. `v2`) and final exported PDF document.

---

## 14. Panel Viva Preparation (Q&A)

### Q1: Why use RAG instead of directly feeding the full protocol PDF to Gemini or Claude?
> **Answer:** Full clinical protocols can be 100+ pages long, exceeding context limits and incurring high latency and cost. Feeding raw text without RAG increases hallucination risks. RAG breaks the protocol into semantic chunks, indexes them in FAISS, and retrieves only the top-$k$ relevant chunks for each section. Most importantly, RAG enables chunk-level traceability (`source_evidence_ids`), allowing clinicians to verify every generated sentence against its exact protocol origin.

### Q2: How does your system prevent LLM hallucinations in clinical consent forms?
> **Answer:** We enforce strict grounding rules at three levels:
> 1. **Prompt Constraints:** The LLM is instructed to use only retrieved RAG context.
> 2. **`NOT_FOUND` Integrity Safeguard:** If a protocol lacks specific details (e.g., missing phone numbers or compensation details), the system strictly outputs *"Not provided in the study protocol."* with empty evidence IDs.
> 3. **Validation Agent Checks:** Our Validation Agent scans generated text using regex patterns for fake 1-800 numbers, 555 numbers, ungrounded dollar amounts, or false medical cure guarantees.

### Q3: What embedding model and vector database are used, and why?
> **Answer:** We use `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional dense vectors) and local FAISS (`IndexFlatIP` with L2 normalization for exact cosine similarity). This combination runs entirely locally, requires zero cloud database fees, provides millisecond search latency, and ensures sensitive protocol data remains on the local machine.

### Q4: How does custom template rendering work without breaking Microsoft Word formatting?
> **Answer:** We use `python-docx` to manipulate the underlying OpenXML structure. The renderer searches for explicit placeholders (e.g., `{{icf.purpose}}`) across Word runs or matches standard section headings (e.g., *"Purpose of the Study"*). Generated text is inserted into existing paragraphs and table cells while preserving original font styles, margins, headers, and footers. Any unmapped template wording is retained as *"unverified template wording"* for human review.

### Q5: How is PDF conversion implemented, and why is LibreOffice used?
> **Answer:** PDF is the required non-editable format for clinical consent distribution. We use local headless LibreOffice (`soffice.com`) via background subprocess calls with isolated temporary profiles and 120-second timeouts. After conversion, the backend parses the PDF using `pypdf` to verify page count, metadata, study ID, revision version, and section text completeness before delivering it to the user.

### Q6: What happens when a clinical reviewer requests changes?
> **Answer:** The system records the reviewer's feedback, increments the document revision (`v1` $\rightarrow$ `v2`), triggers targeted regeneration incorporating the feedback, reruns validation, and automatically resets the review state to `PENDING`. Document export remains strictly blocked by backend guards until the reviewer explicitly approves the new revision.

---

## 15. Summary of Inspected Files

* **Backend API & Routes:** [`backend/app/main.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/main.py), [`workflow_routes.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/api/workflow_routes.py), [`icf_routes.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/api/icf_routes.py), [`protocol_routes.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/api/protocol_routes.py), [`review_routes.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/api/review_routes.py), [`template_routes.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/api/template_routes.py), [`validation_routes.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/api/validation_routes.py)
* **Core Backend Services:** [`icf_generation_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/icf_generation_service.py), [`validation_agent.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/validation_agent.py), [`template_renderer.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/template_renderer.py), [`docx_generation_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/docx_generation_service.py), [`pdf_generation_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/pdf_generation_service.py), [`human_review_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/human_review_service.py), [`vector_store.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/vector_store.py), [`embedding_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/embedding_service.py), [`context_assembler.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/context_assembler.py), [`protocol_analysis_agent.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/protocol_analysis_agent.py), [`chunker.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/chunking/chunker.py), [`canonicalization_engine.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/canonicalization/canonicalization_engine.py), [`llm_service.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/llm/llm_service.py), [`gemini_provider.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/backend/app/services/llm/gemini_provider.py)
* **Frontend Modules:** [`frontend/src/App.jsx`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/frontend/src/App.jsx), [`AppShell.jsx`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/frontend/src/components/AppShell.jsx), [`IntelligencePanels.jsx`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/frontend/src/components/IntelligencePanels.jsx), [`SourcePanels.jsx`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/frontend/src/components/SourcePanels.jsx), [`TemplatePanel.jsx`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/frontend/src/components/TemplatePanel.jsx), [`workflow.js`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/frontend/src/components/workflow.js), [`client.js`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/frontend/src/api/client.js)
* **Documentation & Reports:** [`README.md`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/README.md), [`Implementation-report.md`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/Implementation-report.md), [`docs/ARCHITECTURE.md`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/docs/ARCHITECTURE.md), [`docs/TEMPLATE_PDF_WORKFLOW.md`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/docs/TEMPLATE_PDF_WORKFLOW.md), [`docs/TEMPLATE_PDF_IMPLEMENTATION_REPORT.md`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/docs/TEMPLATE_PDF_IMPLEMENTATION_REPORT.md)
* **Automated Test Suites:** [`tests/test_icf_workflow.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/tests/test_icf_workflow.py), [`test_generation_preferences.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/tests/test_generation_preferences.py), [`test_template_rendering.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/tests/test_template_rendering.py), [`test_template_pdf_workflow.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/tests/test_template_pdf_workflow.py), [`test_phase5_part4.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/tests/test_phase5_part4.py), [`test_gemini_live.py`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/tests/test_gemini_live.py), [`frontend/tests/workflow.test.mjs`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/frontend/tests/workflow.test.mjs), [`frontend/tests/template-export.test.mjs`](file:///d:/Document-Drive/Graduation%20Project/ICF_Generator_Automated_Workflow/ICF_Generator/frontend/tests/template-export.test.mjs)
