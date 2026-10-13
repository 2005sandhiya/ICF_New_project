import os
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, hex_color):
    """Sets background color of a table cell."""
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Sets cell padding in dxa (1 pt = 20 dxa)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)

def create_template_a(output_path):
    """
    Template A: Clean, simple patient-facing ICF layout.
    Traditional document style with clear serif/sans typography, subtle borders, and numbered sections.
    """
    doc = Document()
    
    # Page Margins
    sections = doc.sections
    for s in sections:
        s.top_margin = Inches(1.0)
        s.bottom_margin = Inches(1.0)
        s.left_margin = Inches(1.0)
        s.right_margin = Inches(1.0)

    # Document Header Title
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_title = p_title.add_run("INFORMED CONSENT FORM")
    run_title.font.name = "Arial"
    run_title.font.size = Pt(20)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(0x11, 0x18, 0x27) # Dark slate
    p_title.paragraph_format.space_after = Pt(4)

    # Study Title
    p_stitle = doc.add_paragraph()
    p_stitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_stitle = p_stitle.add_run("[STUDY_TITLE]")
    run_stitle.font.name = "Arial"
    run_stitle.font.size = Pt(14)
    run_stitle.font.italic = True
    run_stitle.font.bold = True
    run_stitle.font.color.rgb = RGBColor(0x37, 0x41, 0x51)
    p_stitle.paragraph_format.space_after = Pt(18)

    # Metadata Box (Simple 2-column table)
    meta_table = doc.add_table(rows=3, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_table.autofit = False

    meta_data = [
        ("Protocol / Study ID:", "[STUDY_ID]"),
        ("Document Version:", "[ICF_VERSION]"),
        ("Version Date:", "[ICF_VERSION_DATE]")
    ]

    for idx, (label, placeholder) in enumerate(meta_data):
        row = meta_table.rows[idx]
        
        c0 = row.cells[0]
        c0.width = Inches(2.2)
        p0 = c0.paragraphs[0]
        r0 = p0.add_run(label)
        r0.font.name = "Arial"
        r0.font.size = Pt(10)
        r0.font.bold = True
        r0.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
        set_cell_background(c0, "F3F4F6")
        set_cell_margins(c0, top=120, bottom=120, left=150, right=150)

        c1 = row.cells[1]
        c1.width = Inches(4.3)
        p1 = c1.paragraphs[0]
        r1 = p1.add_run(placeholder)
        r1.font.name = "Arial"
        r1.font.size = Pt(10)
        r1.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
        set_cell_background(c1, "FAFAFA")
        set_cell_margins(c1, top=120, bottom=120, left=150, right=150)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # Section definitions (10 numbered sections)
    sections_def = [
        ("1. Invitation & Introduction", "[INVITATION_INTRODUCTION]"),
        ("2. Purpose of the Study", "[PURPOSE_OF_STUDY]"),
        ("3. Why You Are Being Asked", "[WHY_YOU_ARE_BEING_ASKED]"),
        ("4. Study Procedures", "[STUDY_PROCEDURES_OVERVIEW]"),
        ("5. Study Interventions & Treatments", "[TREATMENT_DESCRIPTION]"),
        ("6. Alternatives to Participation", "[ALTERNATIVES_TO_PARTICIPATION]"),
        ("7. Voluntary Participation", "[VOLUNTARY_PARTICIPATION]"),
        ("8. Confidentiality & Data Protection", "[CONFIDENTIALITY_PRIVACY]"),
        ("9. Contact Information", "[WHO_TO_CONTACT]"),
    ]

    for heading_text, placeholder_text in sections_def:
        h_para = doc.add_paragraph()
        h_para.paragraph_format.space_before = Pt(14)
        h_para.paragraph_format.space_after = Pt(4)
        h_para.paragraph_format.keep_with_next = True
        h_run = h_para.add_run(heading_text)
        h_run.font.name = "Arial"
        h_run.font.size = Pt(12)
        h_run.font.bold = True
        h_run.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A) # Deep blue accent

        c_para = doc.add_paragraph()
        c_para.paragraph_format.space_before = Pt(0)
        c_para.paragraph_format.space_after = Pt(10)
        c_run = c_para.add_run(placeholder_text)
        c_run.font.name = "Arial"
        c_run.font.size = Pt(11)
        c_run.font.color.rgb = RGBColor(0x37, 0x41, 0x51)

    # Section 10: Participant Consent & Signatures
    h10_para = doc.add_paragraph()
    h10_para.paragraph_format.space_before = Pt(18)
    h10_para.paragraph_format.space_after = Pt(6)
    h10_para.paragraph_format.keep_with_next = True
    h10_run = h10_para.add_run("10. Participant Consent & Signature")
    h10_run.font.name = "Arial"
    h10_run.font.size = Pt(12)
    h10_run.font.bold = True
    h10_run.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)

    stmt_para = doc.add_paragraph()
    stmt_para.paragraph_format.space_after = Pt(14)
    stmt_run = stmt_para.add_run(
        "I have read and understood the information provided for this study. "
        "I have had the opportunity to ask questions and have received satisfactory answers. "
        "I voluntarily agree to participate in this study."
    )
    stmt_run.font.name = "Arial"
    stmt_run.font.size = Pt(10.5)
    stmt_run.font.italic = True
    stmt_run.font.color.rgb = RGBColor(0x4B, 0x55, 0x63)

    # Signature Block
    sig_table = doc.add_table(rows=3, cols=2)
    sig_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    sig_table.autofit = False

    sig_rows = [
        ("Participant Name:", "[Name]"),
        ("Participant Signature:", "[Signature]"),
        ("Date Signed:", "[Date]")
    ]

    for idx, (label, placeholder) in enumerate(sig_rows):
        row = sig_table.rows[idx]
        
        c0 = row.cells[0]
        c0.width = Inches(2.2)
        p0 = c0.paragraphs[0]
        r0 = p0.add_run(label)
        r0.font.name = "Arial"
        r0.font.size = Pt(10)
        r0.font.bold = True
        set_cell_margins(c0, top=140, bottom=140, left=150, right=150)

        c1 = row.cells[1]
        c1.width = Inches(4.3)
        p1 = c1.paragraphs[0]
        r1 = p1.add_run(placeholder)
        r1.font.name = "Arial"
        r1.font.size = Pt(10)
        set_cell_margins(c1, top=140, bottom=140, left=150, right=150)

    doc.save(output_path)
    print(f"Successfully created Template A: {output_path}")

