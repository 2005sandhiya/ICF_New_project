import io
import os
from pathlib import Path
from unittest.mock import patch

import docx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.main import app
from app.services.human_review_service import human_review_service
from app.services.icf_generation_service import icf_generation_service
from app.services.pdf_generation_service import PDFConversionError, PDFDependencyMissing, pdf_generation_service
from app.services.template_service import SECTION_TITLES, template_service
from test_phase6_part5 import build_sample_facts

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_llm_deterministic(monkeypatch):
    from app.services.llm.llm_service import llm_service

    class OfflineProvider:
        provider_name = "offline_mock"
        def is_available(self):
            return False
        def generate_message(self, *args, **kwargs):
            return None

    monkeypatch.setattr(llm_service, "get_active_provider", lambda: OfflineProvider())
@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(template_service, "root", tmp_path / "templates")
    human_review_service.reset_reviews()
    icf_generation_service.reset_store()
    yield
    human_review_service.reset_reviews()
    icf_generation_service.reset_store()


def upload(study="TEST_A", filename="custom.docx", raw=None):
    if raw is None:
        document = docx.Document()
        document.sections[0].header.paragraphs[0].text = "Study {{study_id}} - revision {{revision}}"
        for key, title in reversed(list(SECTION_TITLES.items())):
            document.add_heading(title, 1)
            document.add_paragraph("{{icf." + key + "}}")
        buffer = io.BytesIO()
        document.save(buffer)
        raw = buffer.getvalue()
    return client.post(f"/api/icf/template/{study}", files={"file": (filename, raw, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})


def generate(study="TEST_A", previous=None):
    payload = {"study_id": study, "analysis_facts": build_sample_facts(study).model_dump(mode="json")}
    if previous:
        payload.update(previous_icf_draft=previous["icf_draft"], reviewer_feedback="Clarify missing risk information without adding clinical claims.")
    response = client.post("/api/icf/generate", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def approve(data, **kwargs):
    return client.post(f'/api/icf/review/{data["study_id"]}', json={"review_status": "APPROVED", "revision": data["revision"], **kwargs})


def export(data, kind="standard", format="docx", **kwargs):
    return client.post(f'/api/icf/export/{data["study_id"]}?export_type={kind}&format={format}&revision={data["revision"]}', **kwargs)


def test_upload_api_rejects_invalid_files_and_preserves_selection():
    good = upload()
    assert good.status_code == 200, good.text
    for filename, content in [("bad.pdf", b"pdf"), ("bad.docx", b"broken")]:
        response = upload(filename=filename, raw=content)
        assert response.status_code == 400
        assert client.get("/api/icf/template/TEST_A").json() == good.json()
    assert client.get("/api/icf/template/TEST_B").json()["kind"] == "default"
    replacement = upload(filename="replacement.docx")
    assert replacement.json()["template_id"] != good.json()["template_id"]
    assert client.delete("/api/icf/template/TEST_A").json()["kind"] == "default"


def test_custom_generation_review_and_both_docx_versions():
    selected = upload().json()
    data = generate()
    assert data["template"] == selected
    assert data["icf_draft"] == data["patient_friendly_icf"]
    assert data["validation_report"]["revision"] == data["revision"]
    assert export(data).status_code == 409
    assert approve(data).status_code == 409  # retained template text requires review confirmation
    assert approve(data, template_reviewed=True).status_code == 200
    for kind in ["patient_facing"]:
        response = export(data, kind)
        assert response.status_code == 200, response.text
        document = docx.Document(io.BytesIO(response.content))
        headings = [p.text for p in document.paragraphs if p.style and p.style.name and p.style.name.startswith("Heading")]
        supported_keys = [sec["section_id"] for sec in data["icf_draft"]["sections"] if sec.get("status") == "SUPPORTED"]
        expected_headings = [SECTION_TITLES[k] for k in list(SECTION_TITLES.keys()) if k in supported_keys]
        assert set(expected_headings).issubset(set(headings)) or set(headings).issubset(set(expected_headings))
        assert "Study TEST_A - revision 1" in document.sections[0].header.paragraphs[0].text


def test_replacement_requires_new_revision_and_preserves_history():
    upload()
    first = generate()
    assert approve(first, template_reviewed=True).status_code == 200
    upload(filename="replacement.docx")
    assert export(first).status_code == 409
    assert approve(first, template_reviewed=True).status_code == 409
    second = generate(previous=first)
    assert second["revision"] == 2
    assert second["template"]["template_id"] != first["template"]["template_id"]
    assert client.get("/api/icf/review/TEST_A").json()["review_status"] == "PENDING"
    assert approve(second, template_reviewed=True).status_code == 200
    assert export(first).status_code == 409
    assert export(second).status_code == 200
    history = client.get("/api/icf/revisions/TEST_A").json()
    assert [r["revision"] for r in history["revisions"]] == [1, 2]
    assert history["revisions"][0]["template"] == first["template"]


def test_fresh_generation_also_revokes_old_approval():
    first = generate()
    approve(first)
    second = generate()
    assert second["revision"] == 2
    assert export(second).status_code == 409
    assert approve(first).status_code == 409


def test_export_rejects_body_substitution_and_cross_study_content():
    first, other = generate(), generate("TEST_B")
    approve(first)
    other["icf_draft"]["sections"][0]["content"] = "Content belonging to study B only."
    assert export(first, json={"icf_draft": other["icf_draft"]}).status_code == 409
    changed = first["icf_draft"]
    changed["sections"][0]["content"] = "UNAPPROVED STUDY CONTENT"
    assert export(first, json={"icf_draft": changed}).status_code == 409
    assert export(other).status_code == 409


def test_foreign_protocol_facts_rejected():
    response = client.post("/api/icf/generate", json={"study_id": "TEST_A", "analysis_facts": build_sample_facts("TEST_B").model_dump(mode="json")})
    assert response.status_code == 400


def test_validation_rejects_a_different_draft_without_replacing_current_report():
    data = generate()
    original_report = icf_generation_service.get_stored_icf("TEST_A").validation_report.copy()
    data["icf_draft"]["sections"][0]["content"] = "Unapproved substituted wording."
    response = client.post("/api/icf/validate", json={"study_id": "TEST_A", "icf_draft": data["icf_draft"]})
    assert response.status_code == 409
    assert icf_generation_service.get_stored_icf("TEST_A").validation_report == original_report


def test_missing_custom_template_blocks_generation_and_export():
    selected = upload().json()
    data = generate()
    approve(data, template_reviewed=True)
    (template_service._folder("TEST_A") / (selected["template_id"] + ".docx")).unlink()
    assert client.get("/api/icf/template/TEST_A").status_code == 409
    assert export(data).status_code == 409
    assert client.post("/api/icf/generate", json={"study_id": "TEST_A"}).status_code == 400


def test_pdf_missing_dependency_and_failure_leave_approval_intact(monkeypatch):
    data = generate()
    approve(data)
    monkeypatch.setenv("LIBREOFFICE_PATH", "nonexistent-converter")
    assert export(data, format="pdf").status_code == 503
    with patch.object(pdf_generation_service, "generate_pdf", side_effect=PDFConversionError("Conversion failed.")):
        assert export(data, format="pdf").status_code == 502
    assert client.get("/api/icf/review/TEST_A").json()["review_status"] == "APPROVED"
    assert export(data).status_code == 200


def test_invalid_empty_and_wrong_content_pdf_rejected():
    from pypdf import PdfWriter
    from app.models.icf import ICFDraft
    writer = PdfWriter()
    writer.add_blank_page(width=600, height=800)
    output = io.BytesIO()
    writer.write(output)
    for raw in [b"", b"not pdf", b"%PDF-corrupt", output.getvalue()]:
        with pytest.raises(PDFConversionError):
            pdf_generation_service.validate_pdf(raw, "TEST_A", ICFDraft(revision=1), "standard")


@pytest.mark.parametrize("custom", [False, True], ids=["default", "custom"])
def test_real_pdf_end_to_end_and_revision(custom, tmp_path):
    if not pdf_generation_service.status()["available"]:
        pytest.skip("LibreOffice is not installed; run with LIBREOFFICE_PATH to verify real conversion")
    if custom:
        assert upload().status_code == 200
    data = generate()
    assert export(data, format="pdf").status_code == 409
    assert approve(data, template_reviewed=custom).status_code == 200
    for kind in ["patient_facing"]:
        response = export(data, kind, "pdf")
        assert response.status_code == 200, response.text
        reader = PdfReader(io.BytesIO(response.content))
        assert len(reader.pages) > 0
        assert reader.metadata["/ICFStudyID"] == "TEST_A"
        assert reader.metadata["/ICFRevision"] == "1"
        assert reader.metadata["/ICFDocumentType"] == kind
        (tmp_path / f"{custom}-{kind}.pdf").write_bytes(response.content)
    client.post("/api/icf/review/TEST_A", json={"review_status": "CHANGES_REQUESTED", "revision": 1, "reviewer_comment": "Clarify the risk information."})
    revised = generate(previous=data)
    assert revised["validation_report"]["revision"] == 2
    assert export(revised, format="pdf").status_code == 409
    assert approve(revised, template_reviewed=custom).status_code == 200
    response = export(revised, format="pdf")
    assert response.status_code == 200, response.text
    assert PdfReader(io.BytesIO(response.content)).metadata["/ICFRevision"] == "2"


@pytest.mark.parametrize("missing_word", [False, True])
def test_pdf_page_headers_do_not_interrupt_section_verification(missing_word):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    from app.models.icf import ICFDraft, ICFSection
    writer = PdfWriter()
    for body in ["TEST_A Revision 1 First part of the section.", "Second part of the section." if not missing_word else "Second of the section."]:
        page = writer.add_blank_page(width=600, height=800)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 72 750 Td (Research header) Tj 0 -20 Td (Review footer) Tj 0 -20 Td ({body}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    pdf = io.BytesIO(); writer.write(pdf)
    document = docx.Document()
    document.sections[0].header.paragraphs[0].text = "Research header"
    document.sections[0].footer.paragraphs[0].text = "Review footer"
    source = io.BytesIO(); document.save(source)
    draft = ICFDraft(sections=[ICFSection(section_id="purpose", title="Purpose", content="First part of the section. Second part of the section.")])
    if missing_word:
        with pytest.raises(PDFConversionError):
            pdf_generation_service.validate_pdf(pdf.getvalue(), "TEST_A", draft, "standard", source.getvalue())
    else:
        result = pdf_generation_service.validate_pdf(pdf.getvalue(), "TEST_A", draft, "standard", source.getvalue())
        assert len(PdfReader(io.BytesIO(result)).pages) == 2


def test_real_pdf_long_section_with_repeated_headers():
    from app.models.icf import ICFDraft, ICFSection
    if not pdf_generation_service.status()["available"]:
        pytest.skip("LibreOffice is required for real conversion")
    content = "Each study visit includes the procedures described in the protocol. " * 160
    draft = ICFDraft(sections=[ICFSection(section_id="procedures", title="Study Procedures", content=content)])
    document = docx.Document()
    document.sections[0].header.paragraphs[0].text = "Research header"
    document.sections[0].footer.paragraphs[0].text = "Review footer"
    document.add_paragraph("TEST_A Revision 1")
    document.add_paragraph(content)
    source = io.BytesIO(); document.save(source)
    result = pdf_generation_service.generate_pdf(source.getvalue(), "TEST_A", draft, "standard")
    assert len(PdfReader(io.BytesIO(result)).pages) > 1
