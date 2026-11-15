"""Images and scanned PDFs read with the Windows OCR engine. Synthetic images only."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.services import ocr

needs_ocr = pytest.mark.skipif(not ocr.available(), reason="Windows OCR engine not available")


def _text_image(lines: list[str], fmt: str = "PNG", size: tuple[int, int] = (1400, 420)) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 44)
    except OSError:
        font = ImageFont.load_default()
    for i, line in enumerate(lines):
        draw.text((60, 60 + i * 100), line, fill="black", font=font)
    out = io.BytesIO()
    image.save(out, fmt)
    return out.getvalue()


def _blank_image(fmt: str = "JPEG") -> bytes:
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (800, 600), (120, 160, 200)).save(out, fmt)
    return out.getvalue()


def _scanned_pdf(png: bytes) -> bytes:
    """A PDF whose only page content is an image (no text layer), like a scanner makes."""
    from fpdf import FPDF

    pdf = FPDF(format="A4", unit="pt")
    pdf.add_page()
    pdf.image(io.BytesIO(png), x=20, y=20, w=550)
    return bytes(pdf.output())


def _upload(client: TestClient, name: str, data: bytes, mime: str):  # noqa: ANN202
    return client.post("/api/v1/documents", files={"file": (name, io.BytesIO(data), mime)}, data={"category": "certificate"})


@needs_ocr
def test_png_certificate_is_read(client: TestClient, profile: dict) -> None:
    response = _upload(client, "certificate.png", _text_image(["Certificate of Completion", "Example Data Course"]), "image/png")
    assert response.status_code == 201, response.text
    doc = response.json()
    assert doc["file_extension"] == ".png" and doc["mime_type"] == "image/png"
    assert doc["extraction_status"] == "succeeded" and doc["extraction_method"] == "ocr"
    assert doc["extractor_version"] == "3"
    text = client.get(f"/api/v1/documents/{doc['id']}/text").json()["text"]
    assert "Certificate of Completion" in text and "Example Data Course" in text


@needs_ocr
def test_jpeg_alias_and_photo_without_text(client: TestClient, profile: dict) -> None:
    doc = _upload(client, "photo.jpeg", _blank_image(), "image/jpeg").json()
    assert doc["file_extension"] == ".jpg"
    assert doc["extraction_status"] == "no_text" and doc["extraction_method"] == "ocr"


@needs_ocr
def test_scanned_pdf_is_read_with_ocr(client: TestClient, profile: dict) -> None:
    pdf = _scanned_pdf(_text_image(["Transcript of Records", "Example University"]))
    doc = _upload(client, "scan.pdf", pdf, "application/pdf").json()
    assert doc["extraction_status"] == "succeeded" and doc["extraction_method"] == "ocr"
    assert "Transcript of Records" in client.get(f"/api/v1/documents/{doc['id']}/text").json()["text"]


def test_text_pdf_is_not_ocred(client: TestClient, profile: dict) -> None:
    from tests.files import make_pdf

    doc = _upload(client, "cv.pdf", make_pdf(), "application/pdf").json()
    assert doc["extraction_method"] == "text"


def test_without_ocr_images_fail_softly(client: TestClient, profile: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr, "available", lambda: False)
    doc = _upload(client, "certificate.png", _text_image(["Hello"]), "image/png").json()
    assert doc["extraction_status"] == "failed" and doc["extraction_error"] == "ocr_unavailable"
    from tests.files import make_pdf

    scan = _upload(client, "scan.pdf", make_pdf(None), "application/pdf").json()
    assert scan["extraction_status"] == "no_text"


@pytest.mark.parametrize(
    ("name", "data", "code"),
    [
        ("fake.png", b"MZ not an image at all", "file_content_mismatch"),
        ("fake.jpg", b"\x89PNG\r\n\x1a\n but the wrong type", "file_content_mismatch"),
        ("broken.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "file_content_mismatch"),
    ],
)
def test_bad_images_are_refused(client: TestClient, profile: dict, name: str, data: bytes, code: str) -> None:
    response = _upload(client, name, data, "image/png")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


def test_decompression_bomb_is_refused(client: TestClient, profile: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr, "MAX_PIXELS", 10_000)
    response = _upload(client, "big.png", _text_image(["x"], size=(400, 400)), "image/png")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "image_too_large"
