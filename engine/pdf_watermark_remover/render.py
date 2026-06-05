from __future__ import annotations

import base64
import tempfile
from pathlib import Path

import fitz

from .remove import remove_text_watermarks


def render_page_png_base64(pdf_path: str, page_number: int, zoom: float = 1.5) -> str:
    doc = fitz.open(pdf_path)
    page = doc[page_number - 1]
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    data = pixmap.tobytes("png")
    doc.close()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def render_preview(pdf_path: str, candidate_ids: list[str], page_number: int) -> dict[str, object]:
    before = render_page_png_base64(pdf_path, page_number)
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_pdf = str(Path(tmpdir) / "preview.pdf")
        remove_text_watermarks(pdf_path, temp_pdf, candidate_ids)
        after = render_page_png_base64(temp_pdf, page_number)
    return {"page": page_number, "beforePng": before, "afterPng": after}
