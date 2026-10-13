"""Convert the revision's DOCX through LibreOffice, then validate the PDF."""
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unicodedata

from pypdf import PdfReader, PdfWriter

try:
    from dotenv import load_dotenv
    backend_env = Path(__file__).resolve().parent.parent.parent / ".env"
    if backend_env.is_file():
        load_dotenv(backend_env)
    workspace_env = backend_env.parent.parent / ".env"
    if workspace_env.is_file():
        load_dotenv(workspace_env)
except ImportError:
    pass


class PDFConversionError(RuntimeError):
    pass


class PDFDependencyMissing(PDFConversionError):
    pass


def normalize_text(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value).replace("\u00ad", "")).casefold()


def document_marginal_text(docx_bytes):
    """Known header/footer text, never arbitrary repeated PDF body content."""
    if not docx_bytes:
        return set()
    import docx
    from app.services.template_service import W
    from docx.text.paragraph import Paragraph
    document = docx.Document(io.BytesIO(docx_bytes))
    values = set()
    for section in document.sections:
        for region in [section.header, section.footer, section.first_page_header,
                       section.first_page_footer, section.even_page_header, section.even_page_footer]:
            for element in region._element.iter(W + "p"):
                value = normalize_text(Paragraph(element, region).text)
                if value:
                    values.add(value)
    return values


def page_body_text(value, marginal_text):
    # PDF extraction can place a footer before the body. Strip only exact,
    # known margin strings at page edges, each at most once per page. Joining
    # these page bodies preserves verification of a section spanning pages.
    text = normalize_text(value)
    remaining = set(marginal_text)
    while remaining:
        for margin in sorted(remaining, key=len, reverse=True):
            if text.startswith(margin):
                text = text[len(margin):]
            elif text.endswith(margin):
                text = text[:-len(margin)]
            else:
                continue
            remaining.remove(margin)
            break
        else:
            break
    return text


