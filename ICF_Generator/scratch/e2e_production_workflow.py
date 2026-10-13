import sys
import os
import json
import time
from pathlib import Path
from pypdf import PdfReader

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.services.icf_workflow_service import icf_workflow_service
from app.services.human_review_service import human_review_service
from app.models.human_review import HumanReviewUpdateRequest, ReviewStatusEnum
from app.services.icf_generation_service import icf_generation_service
from app.services.docx_generation_service import docx_generation_service
from app.services.pdf_generation_service import pdf_generation_service
from app.services.template_service import template_service

OUTPUT_DIR = Path(os.path.dirname(__file__)) / "output_documents"
OUTPUT_DIR.mkdir(exist_ok=True)

TARGET_STUDIES = ["NCT00162175", "NCT00081328", "NCT01713764"]

def run_e2e_workflow_for_study(study_id: str):
    print(f"\n=======================================================")
    print(f"RUNNING E2E PRODUCTION WORKFLOW FOR: {study_id}")
    print(f"=======================================================")

    # Step 1: Start Workflow Job
    job = icf_workflow_service.start(study_id=study_id)
    job_id = job["job_id"]
    print(f"Workflow Job Started: ID={job_id}")

    # Synchronous execution of workflow steps (as background worker does)
    icf_workflow_service.run(job_id)

    # Poll status
    job_res = icf_workflow_service.get(job_id)
    print(f"Workflow Job Status: {job_res['status']}")
    if job_res["status"] != "succeeded":
        print(f"ERROR: Workflow failed for {study_id}: {job_res.get('error')}")
        return None

    # Step 2: Human Review Approval (required for export)
    print("Updating Human Review status to APPROVED...")
    review_resp = human_review_service.update_review(
        study_id,
        HumanReviewUpdateRequest(
            review_status=ReviewStatusEnum.APPROVED,
            reviewer_comment="E2E Verification Audit Approval"
        )
    )
    print(f"Review Status: {review_resp.review_status}")

    # Prepare approved documents
    icf_generation_service.prepare_approved_documents(study_id)

    # Step 3: Export DOCX & PDF
    stored = icf_generation_service.get_stored_icf(study_id)
    rev = stored.revision
    selected_template = template_service.selection(study_id)
    t_content = template_service.read(study_id, selected_template)

    docx_bytes = docx_generation_service.generate_docx(
        study_id,
        stored.icf_draft,
        export_type="standard",
        review_status="APPROVED",
        template_content=t_content
    )

    pdf_bytes, pdf_filename = pdf_generation_service.convert_docx_to_pdf(
        docx_bytes,
        filename_prefix=f"ICF_{study_id}_v{rev}"
    )

    docx_file = OUTPUT_DIR / f"{study_id}_v{rev}.docx"
    pdf_file = OUTPUT_DIR / f"{study_id}_v{rev}.pdf"

    docx_file.write_bytes(docx_bytes)
    pdf_file.write_bytes(pdf_bytes)

    print(f"Exported DOCX: {docx_file} ({len(docx_bytes)} bytes)")
    print(f"Exported PDF:  {pdf_file} ({len(pdf_bytes)} bytes)")

    # Step 4: Extract PDF Text and Analyze Content
    reader = PdfReader(pdf_file)
    num_pages = len(reader.pages)
    pdf_text_pages = [page.extract_text() for page in reader.pages]
    full_pdf_text = "\n--- PAGE ---\n".join(pdf_text_pages)

    print(f"\nPDF Metadata & Structure Analysis:")
    print(f"  Total Pages: {num_pages}")
    print(f"  Draft Revision: {rev}")

    # Extract present section titles
    present_sections = []
    for line in full_pdf_text.split("\n"):
        line_s = line.strip()
        if line_s.isupper() or any(sec in line_s for sec in ["Title", "Invitation", "Purpose", "Why You Are Being Asked", "Interventions", "Procedures", "Duration", "Risks", "Benefits", "Voluntary", "Confidentiality", "Questions"]):
            if len(line_s) < 60 and ("Study" in line_s or "Why" in line_s or "Purpose" in line_s or "Risks" in line_s or "Benefits" in line_s or "Voluntary" in line_s or "Confidentiality" in line_s or "Questions" in line_s or "Duration" in line_s):
                if line_s not in present_sections:
                    present_sections.append(line_s)

    print(f"\nDetected ICF Top-Level Section Headings in PDF:")
    for ps in present_sections:
        print(f"  - {ps}")

    return {
        "study_id": study_id,
        "revision": rev,
        "pdf_pages": num_pages,
        "pdf_text": full_pdf_text,
        "sections": present_sections,
        "stored": stored
    }

def main():
    results = {}
    for sid in TARGET_STUDIES:
        res = run_e2e_workflow_for_study(sid)
        results[sid] = res

    # Output full trace details for NCT00162175
    if results.get("NCT00162175"):
        nct_res = results["NCT00162175"]
        print("\n=======================================================")
        print("FULL TEXT OF EXPORTED PDF FOR NCT00162175:")
        print("=======================================================")
        print(nct_res["pdf_text"])

if __name__ == "__main__":
    main()
