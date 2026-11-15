"""Text from images with the OCR engine built into Windows (Windows.Media.Ocr).

Local and free: no model download, nothing leaves the computer. It recognises the languages
installed in Windows (Settings > Time & language > Language); add Finnish there to read Finnish
text well. On other systems, or without the ``winrt`` packages, OCR is reported as unavailable
and the document keeps the ``no_text`` / ``failed`` status it would have had before.

Images are opened with Pillow under a pixel limit (decompression bombs are refused), turned
upright from their EXIF orientation, resized into the engine's range and passed as PNG.
"""

from __future__ import annotations

import asyncio
import io
import logging

logger = logging.getLogger("duuniscript.ocr")

MAX_PIXELS = 60_000_000
MIN_SIDE = 1600  # small images are enlarged: the engine reads small print poorly
MAX_PAGES = 30


class OcrUnavailable(Exception):
    pass


def available() -> bool:
    try:
        from winrt.windows.media.ocr import OcrEngine  # noqa: F401
    except Exception:  # noqa: BLE001 - not Windows or packages missing
        return False
    return True


def _prepare(data: bytes) -> bytes:
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(data)) as image:
        if image.width * image.height > MAX_PIXELS:
            raise ValueError("image has too many pixels")
        image = ImageOps.exif_transpose(image)
        image = image.convert("L")  # greyscale reads as well and is smaller
        try:
            from winrt.windows.media.ocr import OcrEngine

            limit = int(OcrEngine.max_image_dimension)
        except Exception:  # noqa: BLE001
            limit = 10_000
        longest = max(image.size)
        if longest > limit:
            scale = limit / longest
        elif longest < MIN_SIDE:
            scale = min(3.0, MIN_SIDE / longest)
        else:
            scale = 1.0
        if scale != 1.0:
            image = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.LANCZOS)
        out = io.BytesIO()
        image.save(out, format="PNG")
        return out.getvalue()


async def _recognize(png: bytes) -> str:
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        raise OcrUnavailable("no_ocr_language")
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(png)
    await writer.store_async()
    writer.detach_stream()
    stream.seek(0)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    result = await engine.recognize_async(bitmap)
    return "\n".join(line.text for line in result.lines)


def image_text(data: bytes) -> str:
    """OCR one image (PNG, JPEG, or an image taken from a PDF page)."""
    if not available():
        raise OcrUnavailable("ocr_unavailable")
    png = _prepare(data)
    return asyncio.run(_recognize(png))


def pdf_images_text(reader) -> str:  # noqa: ANN001 - pypdf PdfReader
    """OCR the page images of a scanned PDF (one large image per page is typical)."""
    if not available():
        raise OcrUnavailable("ocr_unavailable")
    pages = []
    for number, page in enumerate(reader.pages):
        if number >= MAX_PAGES:
            break
        texts = []
        try:
            images = list(page.images)
        except Exception:  # noqa: BLE001 - unreadable image streams are skipped
            images = []
        for image in images:
            try:
                texts.append(image_text(image.data))
            except OcrUnavailable:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("OCR skipped an image: %s", type(exc).__name__)
        pages.append("\n".join(t for t in texts if t.strip()))
    return "\n\n".join(pages)
