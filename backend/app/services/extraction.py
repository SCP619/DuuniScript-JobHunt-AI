"""Local text extraction for PDF, DOCX, TXT and Markdown.

Extracted text is untrusted data. It is stored for review and later fact extraction;
nothing in it is ever executed or treated as an instruction.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from app.persistence.models import ExtractionStatus
from app.services.file_types import decode_text

logger = logging.getLogger("duuniscript.extraction")

EXTRACTOR_VERSION = "3"
PDF_MAX_PAGES = 300
MAX_EXTRACTED_CHARS = 2_000_000


@dataclass(frozen=True)
class ExtractionResult:
    status: ExtractionStatus
    text: str = ""
    error: str | None = None
    method: str | None = None  # "text" (read from the file) or "ocr" (recognised from images)


def extract_text(path: Path, extension: str) -> ExtractionResult:
    method = "text"
    try:
        if extension in (".png", ".jpg"):
            method = "ocr"
            text = _image(path)
        elif extension == ".pdf":
            text, method = _pdf(path)
        elif extension == ".docx":
            text = _docx(path)
        else:
            decoded = decode_text(path.read_bytes())
            if decoded is None:
                return ExtractionResult(ExtractionStatus.FAILED, error="unsupported_encoding")
            text = _html(decoded) if extension == ".html" else decoded
    except _ExtractionError as exc:
        return ExtractionResult(ExtractionStatus.FAILED, error=exc.code, method=method)
    except Exception as exc:  # noqa: BLE001 - parsers raise many types on malformed input
        logger.warning("Extraction failed: %s", type(exc).__name__)
        return ExtractionResult(ExtractionStatus.FAILED, error="parse_error", method=method)

    text = _normalize(text)[:MAX_EXTRACTED_CHARS]
    if not text.strip():
        # A photo without writing, or a scan OCR could not read.
        return ExtractionResult(ExtractionStatus.NO_TEXT, method=method)
    return ExtractionResult(ExtractionStatus.SUCCEEDED, text=text, method=method)


class _ExtractionError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _image(path: Path) -> str:
    from app.services import ocr

    try:
        return ocr.image_text(path.read_bytes())
    except ocr.OcrUnavailable as exc:
        raise _ExtractionError(str(exc)) from exc


def _pdf(path: Path) -> tuple[str, str]:
    from pypdf import PdfReader

    reader = PdfReader(str(path), strict=False)
    if reader.is_encrypted:
        try:
            if not reader.decrypt(""):
                raise _ExtractionError("encrypted")
        except _ExtractionError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise _ExtractionError("encrypted") from exc
    if len(reader.pages) > PDF_MAX_PAGES:
        raise _ExtractionError("too_many_pages")
    fonts: set[str] = set()
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
        fonts |= _font_names(page)
    text = clean_pdf_text("\n\n".join(pages), fonts)
    if text.strip():
        return text, "text"
    # No text layer: a scanned PDF. Read its page images with OCR when available.
    from app.services import ocr

    if not ocr.available():
        return "", "text"
    return ocr.pdf_images_text(reader), "ocr"


def _font_names(page) -> set[str]:  # noqa: ANN001 - pypdf PageObject
    try:
        resources = page.get("/Resources") or {}
        font_dict = resources.get("/Font") or {}
        names = set()
        for ref in font_dict.values():
            font = ref.get_object()
            descriptor = font.get("/FontDescriptor")
            descriptor = descriptor.get_object() if descriptor is not None else {}
            # Type 3 fonts (used by some browsers' PDF export) name the font only in the descriptor.
            names.add(str(font.get("/BaseFont") or descriptor.get("/FontName") or ""))
        return names
    except Exception:  # noqa: BLE001 - damaged resources only lose the font names
        return set()


# Inter (a common CV font) draws case-sensitive and tabular alternates of digits and
# punctuation that have no Unicode value; PDF printers then map them to private-use code
# points. Checked against real CVs exported with Inter (2026-11-10). Used only when an Inter
# font is in the PDF, because other fonts use the same private code points differently.
INTER_ALTERNATES = {
    **{0xE071 + digit: str(digit) for digit in range(10)},
    0xE081: "(",
    0xE082: ")",
    0xE088: "-",
    0xE089: "\u2013",  # en dash
    0xE094: ".",
    0xE09D: "+",
    0xE09F: "\u00d7",  # multiplication sign
}
LIGATURES = {0xFB00: "ff", 0xFB01: "fi", 0xFB02: "fl", 0xFB03: "ffi", 0xFB04: "ffl", 0xFB05: "st", 0xFB06: "st"}
# Icon fonts (Font Awesome, Material Icons) use this private range for pictures, not text.
_ICONS = re.compile("[\uf000-\uf8ff]")
_PRIVATE = re.compile("[\ue000-\uf8ff]")


def clean_pdf_text(text: str, font_names: set[str]) -> str:
    """Undo PDF text artefacts: ligatures, Inter alternates, icon glyphs.

    Remaining private-use characters cannot be read and become U+FFFD, so the text shows that
    something is missing instead of silently dropping it (e.g. a digit in a date).
    """
    if any("inter" in name.lower().split("+")[-1][:6] for name in font_names):
        text = text.translate(INTER_ALTERNATES)
    text = text.translate(LIGATURES)
    text = _ICONS.sub(" ", text)
    return _PRIVATE.sub("\ufffd", text)


def _html(markup: str) -> str:
    """Visible text of an HTML page (e.g. a CV web page). Scripts and styles are dropped."""
    from app.adapters.job_sources.jsonld import html_to_text

    # CV pages often show skills or contact items as separate inline elements ("tags"); keep
    # them apart. Formatting elements (b, i, strong, em) are left alone so words stay whole.
    markup = re.sub(r"(?i)(</(?:span|a|td|th|label|button|small|code|time|dt|dd)\s*>)", r"\1 ", markup)
    markup = re.sub(r"(?i)(<a\s)", r" \1", markup)
    return html_to_text(markup) or ""


def _docx(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.append("\t".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip() + "\n"
