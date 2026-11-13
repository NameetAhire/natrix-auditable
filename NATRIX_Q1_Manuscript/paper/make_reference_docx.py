"""Turn pandoc's default reference.docx into an Elsevier-style manuscript shell.

Run once after regenerating the default:

    cmd /c "pandoc --print-default-data-file reference.docx > paper\\elsevier_reference.docx"
    python paper/make_reference_docx.py

The script sets A4 pages, 2.54 cm margins, 12 pt Times New Roman double-spaced
body text, compact headings, 9 pt captions/tables, and continuous line numbers.
It is cosmetic only: no manuscript content is stored here.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

REF = Path(__file__).resolve().parent / "elsevier_reference.docx"
FONT = "Times New Roman"


def set_font(style, size: float, bold: bool | None = None,
             italic: bool | None = None) -> None:
    style.font.name = FONT
    style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold
    if italic is not None:
        style.font.italic = italic
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), FONT)


def spacing(style, line: float, before: float = 0, after: float = 0) -> None:
    pf = style.paragraph_format
    pf.line_spacing = line
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)


def add_line_numbers(document: Document) -> None:
    for section in document.sections:
        sect_pr = section._sectPr
        existing = sect_pr.find(qn("w:lnNumType"))
        if existing is not None:
            sect_pr.remove(existing)
        ln = OxmlElement("w:lnNumType")
        ln.set(qn("w:countBy"), "1")
        ln.set(qn("w:restart"), "continuous")
        ln.set(qn("w:distance"), "360")
        sect_pr.append(ln)


def main() -> None:
    if not REF.exists():
        raise SystemExit(f"missing {REF}; generate it with pandoc first")
    doc = Document(REF)

    for section in doc.sections:
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2.54)
        section.bottom_margin = Cm(2.54)
        section.left_margin = Cm(2.54)
        section.right_margin = Cm(2.54)

    styles = doc.styles

    normal = styles["Normal"]
    set_font(normal, 12)
    spacing(normal, 2.0, 0, 0)

    for name in ("Body Text", "First Paragraph"):
        st = styles[name]
        set_font(st, 12)
        spacing(st, 2.0, 0, 0)
        st.paragraph_format.first_line_indent = Cm(0)
        st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    title = styles["Title"]
    set_font(title, 16, bold=True)
    spacing(title, 1.15, 0, 12)
    title.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

    subtitle = styles["Subtitle"]
    set_font(subtitle, 12, italic=True)
    spacing(subtitle, 1.15, 0, 10)
    subtitle.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

    author = styles["Author"]
    set_font(author, 12)
    spacing(author, 1.15, 0, 4)
    author.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

    abstract_title = styles["Abstract Title"]
    set_font(abstract_title, 12, bold=True)
    spacing(abstract_title, 1.15, 12, 6)

    abstract = styles["Abstract"]
    set_font(abstract, 11)
    spacing(abstract, 1.15, 0, 10)
    abstract.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    for name, size, before, after in (
        ("Heading 1", 14, 18, 8),
        ("Heading 2", 12, 14, 6),
        ("Heading 3", 12, 12, 4),
    ):
        st = styles[name]
        set_font(st, size, bold=True)
        spacing(st, 1.15, before, after)
        st.paragraph_format.keep_with_next = True
        st.font.color.rgb = None

    for name in ("Caption", "Table Caption", "Image Caption"):
        st = styles[name]
        set_font(st, 9, italic=False)
        spacing(st, 1.0, 4, 8)

    if "Table" not in [s.name for s in styles]:
        table = styles.add_style("Table", WD_STYLE_TYPE.PARAGRAPH)
    else:
        table = styles["Table"]
    set_font(table, 9)
    spacing(table, 1.0, 0, 0)

    bibliography = styles["Bibliography"]
    set_font(bibliography, 10)
    spacing(bibliography, 1.15, 0, 4)

    add_line_numbers(doc)
    doc.save(REF)
    print(f"styled {REF}")


if __name__ == "__main__":
    main()