class PDFGenerationService:
    def __init__(self):
        self._cached_executable = None

    def executable(self):
        configured = os.environ.get("LIBREOFFICE_PATH")
        if configured:
            clean = configured.strip().strip('"\'')
            candidate = Path(clean)
            if candidate.is_file():
                self._cached_executable = str(candidate)
                return self._cached_executable
            if candidate.is_dir():
                for sub in [candidate / "soffice.exe", candidate / "soffice", candidate / "program" / "soffice.exe", candidate / "program" / "soffice"]:
                    if sub.is_file():
                        self._cached_executable = str(sub)
                        return self._cached_executable
            raise PDFDependencyMissing(
                f"LIBREOFFICE_PATH is set to '{clean}', but does not point to an available executable. "
                "Check the configured path and retry; editable DOCX export remains available."
            )

        if self._cached_executable and Path(self._cached_executable).is_file():
            return self._cached_executable
        located = shutil.which("soffice") or shutil.which("soffice.exe") or shutil.which("libreoffice")
        if located:
            self._cached_executable = located
            return located

        candidates = [
            Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "LibreOffice/program/soffice.exe",
            Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "LibreOffice/program/soffice.exe",
            Path(os.environ.get("LOCALAPPDATA", "C:/")) / "Programs/LibreOffice/program/soffice.exe",
            Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
            Path("/usr/bin/soffice"),
            Path("/usr/bin/libreoffice"),
        ]

        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            u_path = Path(user_profile)
            candidates.extend([
                u_path / "Documents/Codex/2026-09-27/files-mentioned-by-the-user-icf/work/libreoffice-portable/LibreOffice/program/soffice.exe",
                u_path / "Documents/Codex/2026-09-27/files-mentioned-by-the-user-icf/work/libreoffice-cab/soffice.exe",
            ])

        for candidate in candidates:
            if candidate.is_file():
                self._cached_executable = str(candidate)
                return self._cached_executable

        raise PDFDependencyMissing(
            "PDF export requires LibreOffice. Install it on the backend host or set LIBREOFFICE_PATH "
            "to its executable in backend/.env, then retry. Editable DOCX export remains available."
        )

    def status(self):
        try:
            self.executable()
            return {"available": True, "converter": "LibreOffice", "message": "PDF conversion is available."}
        except PDFDependencyMissing as exc:
            return {"available": False, "converter": "LibreOffice", "message": str(exc)}

    def generate_pdf(self, docx_bytes, study_id, draft, export_type):
        if not docx_bytes:
            raise PDFConversionError("Input DOCX document is empty or missing for PDF conversion.")
        executable = self.executable()
        with TemporaryDirectory(prefix="icf-pdf-") as working:
            folder = Path(working)
            source = folder / "consent.docx"
            try:
                source.write_bytes(docx_bytes)
            except Exception as exc:
                raise PDFConversionError(f"Could not write temporary input DOCX document: {exc}") from exc
            profile = folder / "profile"
            # Separate profiles prevent simultaneous conversions from attaching to a user's office process.
            command = [executable, "-env:UserInstallation=" + profile.as_uri(), "--headless", "--nologo",
                       "--nodefault", "--nofirststartwizard", "--convert-to", "pdf:writer_pdf_Export",
                       "--outdir", str(folder), str(source)]
            try:
                result = subprocess.run(command, capture_output=True, timeout=120, check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            except subprocess.TimeoutExpired as exc:
                raise PDFConversionError("PDF conversion timed out. Retry or download the editable DOCX.") from exc
            except PermissionError as exc:
                raise PDFConversionError(f"Permission denied executing LibreOffice at '{executable}'.") from exc
            except OSError as exc:
                raise PDFConversionError(f"The PDF converter executable '{executable}' could not start: {exc}.") from exc

            output = folder / "consent.pdf"
            if result.returncode != 0:
                err_detail = result.stderr.decode("utf-8", errors="ignore").strip() or result.stdout.decode("utf-8", errors="ignore").strip()
                suffix = f" Details: {err_detail}" if err_detail else f" Process returned exit code {result.returncode}."
                raise PDFConversionError(f"LibreOffice conversion process failed.{suffix} Check document layout and converter installation.")

            if not output.is_file() or not output.stat().st_size:
                raise PDFConversionError("LibreOffice finished conversion but did not produce a valid output PDF file.")

            return self.validate_pdf(output.read_bytes(), study_id, draft, export_type, docx_bytes)

    def validate_pdf(self, content, study_id, draft, export_type, docx_bytes=None):
        if not content.startswith(b"%PDF-"):
            raise PDFConversionError("The converter returned an invalid PDF.")
        try:
            reader = PdfReader(io.BytesIO(content), strict=True)
            if reader.is_encrypted or not reader.pages:
                raise ValueError("Empty or encrypted PDF")
            margins = document_marginal_text(docx_bytes)
            text = "".join(page_body_text(page.extract_text() or "", margins) for page in reader.pages)
            
            doc_paragraphs = []
            if docx_bytes:
                import docx
                from app.services.template_service import paragraphs
                input_doc = docx.Document(io.BytesIO(docx_bytes))
                doc_paragraphs = [
                    p.text.strip() for p in paragraphs(input_doc)
                    if p.text.strip() and len(p.text.strip()) > 20
                    and not p.text.strip().startswith(("AI-generated", "Standard ICF", "Patient-Friendly ICF"))
                ]
            
            if doc_paragraphs:
                expected = [study_id, f"Revision {draft.revision}"] + doc_paragraphs
            else:
                expected = [study_id, f"Revision {draft.revision}"] + [
                    sec.content.strip() for sec in draft.sections
                    if sec.content and len(sec.content.strip()) > 20
                ]

            missing = [val for val in expected if normalize_text(val) not in text]
            if missing and (len(missing) > 0 if len(expected) <= 3 else len(missing) > len(expected) // 2):
                raise PDFConversionError("PDF verification failed: expected study, revision or consent content is missing. Review the template layout and retry.")
            writer = PdfWriter()
            writer.clone_document_from_reader(reader)
            writer.add_metadata({"/ICFStudyID": study_id, "/ICFRevision": str(draft.revision), "/ICFDocumentType": export_type})
            result = io.BytesIO()
            writer.write(result)
            return result.getvalue()
        except PDFConversionError:
            raise
        except Exception as exc:
            raise PDFConversionError("The generated PDF could not be validated. No document was exported.") from exc


pdf_generation_service = PDFGenerationService()