def create_template_b(output_path):
    """
    Template B: Visually different modern professional layout.
    Features modern color bar headers, prominent executive grid header table, card-like section headings, and a structured signature matrix.
    """
    doc = Document()
    
    sections = doc.sections
    for s in sections:
        s.top_margin = Inches(0.8)
        s.bottom_margin = Inches(0.8)
        s.left_margin = Inches(0.9)
        s.right_margin = Inches(0.9)

    # Banner Header Table
    header_table = doc.add_table(rows=1, cols=1)
    header_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = header_table.rows[0].cells[0]
    cell.width = Inches(6.7)
    set_cell_background(cell, "0F172A") # Slate 900 dark theme header
    set_cell_margins(cell, top=200, bottom=200, left=200, right=200)

    p_banner = cell.paragraphs[0]
    p_banner.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_banner = p_banner.add_run("CLINICAL RESEARCH INFORMED CONSENT DOCUMENT")
    r_banner.font.name = "Segoe UI"
    r_banner.font.size = Pt(16)
    r_banner.font.bold = True
    r_banner.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # Modern Metadata Grid Table (3x2)
    meta_table = doc.add_table(rows=2, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_table.autofit = False

    # Row 0: Study Title across full concept or 2 cells
    cell_st_lbl = meta_table.rows[0].cells[0]
    cell_st_lbl.width = Inches(2.0)
    p_st_lbl = cell_st_lbl.paragraphs[0]
    r_st_lbl = p_st_lbl.add_run("Study Protocol Title:")
    r_st_lbl.font.name = "Segoe UI"
    r_st_lbl.font.size = Pt(10)
    r_st_lbl.font.bold = True
    r_st_lbl.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
    set_cell_background(cell_st_lbl, "F1F5F9")
    set_cell_margins(cell_st_lbl, top=100, bottom=100, left=120, right=120)

    cell_st_val = meta_table.rows[0].cells[1]
    cell_st_val.width = Inches(4.7)
    p_st_val = cell_st_val.paragraphs[0]
    r_st_val = p_st_val.add_run("[STUDY_TITLE]")
    r_st_val.font.name = "Segoe UI"
    r_st_val.font.size = Pt(10.5)
    r_st_val.font.bold = True
    r_st_val.font.color.rgb = RGBColor(0x02, 0x84, 0xC7) # Light blue emphasis
    set_cell_background(cell_st_val, "FAFAFA")
    set_cell_margins(cell_st_val, top=100, bottom=100, left=120, right=120)

    # Row 1: Protocol ID, Version & Date
    meta_table.add_row()
    r1_c0 = meta_table.rows[1].cells[0]
    r1_c0.width = Inches(2.0)
    p_id_lbl = r1_c0.paragraphs[0]
    r_id_lbl = p_id_lbl.add_run("Protocol ID / Code:")
    r_id_lbl.font.name = "Segoe UI"
    r_id_lbl.font.size = Pt(10)
    r_id_lbl.font.bold = True
    r_id_lbl.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
    set_cell_background(r1_c0, "F1F5F9")
    set_cell_margins(r1_c0, top=100, bottom=100, left=120, right=120)

    r1_c1 = meta_table.rows[1].cells[1]
    r1_c1.width = Inches(4.7)
    p_id_val = r1_c1.paragraphs[0]
    r_id_val = p_id_val.add_run("[STUDY_ID]")
    r_id_val.font.name = "Segoe UI"
    r_id_val.font.size = Pt(10)
    r_id_val.font.color.rgb = RGBColor(0x33, 0x41, 0x55)
    set_cell_background(r1_c1, "FAFAFA")
    set_cell_margins(r1_c1, top=100, bottom=100, left=120, right=120)

    meta_table.add_row()
    r2_c0 = meta_table.rows[2].cells[0]
    r2_c0.width = Inches(2.0)
    p_ver_lbl = r2_c0.paragraphs[0]
    r_ver_lbl = p_ver_lbl.add_run("Version & Date:")
    r_ver_lbl.font.name = "Segoe UI"
    r_ver_lbl.font.size = Pt(10)
    r_ver_lbl.font.bold = True
    r_ver_lbl.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
    set_cell_background(r2_c0, "F1F5F9")
    set_cell_margins(r2_c0, top=100, bottom=100, left=120, right=120)

    r2_c1 = meta_table.rows[2].cells[1]
    r2_c1.width = Inches(4.7)
    p_ver_val = r2_c1.paragraphs[0]
    r_ver_val = p_ver_val.add_run("Version [ICF_VERSION] (Dated: [ICF_VERSION_DATE])")
    r_ver_val.font.name = "Segoe UI"
    r_ver_val.font.size = Pt(10)
    r_ver_val.font.color.rgb = RGBColor(0x33, 0x41, 0x55)
    set_cell_background(r2_c1, "FAFAFA")
    set_cell_margins(r2_c1, top=100, bottom=100, left=120, right=120)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # Modern Section Blocks (Teal Accent Headers with Border Lines)
    modern_sections = [
        ("SECTION 1: STUDY INVITATION & OVERVIEW", "[INVITATION_INTRODUCTION]"),
        ("SECTION 2: STUDY PURPOSE & OBJECTIVES", "[PURPOSE_OF_STUDY]"),
        ("SECTION 3: ELIGIBILITY & PARTICIPATION BASIS", "[WHY_YOU_ARE_BEING_ASKED]"),
        ("SECTION 4: STUDY PROCEDURES & SCHEDULE", "[STUDY_PROCEDURES_OVERVIEW]"),
        ("SECTION 5: INVESTIGATIONAL TREATMENT DETAILS", "[TREATMENT_DESCRIPTION]"),
        ("SECTION 6: AVAILABLE ALTERNATIVE OPTIONS", "[ALTERNATIVES_TO_PARTICIPATION]"),
        ("SECTION 7: VOLUNTARY NATURE OF PARTICIPATION", "[VOLUNTARY_PARTICIPATION]"),
        ("SECTION 8: PRIVACY & DATA CONFIDENTIALITY", "[CONFIDENTIALITY_PRIVACY]"),
        ("SECTION 9: CONTACTS FOR QUESTIONS & RIGHTS", "[WHO_TO_CONTACT]"),
    ]

    for title_text, placeholder_text in modern_sections:
        # Styled section header table banner or shaded paragraph
        sec_table = doc.add_table(rows=1, cols=1)
        sec_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        sec_cell = sec_table.rows[0].cells[0]
        sec_cell.width = Inches(6.7)
        set_cell_background(sec_cell, "0284C7") # Cyan/Teal accent fill
        set_cell_margins(sec_cell, top=80, bottom=80, left=120, right=120)

        p_h = sec_cell.paragraphs[0]
        r_h = p_h.add_run(title_text)
        r_h.font.name = "Segoe UI"
        r_h.font.size = Pt(10.5)
        r_h.font.bold = True
        r_h.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

        p_b = doc.add_paragraph()
        p_b.paragraph_format.space_before = Pt(6)
        p_b.paragraph_format.space_after = Pt(14)
        r_b = p_b.add_run(placeholder_text)
        r_b.font.name = "Segoe UI"
        r_b.font.size = Pt(10.5)
        r_b.font.color.rgb = RGBColor(0x33, 0x41, 0x55)

    # Consent Section & Signature Card Matrix
    consent_sec_table = doc.add_table(rows=1, cols=1)
    consent_sec_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_cell = consent_sec_table.rows[0].cells[0]
    c_cell.width = Inches(6.7)
    set_cell_background(c_cell, "0F172A")
    set_cell_margins(c_cell, top=80, bottom=80, left=120, right=120)

    p_ch = c_cell.paragraphs[0]
    r_ch = p_ch.add_run("SECTION 10: PARTICIPANT INFORMED CONSENT & ACKNOWLEDGEMENT")
    r_ch.font.name = "Segoe UI"
    r_ch.font.size = Pt(10.5)
    r_ch.font.bold = True
    r_ch.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    p_cstmt = doc.add_paragraph()
    p_cstmt.paragraph_format.space_before = Pt(8)
    p_cstmt.paragraph_format.space_after = Pt(12)
    r_cstmt = p_cstmt.add_run(
        "By signing below, I confirm that I have read and understood the information provided in this consent document. "
        "I have had sufficient time to consider my decision and have received satisfactory answers to all my questions. "
        "I freely consent to take part in this research study."
    )
    r_cstmt.font.name = "Segoe UI"
    r_cstmt.font.size = Pt(10)
    r_cstmt.font.italic = True
    r_cstmt.font.color.rgb = RGBColor(0x47, 0x55, 0x69)

    # Modern Grid Signature Box
    grid_sig = doc.add_table(rows=2, cols=3)
    grid_sig.alignment = WD_TABLE_ALIGNMENT.CENTER
    grid_sig.autofit = False

    # Header row
    headers = ["Participant Field", "Value / Signature", "Date"]
    widths = [Inches(2.2), Inches(3.0), Inches(1.5)]

    for idx, (h_text, w) in enumerate(zip(headers, widths)):
        cell = grid_sig.rows[0].cells[idx]
        cell.width = w
        set_cell_background(cell, "E2E8F0")
        set_cell_margins(cell, top=100, bottom=100, left=100, right=100)
        p = cell.paragraphs[0]
        r = p.add_run(h_text)
        r.font.name = "Segoe UI"
        r.font.size = Pt(9.5)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

    # Data Row
    row1 = grid_sig.rows[1]
    
    # Cell 0: Name
    c0 = row1.cells[0]
    c0.width = widths[0]
    set_cell_background(c0, "FAFAFA")
    set_cell_margins(c0, top=120, bottom=120, left=100, right=100)
    p0 = c0.paragraphs[0]
    r0 = p0.add_run("Full Legal Name:\n")
    r0.font.bold = True
    r0.font.size = Pt(9.5)
    r0_val = p0.add_run("[Name]")
    r0_val.font.size = Pt(10)

    # Cell 1: Signature
    c1 = row1.cells[1]
    c1.width = widths[1]
    set_cell_background(c1, "FAFAFA")
    set_cell_margins(c1, top=120, bottom=120, left=100, right=100)
    p1 = c1.paragraphs[0]
    r1 = p1.add_run("Signature:\n")
    r1.font.bold = True
    r1.font.size = Pt(9.5)
    r1_val = p1.add_run("[Signature]")
    r1_val.font.size = Pt(10)

    # Cell 2: Date
    c2 = row1.cells[2]
    c2.width = widths[2]
    set_cell_background(c2, "FAFAFA")
    set_cell_margins(c2, top=120, bottom=120, left=100, right=100)
    p2 = c2.paragraphs[0]
    r2 = p2.add_run("Date Signed:\n")
    r2.font.bold = True
    r2.font.size = Pt(9.5)
    r2_val = p2.add_run("[Date]")
    r2_val.font.size = Pt(10)

    doc.save(output_path)
    print(f"Successfully created Template B: {output_path}")

if __name__ == "__main__":
    out_dir = "data/templates/custom_demo"
    os.makedirs(out_dir, exist_ok=True)
    
    file_a = os.path.join(out_dir, "ICF_Custom_Template_A_Simple.docx")
    file_b = os.path.join(out_dir, "ICF_Custom_Template_B_Modern.docx")

    create_template_a(file_a)
    create_template_b(file_b)
