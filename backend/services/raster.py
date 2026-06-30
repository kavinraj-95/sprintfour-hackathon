"""The raster (scanned-document) path.

The non-negotiable rule (see `redaction-vs-anonymization`, raster warning): for
an image page, REDACT means overwriting the box region in PIXELS and re-encoding
the image. An overlay drawn on top of still-present text/image data is NOT
redaction — it is the exact "covered but the data is still underneath" failure
the product exists to prevent.

Flow:
  1. classify_pdf_pages  — digital-text vs raster (near-zero extractable text),
     with a force_ocr override.
  2. ocr_image           — Tesseract -> reconstructed text + per-token pixel
     boxes, with a char-offset map so a detected span maps back to its tokens.
  3. (detection)         — the SAME pipeline runs over the reconstructed text;
     this module is detector-agnostic and just consumes the resulting spans.
  4. redact_image_pixels — paint the spans' token boxes solid and re-encode, so
     nothing is recoverable beneath them.

Digital-text pages do NOT come here; they use services.redaction (text path).
"""
from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import dataclass, field

import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageDraw

from models.contract import Span

# A page with fewer than this many extractable characters is treated as raster
# (a scan/photo): there is essentially no text layer to work from.
_DIGITAL_TEXT_MIN_CHARS = 10

# Tesseract confidence floor — tokens below this are noise and get no box.
_MIN_TOKEN_CONFIDENCE = 0.0


@dataclass(frozen=True)
class PageKind:
    index: int
    kind: str  # "digital" | "raster"
    extractable_chars: int


@dataclass(frozen=True)
class Token:
    """One OCR word: its text, its char span in the reconstructed string, and
    its pixel box (left, top, right, bottom)."""

    text: str
    start: int
    end: int
    box: tuple[int, int, int, int]


@dataclass
class OcrResult:
    text: str                       # reconstructed reading-order text
    tokens: list[Token] = field(default_factory=list)


def classify_pdf_pages(pdf_bytes: bytes, *, force_ocr: bool = False) -> list[PageKind]:
    """Classify each PDF page as digital-text or raster.

    `force_ocr=True` marks every page raster regardless of its text layer — the
    override for documents whose embedded text is untrustworthy (bad scans saved
    with a garbage text layer, etc.).
    """
    out: list[PageKind] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            chars = 0 if force_ocr else len(page.get_text("text").strip())
            kind = "raster" if (force_ocr or chars < _DIGITAL_TEXT_MIN_CHARS) else "digital"
            out.append(PageKind(index=i, kind=kind, extractable_chars=chars))
    return out


def render_pdf_page_to_image(pdf_bytes: bytes, page_index: int, *, dpi: int = 200) -> Image.Image:
    """Rasterize one PDF page to a PIL image (for OCR + pixel redaction)."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        pix = doc[page_index].get_pixmap(dpi=dpi)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def ocr_image(image: Image.Image) -> OcrResult:
    """Run Tesseract and reconstruct reading-order text with per-token boxes.

    The reconstructed string is what detection runs on; each token records its
    char span in that string so a detected [start,end) maps back to pixel boxes.
    Tokens are joined by spaces within a line and newlines between lines, so
    multi-word values (e.g. a spaced phone number) read as one contiguous span.
    """
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    tokens: list[Token] = []
    pieces: list[str] = []
    cursor = 0
    prev_line_key: tuple[int, int, int] | None = None

    n = len(data["text"])
    for i in range(n):
        word = data["text"][i]
        if not word.strip():
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if conf < _MIN_TOKEN_CONFIDENCE:
            continue

        line_key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        if prev_line_key is None:
            sep = ""
        elif line_key != prev_line_key:
            sep = "\n"
        else:
            sep = " "
        if sep:
            pieces.append(sep)
            cursor += len(sep)
        prev_line_key = line_key

        left, top = data["left"][i], data["top"][i]
        w, h = data["width"][i], data["height"][i]
        start = cursor
        end = start + len(word)
        tokens.append(Token(text=word, start=start, end=end,
                            box=(left, top, left + w, top + h)))
        pieces.append(word)
        cursor = end

    return OcrResult(text="".join(pieces), tokens=tokens)


def boxes_for_spans(ocr: OcrResult, spans: Sequence[Span]) -> list[tuple[int, int, int, int]]:
    """Map detected char spans to the pixel boxes of the tokens they cover.

    A span covers every token whose char range overlaps it (so a value split
    across OCR tokens redacts all of its pieces, not just the first).
    """
    boxes: list[tuple[int, int, int, int]] = []
    for span in spans:
        for tok in ocr.tokens:
            if tok.start < span.end and span.start < tok.end:
                boxes.append(tok.box)
    return boxes


def redact_image_pixels(
    image: Image.Image,
    boxes: Sequence[tuple[int, int, int, int]],
    *,
    pad: int = 1,
) -> bytes:
    """Paint each box solid black and re-encode to PNG bytes.

    This is destructive on purpose: the pixels under each box are replaced, then
    the image is flattened to a fresh PNG. There is no layer to peel back and no
    text to extract — the only way to redact a raster page.
    """
    out = image.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    w, h = out.size
    for (x0, y0, x1, y1) in boxes:
        draw.rectangle(
            [max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)],
            fill=(0, 0, 0),
        )
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()
