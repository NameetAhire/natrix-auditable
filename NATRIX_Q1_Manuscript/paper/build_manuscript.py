"""Build the manuscript in Word and LaTeX from one Markdown source.

The Markdown source may contain include directives on a line of their own:

    {{table:dataset_summary}}     -> tables/dataset_summary.md
    {{include:tables/foo.md}}     -> tables/foo.md

Everything else is ordinary pandoc Markdown.  Citations use pandoc syntax
[@key] and resolve against paper/refs.bib.

Usage
-----
    python paper/build_manuscript.py

Outputs
-------
    paper/NATRIX_manuscript.docx
    paper/NATRIX_manuscript.tex

The .tex file targets the Elsevier elsarticle class and expects refs.bib in the
same directory.  LaTeX is not installed in this workspace, so the .tex file is
not compiled here; the .docx is the build that is checked in.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "paper"
SOURCE = PAPER / "manuscript_short.md"
BUILD = PAPER / "build"
REFERENCE = PAPER / "elsevier_reference.docx"
TEMPLATE = PAPER / "elsarticle_template.tex"
BIB = PAPER / "refs.bib"

INCLUDE = re.compile(r"^\{\{(?:table:|include:)?([^}]+)\}\}[ \t]*$", re.MULTILINE)
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
KEYWORDS = re.compile(r"^keywords:\s*(.+)$", re.MULTILINE)

# Float keys are semantic, so a table can move and its printed number follows.
# The caption prefix identifies the float; the build refuses to run if a prefix
# is missing or duplicated, or if the number of in-text references changes.
TABLE_FLOATS = [
    ("Gate C per-candidate cost", "tab:gate-c"),
    ("Positive control", "tab:positive-control"),
    ("Labelled HTTP corpora", "tab:corpora"),
    ("Matched operating points at the cross-fitted", "tab:matched-operating"),
    ("View ablation. ", "tab:view-ablation"),
    ("Generic control and cross-fitted stackers", "tab:control-models"),
    ("P2 grouping sensitivity", "tab:grouping"),
    ("SR-BH scale sensitivity. The detector", "tab:srbh-scale"),
    ("v3 versus v4 on CSIC 2010", "tab:v3-v4"),
    ("End-to-end inline latency", "tab:latency"),
    ("ModSecurity CRS paranoia levels", "tab:crs"),
    ("Dilution-resistant feature variant", "tab:dilution"),
    ("Deployed enforcement boundary", "tab:deployment"),
]
FIGURE_FLOATS = [
    ("NATRIX architecture", "fig:architecture"),
    ("Matched operating points for NATRIX", "fig:protocol"),
    ("View ablation for the 22-D contract", "fig:views"),
    ("SR-BH scale sensitivity under P1", "fig:learning"),
    ("ECDF of end-to-end latency", "fig:latency"),
]
# One entry per in-text mention, in document order.  These are the semantic
# targets, not the current numbers, so inserting a float cannot silently
# renumber a reference.
TABLE_REF_ORDER = [
    "tab:gate-c",
    "tab:positive-control",
    "tab:corpora",
    "tab:matched-operating",
    "tab:matched-operating",
    "tab:matched-operating",
    "tab:matched-operating",
    "tab:view-ablation",
    "tab:view-ablation",
    "tab:matched-operating",
    "tab:matched-operating",
    "tab:control-models",
    "tab:grouping",
    "tab:srbh-scale",
    "tab:matched-operating",
    "tab:v3-v4",
    "tab:matched-operating",
    "tab:latency",
    "tab:crs",
    "tab:dilution",
    "tab:deployment",
]
FIGURE_REF_ORDER = [
    "fig:architecture",
    "fig:latency",
    "fig:protocol",
    "fig:views",
    "fig:learning",
]


def source_keywords(source: Path = SOURCE) -> str:
    """Read the keyword list from the manuscript YAML front matter."""
    match = KEYWORDS.search(source.read_text(encoding="utf-8"))
    if not match:
        return ""
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value


def included_markdown(text: str) -> str:
    """Strip a table file's own title and turn sub-headings into bold labels.

    The manuscript supplies the numbered caption, so an included file must not
    introduce a numbered section of its own.  Sub-headings inside multi-table
    files (dataset summary, formal evidence) become bold panel labels.
    """
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    out = []
    for line in lines:
        match = HEADING.match(line)
        if match:
            out.append(f"**{match.group(2).strip()}**")
            out.append("")
        else:
            out.append(line)
    return "\n".join(out).strip()


def expand(text: str) -> str:
    def repl(match: re.Match) -> str:
        target = match.group(1).strip()
        if target.startswith("tables/"):
            path = ROOT / target
        else:
            path = ROOT / "tables" / f"{target}.md"
        if not path.exists():
            raise SystemExit(f"include not found: {path}")
        return included_markdown(path.read_text(encoding="utf-8"))

    return INCLUDE.sub(repl, text)


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, text=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def postprocess_docx(path: Path, keywords: str = "") -> None:
    """Apply table-caption and table-cell typography after pandoc."""
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt
    from docx.text.paragraph import Paragraph

    doc = Document(path)
    caption = re.compile(r"^Table\s+\d+\.")
    for paragraph in doc.paragraphs:
        if caption.match(paragraph.text.strip()):
            try:
                paragraph.style = doc.styles["Table Caption"]
            except KeyError:
                pass
            for run in paragraph.runs:
                run.bold = True

    # An included table file may open with an explanatory paragraph, which
    # pandoc places between the manuscript's caption and the table.  Move the
    # caption to the table so it is adjacent, but never across another table
    # (a multi-panel table keeps one caption on its first panel).
    body = doc.element.body
    children = list(body)
    tables = [i for i, child in enumerate(children) if child.tag == qn("w:tbl")]
    for table_index in reversed(tables):
        cursor = table_index - 1
        caption_index = None
        while cursor >= 0:
            child = children[cursor]
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "tbl":
                break
            if tag == "p":
                text = "".join(
                    node.text or "" for node in child.findall(".//" + qn("w:t"))
                ).strip()
                if caption.match(text):
                    caption_index = cursor
                    break
            cursor -= 1
        if caption_index is not None and caption_index < table_index - 1:
            caption_element = children[caption_index]
            body.remove(caption_element)
            children[table_index].addprevious(caption_element)

    for table in doc.tables:
        table.autofit = True
        size = 7 if len(table.columns) >= 10 else 8
        for row_index, row in enumerate(table.rows):
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.size = Pt(size)
                        if row_index == 0:
                            run.bold = True
    if keywords:
        anchor = None
        for paragraph in doc.paragraphs:
            if paragraph.text.strip().startswith("Corresponding author:"):
                anchor = paragraph
                break
        if anchor is None:
            for paragraph in doc.paragraphs:
                if paragraph.text.strip().startswith(
                    "Department of Computer Engineering"
                ):
                    anchor = paragraph
                    break
        if anchor is None:
            for paragraph in doc.paragraphs:
                if paragraph.style.name == "Abstract":
                    anchor = paragraph
                    break
        if anchor is not None:
            new_p = OxmlElement("w:p")
            anchor._p.addnext(new_p)
            keyword_paragraph = Paragraph(new_p, anchor._parent)
            try:
                keyword_paragraph.style = doc.styles["First Paragraph"]
            except KeyError:
                pass
            run = keyword_paragraph.add_run("Keywords: ")
            run.bold = True
            keyword_paragraph.add_run(keywords)

    # Pandoc emits the YAML abstract before body text, which would place the
    # affiliation block below the abstract.  Move the block above it.
    abstract_title = next(
        (p for p in doc.paragraphs if p.style.name == "Abstract Title"), None
    )
    affiliations = [
        p
        for p in doc.paragraphs
        if p.text.strip().startswith(
            (
                "Department of Computer Engineering",
                "Department of Electronics and Telecommunication Engineering",
                "Corresponding author:",
            )
        )
    ]
    if abstract_title is not None:
        for paragraph in affiliations:
            abstract_title._p.addprevious(paragraph._p)

    doc.save(path)


def _matching_brace(text: str, opening: int) -> int:
    """Return the index of the brace that closes ``text[opening]``."""
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1


TABLE_BLOCK = re.compile(r"\\begin\{longtable\}.*?\\end\{longtable\}", re.DOTALL)
SIMPLE_SPEC = re.compile(r"\\begin\{longtable\}\[\]\{@\{\}([lcr]+)@\{\}\}")

# The 14-column drop-evidence table is too wide for equal columns.  The
# feature column needs room for names such as ``suspicious_extension_flag``;
# the confidence-interval column needs room for a bracketed pair.
WIDE_14_SPEC = r"""\begin{longtable}[]{@{}
  >{\raggedright\arraybackslash}p{(\linewidth - 26\tabcolsep) * \real{0.1000}}
  >{\raggedright\arraybackslash}p{(\linewidth - 26\tabcolsep) * \real{0.0700}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 26\tabcolsep) * \real{0.0650}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 26\tabcolsep) * \real{0.0650}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 26\tabcolsep) * \real{0.0650}}
  >{\raggedright\arraybackslash}p{(\linewidth - 26\tabcolsep) * \real{0.1400}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 26\tabcolsep) * \real{0.0550}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 26\tabcolsep) * \real{0.0650}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 26\tabcolsep) * \real{0.0650}}
  >{\centering\arraybackslash}p{(\linewidth - 26\tabcolsep) * \real{0.0400}}
  >{\centering\arraybackslash}p{(\linewidth - 26\tabcolsep) * \real{0.0400}}
  >{\centering\arraybackslash}p{(\linewidth - 26\tabcolsep) * \real{0.0400}}
  >{\centering\arraybackslash}p{(\linewidth - 26\tabcolsep) * \real{0.0400}}
  >{\raggedright\arraybackslash}p{(\linewidth - 26\tabcolsep) * \real{0.0700}}@{}}"""

# The four-column Gate C cost table needs a wide identifier column; equal
# widths split names such as ``max_param_name_entropy`` mid-word.
WIDE_4_COST_SPEC = r"""\begin{longtable}[]{@{}
  >{\raggedright\arraybackslash}p{(\linewidth - 6\tabcolsep) * \real{0.3400}}
  >{\raggedright\arraybackslash}p{(\linewidth - 6\tabcolsep) * \real{0.1600}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 6\tabcolsep) * \real{0.2600}}
  >{\raggedright\arraybackslash}p{(\linewidth - 6\tabcolsep) * \real{0.2400}}@{}}"""


# The v3-D positive-control table needs a wide feature column and a wide
# interval column; six equal columns split identifiers and confidence
# intervals across lines.
WIDE_6_V3D_SPEC = r"""\begin{longtable}[]{@{}
  >{\raggedright\arraybackslash}p{(\linewidth - 10\tabcolsep) * \real{0.2600}}
  >{\raggedright\arraybackslash}p{(\linewidth - 10\tabcolsep) * \real{0.1000}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 10\tabcolsep) * \real{0.1200}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 10\tabcolsep) * \real{0.1200}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 10\tabcolsep) * \real{0.2400}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 10\tabcolsep) * \real{0.1600}}@{}}"""


# The corpus-summary table needs a wide notes column and enough room for
# ``clean / attack`` and ``endpoint signatures``; equal widths wrap every
# cell onto three or four lines.
WIDE_6_DATASET_SPEC = r"""\begin{longtable}[]{@{}
  >{\raggedright\arraybackslash}p{(\linewidth - 10\tabcolsep) * \real{0.1600}}
  >{\raggedright\arraybackslash}p{(\linewidth - 10\tabcolsep) * \real{0.1900}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 10\tabcolsep) * \real{0.0900}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 10\tabcolsep) * \real{0.1400}}
  >{\raggedright\arraybackslash}p{(\linewidth - 10\tabcolsep) * \real{0.1300}}
  >{\raggedright\arraybackslash}p{(\linewidth - 10\tabcolsep) * \real{0.2900}}@{}}"""


# The dilution per-operator panel needs a wide operator column; equal
# widths split names such as ``double_encode``.
WIDE_6_DILUTION_SPEC = r"""\begin{longtable}[]{@{}
  >{\raggedright\arraybackslash}p{(\linewidth - 10\tabcolsep) * \real{0.2000}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 10\tabcolsep) * \real{0.1400}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 10\tabcolsep) * \real{0.1700}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 10\tabcolsep) * \real{0.1700}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 10\tabcolsep) * \real{0.1600}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 10\tabcolsep) * \real{0.1600}}@{}}"""


# The five-column attack-family panel needs a wide first column; equal-width
# columns force long family names to wrap onto four or five lines.
WIDE_5_FAMILY_SPEC = r"""\begin{longtable}[]{@{}
  >{\raggedright\arraybackslash}p{(\linewidth - 8\tabcolsep) * \real{0.4000}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 8\tabcolsep) * \real{0.1500}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 8\tabcolsep) * \real{0.1500}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 8\tabcolsep) * \real{0.1500}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 8\tabcolsep) * \real{0.1500}}@{}}"""

# Nine-column tables put a policy or threshold label in the third column.
# The default equal-width split is too narrow for labels such as
# ``threshold_0.5``; the numeric columns can give up some width.
WIDE_9_SPEC = r"""\begin{longtable}[]{@{}
  >{\raggedright\arraybackslash}p{(\linewidth - 16\tabcolsep) * \real{0.1500}}
  >{\raggedright\arraybackslash}p{(\linewidth - 16\tabcolsep) * \real{0.0700}}
  >{\raggedright\arraybackslash}p{(\linewidth - 16\tabcolsep) * \real{0.1000}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 16\tabcolsep) * \real{0.0900}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 16\tabcolsep) * \real{0.1500}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 16\tabcolsep) * \real{0.0700}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 16\tabcolsep) * \real{0.0700}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 16\tabcolsep) * \real{0.0700}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 16\tabcolsep) * \real{0.1000}}@{}}"""


# The two appendix evidence tables put a long feature identifier in the first
# column and short verdict columns after it.  Equal widths wrap every
# identifier at its underscores.
WIDE_7_FEATURE_SPEC = r"""\begin{longtable}[]{@{}
  >{\raggedright\arraybackslash}p{(\linewidth - 12\tabcolsep) * \real{0.2600}}
  >{\raggedright\arraybackslash}p{(\linewidth - 12\tabcolsep) * \real{0.1300}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 12\tabcolsep) * \real{0.1200}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 12\tabcolsep) * \real{0.1200}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 12\tabcolsep) * \real{0.1200}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 12\tabcolsep) * \real{0.1200}}
  >{\raggedright\arraybackslash}p{(\linewidth - 12\tabcolsep) * \real{0.1300}}@{}}"""

# The multivariate appendix table has two long interval columns; the
# univariate split above wraps every confidence interval onto three lines.
WIDE_7_MULTI_SPEC = r"""\begin{longtable}[]{@{}
  >{\raggedright\arraybackslash}p{(\linewidth - 12\tabcolsep) * \real{0.1600}}
  >{\raggedright\arraybackslash}p{(\linewidth - 12\tabcolsep) * \real{0.2800}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 12\tabcolsep) * \real{0.0650}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 12\tabcolsep) * \real{0.2000}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 12\tabcolsep) * \real{0.0800}}
  >{\raggedleft\arraybackslash}p{(\linewidth - 12\tabcolsep) * \real{0.1150}}
  >{\raggedright\arraybackslash}p{(\linewidth - 12\tabcolsep) * \real{0.1000}}@{}}"""


def _break_texttt(text: str) -> str:
    """Allow line breaks inside long monospaced identifiers.

    Feature names and repository paths contain underscores, slashes, and dots
    but no spaces.  TeX treats them as single unbreakable words, which is the
    main source of overfull lines in the PDF.  Insert an explicit breakpoint
    after each separator; the separator is still printed.
    """
    def replace(match: re.Match[str]) -> str:
        body = match.group(1)
        body = body.replace("\\_", "\\_\\allowbreak{}")
        body = body.replace("/", "/\\allowbreak{}")
        body = body.replace(".", ".\\allowbreak{}")
        body = body.replace(",", ",\\allowbreak{}")
        # CamelCase identifiers such as NoPromotionWithoutCanary are otherwise
        # single unbreakable words and overflow the margin in dense paragraphs.
        body = re.sub(r"(?<=[a-z])(?=[A-Z])", r"\\allowbreak{}", body)
        return "\\texttt{" + body + "}"

    return re.sub(r"\\texttt\{([^{}]*)\}", replace, text)


def _convert_simple_columns(text: str) -> str:
    """Give simple ``l/c/r`` longtables fixed-width, wrapping columns.

    Pandoc uses single-line columns when the Markdown table is narrow.  A long
    identifier in such a column cannot wrap and pushes the table past the
    margin.  Fixed-width columns with the same alignment preserve the layout
    while allowing the existing ragged-right/left settings to break lines.
    """
    def replace(match: re.Match[str]) -> str:
        spec = match.group(1)
        count = len(spec)
        gap = 2 * (count - 1)
        width = (
            f"(\\linewidth - {gap}\\tabcolsep) * "
            f"\\real{{{1.0 / count:.4f}}}"
        )
        alignments = {
            "l": "\\raggedright",
            "c": "\\centering",
            "r": "\\raggedleft",
        }
        columns = [
            ">{" + alignments[column] + "\\arraybackslash}p{" + width + "}"
            for column in spec
        ]
        return (
            "\\begin{longtable}[]{@{}\n  "
            + "\n  ".join(columns)
            + "@{}}"
        )

    return SIMPLE_SPEC.sub(replace, text)


def _tabularize_uncaptioned(text: str) -> str:
    """Set short uncaptioned panels as ordinary tabulars.

    This longtable version calls ``\\refstepcounter{table}`` at every
    ``\\begin{longtable}``, even when no caption follows.  Decrementing the
    counter afterwards keeps caption numbers sequential but makes hyperref
    reuse an anchor, so the PDF reports ``Object @table.N already defined``.
    The uncaptioned panels are short enough to fit on one page; a tabular does
    not touch the table counter and avoids both problems.
    """
    pieces: list[str] = []
    cursor = 0
    for match in TABLE_BLOCK.finditer(text):
        block = match.group(0)
        if "\\caption{" in block:
            pieces.append(text[cursor:match.end()])
        else:
            block = block.replace(
                "\\begin{longtable}[]{", "\\noindent\\begin{tabular}{", 1
            )
            block = block.replace("\\end{longtable}", "\\end{tabular}", 1)
            block = block.replace("\\noalign{}", "")
            # Pandoc wraps header cells in a minipage sized to \linewidth.
            # Inside a longtable that equals the column width, but inside a
            # tabular \linewidth is the outer text width, so the minipage
            # overflows the column.  The p-column spec already carries the
            # alignment, so the wrapper can be removed.
            block = re.sub(
                r"\\begin\{minipage\}\[[tb]\]\{\\linewidth\}"
                r"(?:\\(?:raggedright|raggedleft|centering))?\s*",
                "",
                block,
            )
            block = block.replace("\\end{minipage}", "")
            block = re.sub(
                r"\\endfirsthead.*?\\endhead\s*", "", block, flags=re.DOTALL
            )
            block = re.sub(
                r"\\endhead\s*\\bottomrule\s*\\endlastfoot\s*", "", block
            )
            block = block.replace(
                "\\end{tabular}", "\\bottomrule\n\\end{tabular}", 1
            )
            pieces.append(text[cursor:match.start()])
            pieces.append(block)
        cursor = match.end()
    pieces.append(text[cursor:])
    return "".join(pieces)


def _layout_tables(text: str) -> str:
    """Set table font size and column spacing by table width.

    Wide tables are the second source of margin overflow.  The font sizes
    match the Word build (7 pt for the 14-column appendix table, 8 pt for
    nine-or-more-column tables).  Each table is wrapped in a group so the
    spacing change cannot leak into the surrounding prose.
    """
    pieces: list[str] = []
    cursor = 0
    for match in TABLE_BLOCK.finditer(text):
        block = match.group(0)
        top = block.find("\\toprule")
        if top < 0:
            columns = 0
        else:
            row_end = block.find("\\\\", top)
            header = block[top:row_end] if row_end >= 0 else block[top:]
            columns = header.count("&") + 1

        if columns >= 14:
            block = re.sub(
                r"\\begin\{longtable\}\[\]\{@\{\}.*?@\{\}\}",
                lambda _: WIDE_14_SPEC,
                block,
                count=1,
                flags=re.DOTALL,
            )
            font = "\\fontsize{7}{8.4}\\selectfont"
            spacing = "2pt"
        elif columns == 5 and "family & full clean" in block:
            block = re.sub(
                r"\\begin\{longtable\}\[\]\{@\{\}.*?@\{\}\}",
                lambda _: WIDE_5_FAMILY_SPEC,
                block,
                count=1,
                flags=re.DOTALL,
            )
            font = "\\small"
            spacing = None
        elif columns == 7 and ("zero clean" in block or "perm. imp." in block):
            spec = (
                WIDE_7_MULTI_SPEC
                if "perm. imp." in block
                else WIDE_7_FEATURE_SPEC
            )
            block = re.sub(
                r"\\begin\{longtable\}\[\]\{@\{\}.*?@\{\}\}",
                lambda _: spec,
                block,
                count=1,
                flags=re.DOTALL,
            )
            font = "\\scriptsize"
            spacing = "2pt"
        elif columns == 9:
            block = re.sub(
                r"\\begin\{longtable\}\[\]\{@\{\}.*?@\{\}\}",
                lambda _: WIDE_9_SPEC,
                block,
                count=1,
                flags=re.DOTALL,
            )
            font = "\\scriptsize"
            spacing = "2pt"
        elif columns == 10:
            font = "\\fontsize{7}{8.4}\\selectfont"
            spacing = "2pt"
        elif columns == 6 and "clean / attack" in block:
            block = re.sub(
                r"\\begin\{longtable\}\[\]\{@\{\}.*?@\{\}\}",
                lambda _: WIDE_6_DATASET_SPEC,
                block,
                count=1,
                flags=re.DOTALL,
            )
            font = "\\footnotesize"
            spacing = "3pt"
        elif columns == 6 and "v3-D evaded" in block:
            block = re.sub(
                r"\\begin\{longtable\}\[\]\{@\{\}.*?@\{\}\}",
                lambda _: WIDE_6_DILUTION_SPEC,
                block,
                count=1,
                flags=re.DOTALL,
            )
            font = "\\scriptsize"
            spacing = "2pt"
        elif columns == 6 and "C1/C2/C3" in block:
            block = re.sub(
                r"\\begin\{longtable\}\[\]\{@\{\}.*?@\{\}\}",
                lambda _: WIDE_6_V3D_SPEC,
                block,
                count=1,
                flags=re.DOTALL,
            )
            font = "\\scriptsize"
            spacing = "2pt"
        elif columns == 4 and "Gate B accepted" in block:
            block = re.sub(
                r"\\begin\{longtable\}\[\]\{@\{\}.*?@\{\}\}",
                lambda _: WIDE_4_COST_SPEC,
                block,
                count=1,
                flags=re.DOTALL,
            )
            font = "\\small"
            spacing = None
        elif columns >= 8:
            font = "\\scriptsize"
            spacing = "2pt"
        elif columns >= 6:
            font = "\\scriptsize"
            spacing = "3pt"
        elif columns == 5:
            font = "\\small"
            spacing = None
        else:
            font = None
            spacing = None

        if font is not None and top >= 0:
            prefix = "\\begingroup" + font
        else:
            prefix = "\\begingroup"
        if spacing is not None:
            prefix += "\\setlength{\\tabcolsep}{" + spacing + "}"
        block = prefix + "\n" + block + "\n\\endgroup"
        # The 14-column tables use fixed-width columns that sum to \linewidth,
        # so they fit in portrait.  A landscape environment changed the text
        # block for the following pages and left most of a page blank; it is
        # deliberately not used here.

        pieces.append(text[cursor:match.start()])
        pieces.append(block)
        cursor = match.end()
    pieces.append(text[cursor:])
    return "".join(pieces)


def _repeat_table_headers(text: str) -> str:
    """Keep the header on continuation pages without repeating the caption.

    Pandoc emits one ``\\endhead`` block.  longtable repeats everything before
    ``\\endhead``, including the caption, on every page.  Split the head into a
    first-page head (with caption) and a continuation head (without caption).
    """
    pieces: list[str] = []
    cursor = 0
    for match in TABLE_BLOCK.finditer(text):
        block = match.group(0)
        if "\\caption{" in block and "\\endfirsthead" not in block:
            top = block.find("\\toprule")
            endhead = block.find("\\endhead", top)
            if top >= 0 and endhead >= 0:
                head = block[top:endhead]
                block = (
                    block[:top]
                    + head
                    + "\\endfirsthead\n"
                    + head
                    + "\\endhead"
                    + block[endhead + len("\\endhead"):]
                )
        pieces.append(text[cursor:match.start()])
        pieces.append(block)
        cursor = match.end()
    pieces.append(text[cursor:])
    return "".join(pieces)


def _mask_alt(text: str) -> str:
    """Blank alt={...} spans without shifting string offsets."""
    return re.sub(r"alt=\{[^}]*\}", lambda m: " " * len(m.group(0)), text)


def _caption_span(text: str, prefix: str) -> tuple[int, int]:
    matches = list(re.finditer(r"\\caption\{" + re.escape(prefix), text))
    if len(matches) != 1:
        raise SystemExit(
            f"expected exactly one caption starting {prefix!r}, found {len(matches)}"
        )
    opening = matches[0].start() + len("\\caption")
    closing = _matching_brace(text, opening)
    if closing < 0:
        raise SystemExit(f"unbalanced caption starting {prefix!r}")
    return opening, closing


def _add_table_labels(text: str) -> str:
    for prefix, label in TABLE_FLOATS:
        _, closing = _caption_span(text, prefix)
        tag = "\\label{" + label + "}"
        if tag in text:
            continue
        text = text[:closing + 1] + tag + text[closing + 1:]
    return text


def _check_float_labels(text: str) -> None:
    for floats in (TABLE_FLOATS, FIGURE_FLOATS):
        for prefix, label in floats:
            _, closing = _caption_span(text, prefix)
            tail = text[closing + 1:closing + 10 + len(label)]
            if not tail.startswith("\\label{" + label + "}"):
                raise SystemExit(
                    f"caption {prefix!r} is not followed by \\label{{{label}}}"
                )


def _replace_float_refs(text: str) -> str:
    for kind, order in (("Table", TABLE_REF_ORDER), ("Figure", FIGURE_REF_ORDER)):
        masked = _mask_alt(text)
        matches = list(re.finditer(kind + r"\s+\d+", masked))
        if len(matches) != len(order):
            raise SystemExit(
                f"expected {len(order)} in-text {kind} references, found {len(matches)}"
            )
        for match, key in reversed(list(zip(matches, order))):
            text = (
                text[:match.start()]
                + kind
                + "~\\ref{"
                + key
                + "}"
                + text[match.end():]
            )
    return text


def _check_float_refs(text: str) -> None:
    if len(re.findall(r"\\begin\{longtable\}", text)) != len(TABLE_FLOATS):
        raise SystemExit("table count changed; update TABLE_FLOATS and the references")
    if len(re.findall(r"\\begin\{figure\}", text)) != len(FIGURE_FLOATS):
        raise SystemExit("figure count changed; update FIGURE_FLOATS and the references")
    labels = re.findall(r"\\label\{([^}]*)\}", text)
    if len(labels) != len(set(labels)):
        raise SystemExit("duplicate float labels")
    refs = set(re.findall(r"\\ref\{([^}]*)\}", text))
    missing = refs - set(labels)
    if missing:
        raise SystemExit(f"references to missing labels: {sorted(missing)}")
    if len(re.findall(r"\\ref\{tab:", text)) != len(TABLE_REF_ORDER):
        raise SystemExit("table reference count changed")
    if len(re.findall(r"\\ref\{fig:", text)) != len(FIGURE_REF_ORDER):
        raise SystemExit("figure reference count changed")
    leftover = re.findall(r"(?:Table|Figure)\s+\d+", _mask_alt(text))
    if leftover:
        raise SystemExit(f"literal float references remain: {leftover[:5]}")


def postprocess_tex(path: Path) -> None:
    """Move bold table captions into their first longtable.

    Pandoc emits a numbered caption written as a separate bold paragraph as
    ordinary text, so the longtables would compile without captions and the
    table counter would never advance.  Each caption is attached to the next
    longtable; a multi-panel table keeps one numbered caption on its first
    panel.  The ``LTcaptype=none`` guard is removed so that ``\\caption``
    increments the table counter.
    """
    text = path.read_text(encoding="utf-8")
    # The Markdown source numbers figures in the alt text so that Word shows a
    # number; LaTeX supplies its own "Figure N:" prefix, so strip the manual one.
    text = re.sub(r"\\caption\{Figure\s+\d+\.\s*", r"\\caption{", text)
    # The docx build needs raster images, but the typeset PDF should embed the
    # vector versions that sit next to them.
    text = re.sub(
        r"(\\includegraphics(?:\[[^\]]*\])?\{[^}]+)\.png\}",
        r"\1.pdf}",
        text,
    )
    text = text.replace("\\textless=", "$\\le$").replace("\\textgreater=", "$\\ge$")
    # The Markdown table headers use raw Greek letters; XeTeX's default text
    # font does not contain them, so typeset them as math.
    text = text.replace("δ", "$\\delta$").replace("Δ", "$\\Delta$")
    # The Word build needs the affiliation and corresponding-author lines after
    # the author block; the LaTeX frontmatter already carries them in \address,
    # \ead and \cortext, so drop the duplicates.
    text = re.sub(r"\\emph\{Department of [^{}]*\}\s*", "", text)
    text = re.sub(r"\\emph\{Corresponding author:[^{}]*\}\s*", "", text)

    captions: list[tuple[int, int, str]] = []
    cursor = 0
    pattern = re.compile(r"\\textbf\{(Table\s+\d+\.)")
    while True:
        match = pattern.search(text, cursor)
        if match is None:
            break
        opening = match.start() + len("\\textbf")
        closing = _matching_brace(text, opening)
        if closing < 0:
            raise SystemExit("unbalanced table caption in TeX output")
        captions.append((match.start(), closing, text[opening + 1:closing]))
        cursor = closing + 1

    for start, end, caption in reversed(captions):
        table = re.search(r"\\begin\{longtable\}", text[end:])
        if table is None:
            raise SystemExit(f"no longtable after caption: {caption[:40]}")
        table_start = end + table.start()
        rule = re.search(r"\\toprule", text[table_start:])
        if rule is None:
            raise SystemExit(f"no toprule in table after caption: {caption[:40]}")
        insert_at = table_start + rule.start()
        # longtable's \caption supplies the "Table N:" prefix itself.
        body = re.sub(r"^Table\s+\d+\.\s*", "", caption)
        text = (
            text[:insert_at]
            + "\\caption{" + body + "}\\\\\n"
            + text[insert_at:]
        )
        text = text[:start] + text[end + 1:]

    # Pandoc guards every uncaptioned longtable so that it does not consume a
    # table number.  A table that now carries an injected \caption must step
    # the counter; an uncaptioned panel must not.  Remove the guard only from
    # captioned tables so numbers stay sequential and hyperref anchors unique.
    guarded = re.compile(
        r"\{\\def\\LTcaptype\{none\} % do not increment counter\n"
        r"(\\begin\{longtable\}.*?\\end\{longtable\})",
        re.DOTALL,
    )

    def unguard(match: re.Match[str]) -> str:
        block = match.group(1)
        if "\\caption{" in block:
            return "{\n" + block
        return match.group(0)

    text = guarded.sub(unguard, text)

    # Pandoc copies the Markdown image width (6.4 in) into the TeX source; that
    # is wider than the elsarticle preprint text block.  Let LaTeX fit the
    # figure to the line instead.
    text = text.replace("width=6.4in,height=\\textheight,keepaspectratio",
                        "width=\\linewidth,height=\\textheight,keepaspectratio")
    text = _break_texttt(text)
    text = _convert_simple_columns(text)
    # Bullet lists in elsarticle are justified against a narrow measure and
    # contain long identifiers; ragged-right keeps them inside the margin.
    text = text.replace("\\begin{itemize}\n", "\\begin{itemize}\\raggedright\n")
    text = _repeat_table_headers(text)
    text = _layout_tables(text)
    text = _tabularize_uncaptioned(text)
    # Keep the gate-plus-CRS table on one page; the other new tables already
    # fit without a forced break and would leave large gaps if moved.
    for marker, lines in (("Gate plus CRS fusion", 16),):
        caption_at = text.find("\\caption{" + marker)
        if caption_at < 0:
            continue
        table_at = text.rfind("\\begin{longtable}", 0, caption_at)
        if table_at >= 0:
            text = (
                text[:table_at]
                + "\\needspace{" + str(lines) + "\\baselineskip}\n"
                + text[table_at:]
            )
    # Keep a multi-panel table's panel label with the panel it introduces.
    text = re.sub(
        r"(\\textbf\{Panel [A-Z]:[^}]*\})",
        r"\\needspace{9\\baselineskip}\n\1",
        text,
    )
    text = text.replace("\\begin{minipage}[b]", "\\begin{minipage}[t]")

    text = _add_table_labels(text)
    _check_float_labels(text)
    text = _replace_float_refs(text)
    _check_float_refs(text)

    path.write_text(text, encoding="utf-8")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--stem", default="NATRIX_manuscript")
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--reference-doc", type=Path, default=REFERENCE)
    parser.add_argument("--csl", type=Path, default=PAPER / "elsevier-vancouver.csl")
    args = parser.parse_args()

    source = args.source if args.source.is_absolute() else ROOT / args.source
    if not source.exists():
        raise SystemExit(f"missing {source}")
    stem = args.stem
    template = args.template if args.template.is_absolute() else ROOT / args.template
    reference = (
        args.reference_doc
        if args.reference_doc.is_absolute()
        else ROOT / args.reference_doc
    )
    csl = args.csl if args.csl.is_absolute() else ROOT / args.csl

    BUILD.mkdir(parents=True, exist_ok=True)
    expanded = BUILD / f"{stem}_expanded.md"
    expanded.write_text(expand(source.read_text(encoding="utf-8")),
                        encoding="utf-8")

    common = [
        "pandoc", str(expanded.relative_to(ROOT)),
        "--from", "markdown+pipe_tables+tex_math_dollars+footnotes",
        "--bibliography", str(BIB.relative_to(ROOT)),
        "--resource-path", ".:figures:paper",
    ]

    run(common + [
        "--citeproc",
        "--csl", str(csl.relative_to(ROOT)),
        "--reference-doc", str(reference.relative_to(ROOT)),
        "--number-sections",
        "--output", str((PAPER / f"{stem}.docx").relative_to(ROOT)),
    ])

    run(common + [
        "--natbib",
        "--template", str(template.relative_to(ROOT)),
        "--output", str((PAPER / f"{stem}.tex").relative_to(ROOT)),
    ])

    postprocess_docx(PAPER / f"{stem}.docx", source_keywords(source))
    postprocess_tex(PAPER / f"{stem}.tex")

    print(f"built paper/{stem}.docx and paper/{stem}.tex")


if __name__ == "__main__":
    main()
