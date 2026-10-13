# Templates, review and PDF export

Generated consent documents are drafts requiring appropriate human review. Automated checks and an internal approval do not constitute clinical validation, regulatory approval or IRB approval.

## Existing architecture and implementation plan

The application uses React 18 with Vite and CSS, FastAPI with Pydantic, JSON protocol data, local upload directories, sentence-transformers embeddings and FAISS retrieval. Protocol analysis supplies traceable facts to the existing standard and patient-friendly generation paths. The existing LLM integrations and deterministic fallbacks remain in place.

Before this change, DOCX export constructed a default layout in `backend/app/services/docx_generation_service.py`. The NIH document in `data/templates` was an unused reference, not the active generation template. The default layout remains the same. The reference document is unchanged and is never used as protocol evidence.

The work adds study-specific template storage, DOCX population, revision-bound review/export, a LibreOffice PDF converter and a single automatic protocol-to-consent workflow. The existing visual design and RAG pipeline remain in place. The workflow jobs use process-local status storage and FastAPI background tasks; run one backend worker.

## Normal user workflow

The sidebar keeps four user milestones: **Study & protocol**, **Generate ICF**, **Human review**, and **Export documents**. Select a preloaded study or upload a PDF, DOCX, TXT or JSON protocol, then continue to Generate ICF. Clicking **Generate informed consent form** starts the backend workflow. It checks the source, prepares searchable evidence when needed, gathers grounded study facts, generates both consent versions, validates the new revision, and prepares the DOCX documents. Progress appears in the existing page and pathway card; users do not need to run chunking, embeddings, retrieval, analysis or validation separately.

An optional template can be selected before generation. For an uploaded protocol, the DOCX is held for the current run and stored against the study identifier read from that protocol (or a stable content-derived identifier when the protocol has none). For a preloaded study, its saved template selection is loaded as before. Both paths use the existing default or study-specific template service.

Human review remains explicit. The reviewer inspects the generated drafts and built-in validation report. Clicking **Request changes & regenerate** saves the comment and immediately creates, validates and prepares the next revision. The new revision returns to PENDING; the reviewer must make a new decision before export.

## Run the application

From the project root, create an environment and install the backend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8001
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

On Linux/macOS, activate the environment with `source .venv/bin/activate`; the remaining Python commands are the same. The first embedding operation may download the configured sentence-transformers model. Optional provider credentials must be supplied through the backend process environment. This project does not automatically load `.env` files.

## PDF conversion dependency

