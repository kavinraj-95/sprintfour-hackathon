"""Tests for the raster (scanned-document) path.

The decisive test is `test_pixel_redaction_leaves_nothing_recoverable`: it proves
the raster warning is honoured — after redaction there is no extractable text and
no image data under the boxes. The rest cover page classification and the
OCR -> detection -> box-mapping wiring.
"""
from __future__ import annotations

import glob
import io

import fitz
import pytesseract
import pytest
from PIL import Image, ImageDraw, ImageFont

from services import raster
from services.detection import regex_layer

# OCR-friendly synthetic page content. The phone is the value we track end to end.
_PHONE = "0412 887 905"
_LINES = [
    "CONFIDENTIAL CLAIM NOTE",
    "Claimant contact details below.",
    f"Phone number: {_PHONE}",
    "Please file under the usual reference.",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for cand in (
        "/usr/share/fonts/Adwaita/AdwaitaSans-Regular.ttf",
        *glob.glob("/usr/share/fonts/**/NotoSans-Regular.ttf", recursive=True),
        *glob.glob("/usr/share/fonts/**/LiberationSans-Regular.ttf", recursive=True),
    ):
        try:
            return ImageFont.truetype(cand, size)
        except OSError:
            continue
    pytest.skip("no usable TrueType font found for rendering an OCR test page")


def _scanned_page_image() -> Image.Image:
    """Render the lines to a clean white image — a stand-in for a scanned page."""
    img = Image.new("RGB", (1100, 360), "white")
    draw = ImageDraw.Draw(img)
    font = _font(34)
    y = 30
    for line in _LINES:
        draw.text((40, y), line, fill="black", font=font)
        y += 70
    return img


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ----------------------------------------------------- 1. classification ----
def test_classifies_digital_vs_raster_and_force_ocr() -> None:
    # A digital-text page (real text layer).
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), f"Claimant phone {_PHONE} on file.", fontsize=12)
    digital_pdf = doc.tobytes()
    doc.close()

    kinds = raster.classify_pdf_pages(digital_pdf)
    assert kinds[0].kind == "digital" and kinds[0].extractable_chars > 0

    # force_ocr overrides the text layer -> raster.
    forced = raster.classify_pdf_pages(digital_pdf, force_ocr=True)
    assert forced[0].kind == "raster"

    # An image-only page (no text layer) -> raster.
    img = _scanned_page_image()
    doc = fitz.open()
    page = doc.new_page(width=img.width, height=img.height)
    page.insert_image(fitz.Rect(0, 0, img.width, img.height), stream=_png_bytes(img))
    raster_pdf = doc.tobytes()
    doc.close()
    assert raster.classify_pdf_pages(raster_pdf)[0].kind == "raster"


# ---------------------------------------- 2-3. OCR feeds the SAME pipeline ----
def test_ocr_text_runs_through_the_existing_detection_layer() -> None:
    ocr = raster.ocr_image(_scanned_page_image())
    assert _PHONE in ocr.text, f"OCR did not read the phone; got: {ocr.text!r}"

    # The reconstructed OCR text goes through the SAME regex layer as digital text.
    spans = regex_layer.detect(ocr.text)
    assert any(s.type.value == "PHONE" for s in spans), "pipeline missed the OCR'd phone"


# --------------------------------------------- 4. PROOF of pixel redaction ----
def test_pixel_redaction_leaves_nothing_recoverable() -> None:
    img = _scanned_page_image()
    ocr = raster.ocr_image(img)
    spans = [s for s in regex_layer.detect(ocr.text) if s.type.value == "PHONE"]
    assert spans, "no phone detected to redact"

    boxes = raster.boxes_for_spans(ocr, spans)
    assert boxes, "detected span mapped to no pixel box"

    out_png = raster.redact_image_pixels(img, boxes)
    out_img = Image.open(io.BytesIO(out_png)).convert("RGB")

    # (a) No recoverable TEXT: re-OCR the whole output; the phone is gone.
    reocr = pytesseract.image_to_string(out_img)
    assert _PHONE not in reocr
    digits = _PHONE.replace(" ", "")
    assert digits not in reocr.replace(" ", "")

    # (b) No recoverable DATA: every redacted box is solid black in the output
    # (mean pixel ~0), so there is nothing underneath, not a cover on top.
    for (x0, y0, x1, y1) in boxes:
        crop = out_img.crop((x0, y0, x1, y1))
        pixels = list(crop.getdata())
        mean = sum(sum(p) for p in pixels) / (len(pixels) * 3)
        assert mean < 5.0, f"box {(x0, y0, x1, y1)} is not fully blacked out (mean={mean:.1f})"
