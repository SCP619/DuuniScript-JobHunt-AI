"""Render draft Markdown to DOCX and PDF, locally.

Only a small Markdown subset is understood, which is what the draft builder writes and what a
user needs when editing: ``# name``, ``## section``, ``### entry``, a whole line in ``*italics*``
(dates), ``- bullet`` lines and paragraphs. Anything else is printed as plain text; nothing in a
draft is ever interpreted as markup beyond that (no HTML, links or images).

PDF uses a Unicode TrueType font from the Windows font folder when one is available
(Calibri, Arial, Georgia or Segoe UI); otherwise the built-in Helvetica, with characters it
cannot draw replaced, so export never fails because of a font.
"""

from __future__ import annotations

import functools
import io
import os
import re
from dataclasses import dataclass
from pathlib import Path

from app.services.drafting import CV_TEMPLATES

RENDERER_VERSION = "render-1"


@dataclass(frozen=True)
class Block:
    kind: str  # title, heading, entry, meta, bullet, paragraph, blank
    text: str


def parse(markdown: str) -> list[Block]:
    blocks: list[Block] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            blocks.append(Block("paragraph", "\n".join(paragraph)))
            paragraph.clear()

    for raw in markdown.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            flush()
            if blocks and blocks[-1].kind != "blank":
                blocks.append(Block("blank", ""))
            continue
        for prefix, kind in (("### ", "entry"), ("## ", "heading"), ("# ", "title")):
            if stripped.startswith(prefix):
                flush()
                blocks.append(Block(kind, _inline(stripped[len(prefix):])))
                break
        else:
            if re.fullmatch(r"\*[^*].*\*", stripped) or re.fullmatch(r"_[^_].*_", stripped):
                flush()
                blocks.append(Block("meta", _inline(stripped[1:-1])))
            elif re.match(r"^[-*•]\s+", stripped):
                flush()
                blocks.append(Block("bullet", _inline(re.sub(r"^[-*•]\s+", "", stripped))))
            else:
                paragraph.append(_inline(stripped))
    flush()
    while blocks and blocks[-1].kind == "blank":
        blocks.pop()
    return blocks


def _inline(text: str) -> str:
    # Emphasis markers are dropped; everything else is kept as typed.
    return re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)


def plain_text(markdown: str) -> str:
    """Draft as plain text (e.g. for an email body or a form's text box)."""
    out: list[str] = []
    for block in parse(markdown):
        if block.kind == "blank":
            out.append("")
        elif block.kind == "bullet":
            out.append(f"• {block.text}")
        elif block.kind == "heading":
            out.append(block.text.upper())
        else:
            out.append(block.text)
    return "\n".join(out).strip() + "\n"


# ---------- Styles ----------


@dataclass(frozen=True)
class Style:
    font_files: tuple[str, str, str]  # regular, bold, italic (Windows font file names)
    docx_font: str
    base_size: float
    title_size: float
    heading_size: float
    accent: tuple[int, int, int]


STYLES = {
    "utu_rekry": Style(("calibri.ttf", "calibrib.ttf", "calibrii.ttf"), "Calibri", 10.5, 18, 12, (0, 92, 158)),
    "utu_rekry_fi": Style(("calibri.ttf", "calibrib.ttf", "calibrii.ttf"), "Calibri", 10.5, 18, 12, (0, 92, 158)),
    "classic": Style(("georgia.ttf", "georgiab.ttf", "georgiai.ttf"), "Georgia", 10.5, 20, 12.5, (40, 40, 40)),
    "compact": Style(("calibri.ttf", "calibrib.ttf", "calibrii.ttf"), "Calibri", 10, 17, 11.5, (25, 70, 120)),
    "projects_first": Style(("arial.ttf", "arialbd.ttf", "ariali.ttf"), "Arial", 10, 18, 12, (20, 90, 80)),
    "letter": Style(("calibri.ttf", "calibrib.ttf", "calibrii.ttf"), "Calibri", 11, 13, 11, (0, 0, 0)),
}
FALLBACK_FONTS = (
    ("arial.ttf", "arialbd.ttf", "ariali.ttf"),
    ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf"),
)


def style_for(template: str | None, kind: str, cv_template: str | None = None) -> Style:
    """CV style by template. A cover letter uses the CV's font (the UTU guide: the CV and the
    application are a pair, use the same font in both) at letter sizes."""
    if kind == "cover_letter":
        letter = STYLES["letter"]
        cv = STYLES[cv_template] if cv_template in CV_TEMPLATES else None
        if cv is None:
            return letter
        return Style(cv.font_files, cv.docx_font, letter.base_size, letter.title_size, letter.heading_size, letter.accent)
    return STYLES[template] if template in CV_TEMPLATES else STYLES["classic"]


def _font_dir() -> Path | None:
    windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
    if not windir:
        return None
    path = Path(windir) / "Fonts"
    return path if path.is_dir() else None


def _font_paths(style: Style, font_dir: Path | None) -> tuple[Path, Path, Path] | None:
    if font_dir is None:
        return None
    for files in (style.font_files, *FALLBACK_FONTS):
        paths = tuple(font_dir / name for name in files)
        if all(p.is_file() for p in paths):
            return paths  # type: ignore[return-value]
    return None


