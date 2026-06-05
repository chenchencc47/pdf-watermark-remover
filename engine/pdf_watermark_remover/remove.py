from __future__ import annotations

import re

import fitz

from .content_units import extract_units_from_stream

_VOLKA_ENGLISH_BLOCK = re.compile(
    rb"q\s*\n"
    rb"(?:0 0 612 792 re\s*\nW\* n\s*\nq\s*\n)?"
    rb"\.53218216 -\.53218281 \.53117019 \.53116953 72\.124512 555\.6\d+ cm\s*\n"
    rb"\.9098 \.9176 \.9294 RG \.9098 \.9176 \.9294 rg\s*\n"
    rb"/G3 gs\s*\n"
    rb"BT\s*\n"
    rb"/F9 114\.666664 Tf\s*\n"
    rb"1 0 0 -1 0 0 Tm\s*\n"
    rb"(?:[-.0-9]+ [-.0-9]+ Td <[0-9A-F]+> Tj\s*\n){12}"
    rb"ET\s*\n"
    rb"Q\s*\n"
    rb"(?:Q\s*\n)?"
)

_WPS_IMAGE_ARTIFACT_RE = re.compile(rb"/KSPE\d+\s+gs[\s\S]*/KSPX\d+\s+Do")


def _candidate_value(candidate_id: str, kind: str) -> str:
    prefix = f"{kind}:"
    if not candidate_id.startswith(prefix):
        raise ValueError(f"Unsupported candidate id: {candidate_id}")
    return candidate_id.removeprefix(prefix)


def _remove_volka_english_blocks(doc: fitz.Document, page: fitz.Page) -> int:
    removed = 0
    for xref in page.get_contents():
        stream = doc.xref_stream(xref)
        updated, count = _VOLKA_ENGLISH_BLOCK.subn(b"", stream)
        if count:
            doc.update_stream(xref, updated)
            removed += count
    return removed


def remove_unit_watermark_artifacts_from_page(doc, page, *, wps_only: bool = False) -> int:
    from .content_units import extract_units_from_stream

    page_number = page.number + 1
    removed = 0
    for xref in page.get_contents():
        stream = doc.xref_stream(xref)
        artifact_units = [
            unit
            for unit in extract_units_from_stream(stream, page_number=page_number, stream_xref=xref)
            if unit.kind == "artifact"
            and unit.is_watermark_artifact
            and (not wps_only or _WPS_IMAGE_ARTIFACT_RE.search(unit.data))
        ]
        if not artifact_units:
            continue

        updated = bytearray(stream)
        for unit in sorted(artifact_units, key=lambda item: item.start, reverse=True):
            del updated[unit.start : unit.end]
            removed += 1
        doc.update_stream(xref, bytes(updated))
    return removed


def _page_image_xrefs(page) -> dict[str, int]:
    image_xrefs: dict[str, int] = {}
    for image in page.get_images(full=True):
        if len(image) > 7:
            image_xrefs[str(image[7])] = int(image[0])
    return image_xrefs


def _remove_xobject_units_from_page(doc: fitz.Document, page: fitz.Page, target_values: set[str]) -> int:
    removed = 0
    page_number = page.number + 1
    image_xrefs = _page_image_xrefs(page)
    for xref in page.get_contents():
        stream = doc.xref_stream(xref)
        selected_units = []
        for unit in extract_units_from_stream(stream, page_number=page_number, stream_xref=xref):
            if unit.kind != "xobject":
                continue
            resource_xref = image_xrefs.get(unit.resource_name or "")
            if resource_xref is not None and str(resource_xref) in target_values:
                selected_units.append(unit)
        if not selected_units:
            continue

        updated = bytearray(stream)
        for unit in sorted(selected_units, key=lambda item: item.start, reverse=True):
            del updated[unit.start : unit.end]
            removed += 1
        doc.update_stream(xref, bytes(updated))
    return removed


def remove_text_watermarks(pdf_path: str, output_path: str, candidate_ids: list[str]) -> int:
    doc = fitz.open(pdf_path)
    try:
        removed = 0
        target_texts = [_candidate_value(candidate_id, "text") for candidate_id in candidate_ids if candidate_id.startswith("text:")]
        target_images = [_candidate_value(candidate_id, "image") for candidate_id in candidate_ids if candidate_id.startswith("image:")]
        target_artifacts = [_candidate_value(candidate_id, "artifact") for candidate_id in candidate_ids if candidate_id.startswith("artifact:")]
        target_xobjects = {_candidate_value(candidate_id, "xobject") for candidate_id in candidate_ids if candidate_id.startswith("xobject:")}
        invalid_xobjects = [candidate_id for candidate_id in candidate_ids if candidate_id.startswith("xobject:") and not _candidate_value(candidate_id, "xobject").isdigit()]
        if invalid_xobjects:
            raise ValueError(f"Unsupported xobject candidate id: {invalid_xobjects[0]}")

        unsupported = [candidate_id for candidate_id in candidate_ids if not candidate_id.startswith(("text:", "image:", "artifact:", "xobject:"))]
        if unsupported:
            raise ValueError(f"Unsupported candidate id: {unsupported[0]}")

        for page in doc:
            if "VolkaEnglish" in target_texts:
                removed += _remove_volka_english_blocks(doc, page)
            if "watermark" in target_artifacts:
                removed += remove_unit_watermark_artifacts_from_page(doc, page)
            elif "wps-watermark" in target_images:
                removed += remove_unit_watermark_artifacts_from_page(doc, page, wps_only=True)
            if target_xobjects:
                removed += _remove_xobject_units_from_page(doc, page, target_xobjects)

        doc.save(output_path, garbage=4, clean=True, deflate=True)
        return removed
    finally:
        doc.close()
