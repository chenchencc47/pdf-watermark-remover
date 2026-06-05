from __future__ import annotations

import fitz

from .models import PageSize, PdfInfo, TextSpan


def inspect_document(doc, pdf_path: str) -> tuple[PdfInfo, list[TextSpan]]:
    page_sizes: list[PageSize] = []
    spans: list[TextSpan] = []

    for page_index, page in enumerate(doc, start=1):
        rect = page.rect
        page_sizes.append(PageSize(page=page_index, width=round(rect.width, 2), height=round(rect.height, 2)))
        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    bbox = tuple(round(float(value), 2) for value in span.get("bbox", (0, 0, 0, 0)))
                    spans.append(
                        TextSpan(
                            page=page_index,
                            text=text,
                            size=round(float(span.get("size", 0)), 2),
                            color=int(span.get("color", 0)),
                            bbox=bbox,
                        )
                    )

    info = PdfInfo(
        path=pdf_path,
        page_count=doc.page_count,
        encrypted=doc.needs_pass,
        has_text=bool(spans),
        page_sizes=page_sizes,
    )
    return info, spans


def inspect_pdf(pdf_path: str) -> tuple[PdfInfo, list[TextSpan]]:
    doc = fitz.open(pdf_path)
    try:
        return inspect_document(doc, pdf_path)
    finally:
        doc.close()
