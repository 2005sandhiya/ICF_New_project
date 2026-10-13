# Template and PDF implementation report

Verified 28 September 2026. This change extends the existing React/FastAPI application and preserves its current design, data and RAG/LLM pipeline.

## Implemented features

- Optional, study-specific DOCX template upload, replacement, reference download and removal. File size, DOCX structure, unsafe content and storage paths are checked. Invalid uploads preserve the previous selection; missing selected files block generation/export with an actionable error.
- The existing built-in DOCX layout remains the default. The NIH reference document under `data/templates` remains unchanged; it was not the application's active default template.
- Known placeholders and headings receive generated sections. The renderer retains supported styles, tables, ordering, headers, footers and page setup. Missing sections are appended and flagged. Template wording never enters RAG or protocol facts; retained wording requires explicit human review.
- Standard and patient-friendly documents share the selected template version and retain separate generated content. Generation includes populated text previews and validation for the current revision.
- PDF is the primary UI download, with editable DOCX available for both variants. Conversion runs locally with LibreOffice; outputs are checked for valid pages and the expected study, revision and section text, including sections spanning repeated page headers/footers.
- Approval binds the current study, revision, template and draft content. Successful regeneration increments the revision and requires review again. Template changes invalidate approval. Stale requests and supplied content that differs from the approved stored draft are rejected.
- Revision snapshots, validation results and review decisions are visible in the review history. Existing targeted feedback/regeneration and deterministic generation fallbacks are retained.

## Important files

| Files | Purpose |
| --- | --- |
| `backend/app/services/template_service.py`, `backend/app/models/template.py`, `backend/app/api/template_routes.py` | Upload validation, isolated persistent selection, immutable template versions and API routes |
| `backend/app/services/template_renderer.py`, `docx_generation_service.py` | Populate custom layouts and preserve the default DOCX generation path |
| `backend/app/services/pdf_generation_service.py` | Headless LibreOffice conversion, timeouts, PDF text/metadata verification and actionable errors |
| `backend/app/services/icf_generation_service.py`, `human_review_service.py`, `workflow_lock.py` | Revision snapshots, generated document storage, validation and approval binding, per-study concurrency control |
| `backend/app/api/icf_routes.py`, `review_routes.py`, `validation_routes.py`, `backend/app/main.py` | Export restrictions, history, capabilities and route integration |
| `backend/app/models/icf.py`, `human_review.py` | Template, preview, validation, revision and approval fields |
| `frontend/src/App.jsx`, `api/templates.js`, `api/client.js` | Template API state, exact-revision downloads and review integration |
| `frontend/src/components/TemplatePanel.jsx`, `IntelligencePanels.jsx`, `workflow.js`, `frontend/src/index.css` | Focused template, review, history, PDF/DOCX controls and status indicators |
| `tests/test_templates.py`, `test_template_rendering.py`, `test_template_pdf_workflow.py`, `frontend/tests/template-export.test.mjs` | Template, formatting, workflow, conversion and frontend regression coverage |
| `backend/requirements.txt`, `README.md`, `docs/TEMPLATE_PDF_WORKFLOW.md` | Dependencies, startup, supported templates, test commands and limitations |
| `frontend/dist` | Rebuilt production assets |

The original `test_phase3_part2.py` DOCX fallback fixture was corrected to create a valid Word package and use the actual reference-template location. The standalone validation endpoint test in `test_phase5_part4.py` now isolates its in-memory draft store from earlier tests. Existing assertions were retained. A separate regression test verifies that substituted validation content is rejected.

## Dependencies

LibreOffice is required on the backend host for PDF conversion; version 26.8.0.3 was used for verification. It is external software and is not bundled in the project ZIP. Set `LIBREOFFICE_PATH` if it is not installed in a standard location.

The backend requirements now explicitly declare existing application dependencies: `python-docx` (Word document handling), `pypdf` (PDF parsing/verification), `numpy`, `sentence-transformers` and `faiss-cpu` (existing embeddings/retrieval). No frontend production dependency was added.

## Executed verification