Install [LibreOffice](https://www.libreoffice.org/download/) on the backend host. PDF conversion uses its [documented headless conversion interface](https://help.libreoffice.org/latest/en-GB/text/shared/guide/start_parameters.html). No cloud document service receives the consent document.

If LibreOffice is not discoverable on PATH or in a standard installation location, configure its executable before starting the backend:

```powershell
$env:LIBREOFFICE_PATH = 'C:\Program Files\LibreOffice\program\soffice.com'
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8001
```

For Linux, an example is `export LIBREOFFICE_PATH=/usr/bin/libreoffice`. For macOS, use `/Applications/LibreOffice.app/Contents/MacOS/soffice`.

Each conversion has an isolated temporary directory and LibreOffice profile, a 120-second timeout, and cleanup. The backend verifies the PDF header, parseability, pages, study ID, revision and every generated section's expected text. Known DOCX header/footer strings are removed only from extracted page edges so repeated margins do not interrupt sections spanning pages; missing body text still fails verification. It then records study, revision and document type in PDF metadata. Missing converters return HTTP 503; failed or invalid conversions return HTTP 502. They do not change approval or silently substitute another document. Editable DOCX remains available.

LibreOffice is external software, not a pip package. Python dependencies newly declared in `requirements.txt` are `python-docx`, `pypdf`, `numpy`, `sentence-transformers` and `faiss-cpu`; these were already imported by the application. No frontend production dependency is added.

## Upload a custom template

1. Choose a preloaded study or upload a protocol, then open **Generate ICF**.
2. In **ICF Template**, select an optional DOCX file, up to 10 MB. For an upload source, its filename is shown as staged for the study identified from the protocol; it is saved when generation starts.
3. For a saved study template, use **View selected template** to download the reference. Choose another file to replace it, or **Remove custom template / use default** to return to the built-in layout.
4. Click **Generate informed consent form**. Both document variants use the same selected template version and their respective generated content.

An invalid upload leaves the previous selection intact and displays an error. A missing or modified selected file blocks generation/export until the selection is repaired or explicitly removed. Template selection is stored under `data/templates/custom/<hash-of-study-id>/selection.json`; immutable DOCX versions use generated identifiers. User filenames are display metadata, never storage paths. Keep this directory with your project data.

## Template population

Explicit placeholders provide the most predictable mapping. They may appear in body paragraphs or table cells, including placeholders split across Word runs:

```text
{{icf.study_title}}
{{icf.invitation}}
{{icf.purpose}}
{{icf.why_asked}}
{{icf.procedures}}
{{icf.duration}}
{{icf.interventions}}
{{icf.risks}}
{{icf.benefits}}
{{icf.alternatives}}
{{icf.voluntary}}
{{icf.confidentiality}}
{{icf.questions_contact}}
```

Metadata placeholders `{{study_id}}`, `{{revision}}` and `{{document_type}}` work in body text, headers and footers. Consent-section placeholders belong in the document body. Unknown or duplicate section placeholders produce errors.

Without section placeholders, exact standard section headings such as **Purpose of the Study**, **Study Procedures**, **Risks and Discomforts**, and **Questions / Contact Information** are recognized, ignoring case, numbering and punctuation. Some common question-style headings are also recognized. Body text immediately following a mapped heading is replaced up to the next heading or structural boundary. A heading in a table label cell can populate the adjacent value cell. Ambiguous duplicate headings are rejected. Use placeholders for complex or unusual layouts.

The renderer retains the DOCX package, styles, headings, section order, tables, page setup, headers and footers where supported. It uses the existing paragraph/run formatting for inserted content. Missing generated sections are appended once under **Additional required consent sections** and reported as validation warnings. No clinical details are invented to fill gaps.

Template text never enters protocol analysis, RAG indexing, facts or LLM generation. Sample text under mapped headings is replaced. Other template wording is retained as **unverified template wording**, visible in the populated text preview and flagged for human review. For custom templates, approval requires an explicit confirmation that the populated document and retained wording were checked against the protocol. Authors should remove sample claims from unmapped text before upload.

## Review and revision workflow

Generation produces separate standard and patient-friendly content, populated document text previews, and a validation report for the new revision. Every successful generation increments the revision and resets review to PENDING, even when no reviewer feedback was supplied. A failed generation preserves the prior stored draft and review.

Open **Human review** to inspect both consent versions, populated document text and validation findings, then record a decision or request changes. Saved comments remain associated with their study/revision and are not clinical evidence. Requesting changes automatically runs the existing targeted revision workflow, validates the updated content, and requires human review again.

The existing human decision remains authoritative; validation findings, including failures and missing information, are presented for review and do not automatically approve a draft. There is no new numeric score threshold. Validation must have run on the stored current revision before it can be approved.

Approval binds the study, revision, template ID and a hash of both drafts. Changing a template invalidates review and requires a new generated revision. Export rejects stale revision requests and client-supplied content that differs from the stored approved draft. Revision and review history remain available in the human review panel and through the history endpoint.

In **Export documents**, PDF is the primary choice, with separate standard and patient-friendly downloads. Optional editable DOCX downloads use the same approved revision. The original export endpoint still defaults to DOCX for API compatibility; the frontend explicitly requests PDF.

## Added and extended API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/icf/template/{study_id}` | Selected template metadata, default/custom status and warnings |
| POST | `/api/icf/template/{study_id}` | Multipart DOCX upload or replacement using `file` |
| DELETE | `/api/icf/template/{study_id}` | Explicitly select the default layout |
| GET | `/api/icf/template/{study_id}/file` | Download the custom reference template |
| GET | `/api/icf/export-capabilities` | Converter availability without exposing server paths |
| GET | `/api/icf/revisions/{study_id}` | Generated revision snapshots and review decisions |
| POST | `/api/icf/workflow` | Start the automatic workflow with multipart `study_id` or `protocol`; optional `template` DOCX |
| GET | `/api/icf/workflow/{job_id}` | Read job status, progress messages and completed workflow result |
| POST | `/api/icf/export/{study_id}?format=pdf&export_type=standard&revision=2` | Approved PDF for the exact current revision |

Use `format=docx` for editable output and `export_type=patient_friendly` for the simplified version. Review updates can include `revision`; custom-template approval also requires `template_reviewed: true`.

## Testing

From the project root:

```powershell
python -m pytest tests -q
```

`tests/test_icf_workflow.py` covers the uploaded source path, an already-indexed preloaded study, stable fallback study identifiers and invalid-study failure state.

From `frontend`:

```powershell
npm run build
node tests/workflow.test.mjs
node --test tests/template-export.test.mjs
```

Real PDF integration tests run when LibreOffice is available; otherwise those tests report skipped. Unit tests still exercise missing dependencies, conversion errors and invalid/empty PDFs. Tests use temporary template storage, and frontend request mocks are confined to the test suite.

Manual checks: select a preloaded study and generate without clicking technical pipeline controls; repeat with an uploaded protocol and a staged custom template; verify progress ends at human review; request changes and confirm the new revision returns to PENDING; approve both variants, export PDF/DOCX, replace/remove a template and confirm approval resets; try a corrupt DOCX and confirm the selection remains intact; try exporting while pending and confirm it is blocked.

## Limitations

- Generated drafts, populated document bytes, validation reports, approvals and revision history use the existing in-memory architecture and reset on backend restart. Templates persist on disk. Run one backend worker; process-local state and locks do not coordinate multiple workers.
- This is the existing local review workflow. It has no authenticated user/role system; approval is a workflow restriction, not identity-based authorization.
- The application cannot determine whether retained institutional boilerplate is clinically appropriate. The human reviewer must check the complete populated document.
- Macros, embedded executable objects, external images/linked documents, text boxes and tracked changes are rejected. Complex conditional sections, content inside unsupported fields and arbitrary heading layouts require template preparation.
- Font availability and LibreOffice's DOCX rendering can affect pagination, wrapping and layout. Text/content validation is not a proof of perfect visual fidelity. Review the rendered PDF, especially custom tables, narrow cells and long sections.
- The standard and patient-friendly transformations retain the existing safeguards and deterministic fallback; their clinical meaning still requires human review.
