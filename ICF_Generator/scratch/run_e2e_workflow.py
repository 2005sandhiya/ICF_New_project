import os
import json
import time
import urllib.request
import urllib.parse
from pypdf import PdfReader

BASE_URL = "http://127.0.0.1:8001/api"
STUDIES = ["NCT00162175", "NCT00081328", "NCT01713764"]
OUTPUT_DIR = r"d:\Document-Drive\Graduation Project\ICF_Generator_Automated_Workflow\scratch\output_documents"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def post_form(url, fields):
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = []
    for k, v in fields.items():
        body.append(f"--{boundary}".encode("utf-8"))
        body.append(f'Content-Disposition: form-data; name="{k}"'.encode("utf-8"))
        body.append(b"")
        body.append(str(v).encode("utf-8"))
    body.append(f"--{boundary}--".encode("utf-8"))
    body.append(b"")
    payload = b"\r\n".join(body)

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_json(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def post_json(url, data):
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def download_file(url, out_path):
    req = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(req) as resp:
        content = resp.read()
        with open(out_path, "wb") as f:
            f.write(content)
        print(f"Saved: {out_path} ({len(content)} bytes)")

def run_study_workflow(study_id):
    print(f"\n=================== Starting E2E Production Workflow for {study_id} ===================")
    # 1. Start Workflow
    start_resp = post_form(f"{BASE_URL}/icf/workflow", {"study_id": study_id})
    job_id = start_resp["job_id"]
    print(f"Job started: {job_id}")

    # 2. Poll Workflow status
    start_time = time.time()
    job_result = None
    while True:
        job = get_json(f"{BASE_URL}/icf/workflow/{job_id}")
        status = job.get("status")
        current_step = job.get("current_step")
        print(f"Job {job_id} [{status}] current_step: {current_step}")
        if status in ("succeeded", "COMPLETED", "completed"):
            job_result = job.get("result")
            break
        elif status in ("failed", "FAILED", "error", "ERROR"):
            print(f"Job failed with error: {job.get('error')}")
            return None
        time.sleep(2)
        if time.time() - start_time > 180:
            print("Timeout waiting for job completion")
            break

    # Save job result for trace audit if available
    if job_result:
        result_trace_path = os.path.join(OUTPUT_DIR, f"{study_id}_workflow_result.json")
        with open(result_trace_path, "w", encoding="utf-8") as f:
            json.dump(job_result, f, indent=2)
        print(f"Saved workflow result trace to {result_trace_path}")

    # 3. Approve Review
    print(f"Approving human review for {study_id}...")
    rev_state = get_json(f"{BASE_URL}/icf/review/{study_id}")
    print(f"Current review state: {rev_state.get('review_status')}")
    
    approved_res = post_json(f"{BASE_URL}/icf/review/{study_id}", {
        "review_status": "APPROVED",
        "reviewer_comment": "E2E Production Workflow Verification Approved"
    })
    print(f"Approved state: {approved_res.get('review_status')}")

    # 4. Export DOCX & PDF
    docx_path = os.path.join(OUTPUT_DIR, f"{study_id}_Standard_ICF.docx")
    pdf_path = os.path.join(OUTPUT_DIR, f"{study_id}_Standard_ICF.pdf")

    print(f"Exporting production DOCX for {study_id}...")
    download_file(f"{BASE_URL}/icf/export/{study_id}?format=docx&export_type=standard", docx_path)

    print(f"Exporting production PDF for {study_id}...")
    download_file(f"{BASE_URL}/icf/export/{study_id}?format=pdf&export_type=standard", pdf_path)

    # 5. Extract PDF text
    reader = PdfReader(pdf_path)
    full_text = "\n".join([page.extract_text() for page in reader.pages])
    txt_path = os.path.join(OUTPUT_DIR, f"{study_id}_Standard_ICF.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(full_text)
    print(f"Extracted {len(full_text)} characters from generated PDF into {txt_path}")
    return txt_path

if __name__ == "__main__":
    for s in STUDIES:
        run_study_workflow(s)