# ---------- DOCX ----------


def to_docx(markdown: str, style: Style) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor

    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = style.docx_font
    normal.font.size = Pt(style.base_size)
    for section in doc.sections:
        section.left_margin = section.right_margin = Pt(54)
        section.top_margin = section.bottom_margin = Pt(48)
    color = RGBColor(*style.accent)

    def para(text: str, *, size: float | None = None, bold: bool = False, italic: bool = False,
             space_before: float = 0, space_after: float = 2, rgb=None, bullet: bool = False):  # noqa: ANN001, ANN202
        p = doc.add_paragraph(style="List Bullet" if bullet else None)
        p.paragraph_format.space_before = Pt(space_before)
        p.paragraph_format.space_after = Pt(space_after)
        lines = text.split("\n")
        for i, line in enumerate(lines):
            run = p.add_run(line)
            run.bold = bold
            run.italic = italic
            run.font.name = style.docx_font
            if size:
                run.font.size = Pt(size)
            if rgb is not None:
                run.font.color.rgb = rgb
            if i < len(lines) - 1:
                run.add_break()
        return p

    for block in parse(markdown):
        if block.kind == "title":
            p = para(block.text, size=style.title_size, bold=True, rgb=color, space_after=2)
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        elif block.kind == "heading":
            para(block.text.upper(), size=style.heading_size, bold=True, rgb=color, space_before=10, space_after=3)
        elif block.kind == "entry":
            para(block.text, bold=True, space_before=5, space_after=0)
        elif block.kind == "meta":
            para(block.text, italic=True, space_after=1, rgb=RGBColor(90, 90, 90))
        elif block.kind == "bullet":
            para(block.text, bullet=True, space_after=1)
        elif block.kind == "paragraph":
            para(block.text, space_after=4)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


# ---------- PDF ----------


def to_pdf(markdown: str, style: Style, *, font_dir: Path | None = None, use_system_fonts: bool = True) -> bytes:
    return bytes(_render_pdf(markdown, style, font_dir=font_dir, use_system_fonts=use_system_fonts).output())


@functools.lru_cache(maxsize=256)
def pdf_pages(markdown: str, style: Style) -> int:
    """How many A4 pages the draft takes as PDF (cached: drafts are checked on every read)."""
    return _render_pdf(markdown, style).pages_count


def _render_pdf(markdown: str, style: Style, *, font_dir: Path | None = None, use_system_fonts: bool = True):  # noqa: ANN202
    from fpdf import FPDF

    pdf = FPDF(format="A4", unit="pt")
    pdf.set_margins(54, 48, 54)
    pdf.set_auto_page_break(True, margin=48)
    pdf.set_creator("DuuniScript")
    paths = _font_paths(style, font_dir or _font_dir()) if use_system_fonts else None
    if paths:
        family = "Body"
        pdf.add_font(family, "", str(paths[0]))
        pdf.add_font(family, "B", str(paths[1]))
        pdf.add_font(family, "I", str(paths[2]))
        safe = lambda text: text  # noqa: E731
    else:
        family = "helvetica"
        safe = _latin1  # built-in fonts only cover Latin-1
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin
    base = style.base_size
    line = base * 1.35

    def write(text: str, *, size: float, emphasis: str = "", rgb=(0, 0, 0), before: float = 0, after: float = 2,
              indent: float = 0) -> None:  # noqa: ANN001
        pdf.set_font(family, emphasis, size)
        pdf.set_text_color(*rgb)
        if before:
            pdf.ln(before)
        pdf.set_x(pdf.l_margin + indent)
        pdf.multi_cell(width - indent, size * 1.35, safe(text), align="L", new_x="LMARGIN", new_y="NEXT")
        if after:
            pdf.ln(after)

    for block in parse(markdown):
        if block.kind == "title":
            write(block.text, size=style.title_size, emphasis="B", rgb=style.accent, after=2)
        elif block.kind == "heading":
            write(block.text.upper(), size=style.heading_size, emphasis="B", rgb=style.accent, before=8, after=0)
            y = pdf.get_y() + 1
            pdf.set_draw_color(*style.accent)
            pdf.set_line_width(0.6)
            pdf.line(pdf.l_margin, y, pdf.l_margin + width, y)
            pdf.ln(4)
        elif block.kind == "entry":
            write(block.text, size=base, emphasis="B", before=3, after=0)
        elif block.kind == "meta":
            write(block.text, size=base - 0.5, emphasis="I", rgb=(90, 90, 90), after=1)
        elif block.kind == "bullet":
            pdf.set_font(family, "", base)
            pdf.set_text_color(0, 0, 0)
            pdf.set_x(pdf.l_margin + 4)
            pdf.cell(10, line, safe("•") if paths else "-")
            write(block.text, size=base, indent=14, after=1)
        elif block.kind == "paragraph":
            write(block.text, size=base, after=3)
        elif block.kind == "blank":
            pdf.ln(line * 0.35)
    return pdf


_REPLACEMENTS = {"–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"',
                 "•": "-", "…": "...", "·": "·", "−": "-", "×": "x"}


def _latin1(text: str) -> str:
    text = "".join(_REPLACEMENTS.get(ch, ch) for ch in text)
    return text.encode("latin-1", "replace").decode("latin-1")
