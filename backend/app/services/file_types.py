"""Allowed upload types, verified by content signature rather than client-supplied MIME type."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from app.core.errors import AppError

# DOCX archive safety limits (zip-bomb protection).
DOCX_MAX_ENTRIES = 2_000
DOCX_MAX_UNCOMPRESSED = 200 * 1_048_576
DOCX_MAX_RATIO = 200

TEXT_ENCODINGS = ("utf-8-sig", "utf-16")


@dataclass(frozen=True)
class FileType:
    extension: str
    mime_type: str


FILE_TYPES: dict[str, FileType] = {
    ".pdf": FileType(".pdf", "application/pdf"),
    ".docx": FileType(".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ".txt": FileType(".txt", "text/plain; charset=utf-8"),
    ".md": FileType(".md", "text/markdown; charset=utf-8"),
    ".html": FileType(".html", "text/html; charset=utf-8"),
    ".png": FileType(".png", "image/png"),
    ".jpg": FileType(".jpg", "image/jpeg"),
}
IMAGE_TYPES = (".png", ".jpg")
_HTML_START = ("<!doctype html", "<html", "<head", "<body", "<!--")


def sanitize_filename(raw: str | None) -> str:
    """Strip any directory part and control characters; keep a readable display name."""
    name = PureWindowsPath(raw or "").name  # handles both / and \ separators
    name = re.sub(r"[\x00-\x1f\x7f<>:\"|?*]", "", name).strip().strip(".")
    return name[:255] or "document"


def file_type_for(filename: str) -> FileType:
    ext = Path(filename).suffix.lower()
    if ext == ".markdown":
        ext = ".md"
    elif ext == ".htm":
        ext = ".html"
    elif ext == ".jpeg":
        ext = ".jpg"
    file_type = FILE_TYPES.get(ext)
    if file_type is None:
        raise AppError(
            415,
            "unsupported_file_type",
            "Only PDF, DOCX, TXT, Markdown, HTML, PNG and JPEG files are accepted.",
            {"allowed": sorted(FILE_TYPES)},
        )
    return file_type


def decode_text(data: bytes) -> str | None:
    if b"\x00" in data and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return None
    for encoding in TEXT_ENCODINGS:
        if encoding == "utf-16" and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
            continue
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def check_docx_archive(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = {i.filename for i in infos}
            if "word/document.xml" not in names or "[Content_Types].xml" not in names:
                raise _mismatch()
            if len(infos) > DOCX_MAX_ENTRIES:
                raise AppError(422, "unsafe_archive", "The DOCX file has too many internal parts.")
            total = sum(i.file_size for i in infos)
            compressed = sum(i.compress_size for i in infos) or 1
            if total > DOCX_MAX_UNCOMPRESSED or total / compressed > DOCX_MAX_RATIO:
                raise AppError(422, "unsafe_archive", "The DOCX file expands to an unsafe size.")
    except zipfile.BadZipFile as exc:
        raise _mismatch() from exc


def verify_signature(path: Path, file_type: FileType) -> None:
    """Raise if the stored bytes do not match the declared extension."""
    with path.open("rb") as handle:
        head = handle.read(8)
    if file_type.extension == ".pdf":
        if not head.startswith(b"%PDF-"):
            raise _mismatch()
    elif file_type.extension == ".docx":
        if not head.startswith(b"PK\x03\x04"):
            raise _mismatch()
        check_docx_archive(path)
    elif file_type.extension == ".png":
        if not head.startswith(b"\x89PNG\r\n\x1a\n"):
            raise _mismatch()
        check_image(path)
    elif file_type.extension == ".jpg":
        if not head.startswith(b"\xff\xd8\xff"):
            raise _mismatch()
        check_image(path)
    else:
        text = decode_text(path.read_bytes())
        if text is None:
            raise AppError(
                422, "unsupported_encoding", "Text files must be UTF-8 (or UTF-16 with a byte-order mark)."
            )
        if file_type.extension == ".html" and not text.lstrip().lower().startswith(_HTML_START):
            raise _mismatch()


def check_image(path: Path) -> None:
    """The image must open and stay under the pixel limit (decompression-bomb protection)."""
    from PIL import Image

    from app.services.ocr import MAX_PIXELS

    # The size is read from the header before any pixels are decoded; Pillow's global limit is
    # left alone (changing it would affect every other image use in the process).
    try:
        with Image.open(path) as image:
            width, height = image.size
            if width * height > MAX_PIXELS:
                raise AppError(422, "image_too_large", "The image has too many pixels.")
            image.verify()
    except AppError:
        raise
    except Image.DecompressionBombError as exc:
        raise AppError(422, "image_too_large", "The image has too many pixels.") from exc
    except Exception as exc:  # noqa: BLE001 - any decoder error means a broken file
        raise _mismatch() from exc
    if width * height > MAX_PIXELS:
        raise AppError(422, "image_too_large", "The image has too many pixels.")


def _mismatch() -> AppError:
    return AppError(422, "file_content_mismatch", "The file content does not match its file type.")