| Check | Observed result |
| --- | --- |
| Baseline backend suite before changes | 159 passed; 1 failed due to the invalid DOCX test fixture described above |
| Final complete backend suite | **196 passed, 2 warnings**, no failures or skipped tests, in 439.70 seconds |
| Existing frontend workflow checks | **23 passed** |
| New frontend template/export checks | **9 passed** |
| Production build | Vite build passed: 40 modules; output includes the updated template/review/export UI |
| Real PDF integration | Default and custom templates, standard and patient-friendly versions, approval restrictions, request-changes/revision flow and a long section across repeated headers passed |
| Failure/isolation coverage | Invalid/corrupt/unsafe templates, replacement/removal, cross-study isolation, missing selected files, stale approvals, substituted content, missing converter, conversion errors, empty/invalid PDFs and missing section text passed |
| Browser verification | Default generation with automatic validation; test review and standard PDF download; custom upload and filename; approval reset; new revision; explicit custom-template review confirmation; patient-friendly DOCX download and success status |
| Document visual verification | All pages of four default/custom PDF variants inspected (10 pages total); additional long standard/patient-friendly custom DOCX documents rendered with `render_docx.py`, and all six resulting pages inspected. Table structure, headings, headers/footers and readable content were checked |
| Preserved files | Hash comparison found no changes to project data or the NIH reference template, and no changes to the LLM service, protocol analysis, RAG, chunking or embedding services |

Tests and interactive verification used isolated data copies and temporary template storage. Test review decisions are software checks, not clinical approvals. Live external LLM calls were not exercised with paid credentials; existing provider unit tests and the deterministic fallback ran.

The usual `npm run build` command encountered an environment-specific permission error while esbuild scanned a restricted ancestor directory. The same Vite configuration completed the production build through native configuration import:

```powershell
node --input-type=module -e 'import {build} from "vite"; import config from "./vite.config.js"; await build({...config,configFile:false});'
```

No application configuration was changed to work around that local sandbox restriction.

## Start the application

From the extracted `ICF_Generator` directory, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
# Set this only if LibreOffice is not otherwise discoverable:
$env:LIBREOFFICE_PATH = 'C:\Program Files\LibreOffice\program\soffice.com'
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8001
```

In another terminal, from the extracted project directory:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. The backend is at `http://127.0.0.1:8001`. Use the actual LibreOffice path on your machine. The first embedding operation may download its configured model. Supply any optional LLM credentials through the process environment; the application does not automatically load `.env` files.

## Try the new workflow

1. Select a study or process/index a protocol and check the target study ID.
2. Open **ICF generation**. Generate with the default layout, or upload a DOCX containing supported headings/placeholders. The workflow guide lists the template contract.
3. Inspect both generated variants, populated template text and validation findings.
4. Open **Human review**. For a custom template, check retained wording against the protocol and confirm the checkbox before approving.
5. Download standard/patient-friendly PDF, then optionally DOCX. Confirm study ID and revision in the document and filename.
6. Request changes, regenerate and verify the new revision is pending review. Approve it only after checking the new validation findings.
7. Replace/remove a template and confirm a newly generated revision is required. Try a corrupt DOCX and confirm the previous selection remains intact with an error.

To rerun automated checks, use `python -m pytest tests -q` from the project root. From `frontend`, run `node tests/workflow.test.mjs`, `node --test tests/template-export.test.mjs` and `npm run build`. Real conversion tests require LibreOffice and skip when it is unavailable.

## Remaining limitations

- Drafts, populated documents, validation, review state and revision history follow the existing in-memory architecture and reset on backend restart. Templates persist. Run one backend worker.
- Existing local review has no authenticated reviewer roles. Internal approval is a workflow restriction and does not constitute clinical, regulatory or IRB approval.
- Retained institutional wording requires human review. Fonts, wrapping and LibreOffice pagination can differ from Word; arbitrary templates are not guaranteed to retain perfect layout. Unsupported macros, embedded objects, external linked content, text boxes and tracked changes are rejected. Complex fields and layouts may require template preparation or may fail conservative PDF text verification.
- The normal npm CLI build could not complete inside this restricted execution environment; the Vite API build succeeded as described above.

No required feature remains unimplemented within these documented boundaries. See [the workflow guide](TEMPLATE_PDF_WORKFLOW.md) for the full API and template preparation reference.
