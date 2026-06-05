from __future__ import annotations

import re
from collections import defaultdict

import fitz

from .models import ContentUnit, TextSpan, WatermarkCandidate

_WPS_IMAGE_ARTIFACT_RE = re.compile(rb"/KSPE\d+\s+gs[\s\S]*/KSPX\d+\s+Do")


def _is_light_color(color: int) -> bool:
    red = (color >> 16) & 255
    green = (color >> 8) & 255
    blue = color & 255
    return red >= 180 and green >= 180 and blue >= 180


def find_unit_watermark_candidates(units: list[ContentUnit], page_count: int) -> list[WatermarkCandidate]:
    candidates: list[WatermarkCandidate] = []

    artifact_units = [unit for unit in units if unit.kind == "artifact" and unit.is_watermark_artifact]
    if artifact_units:
        pages = sorted({unit.page for unit in artifact_units})
        page_ratio = len(pages) / max(page_count, 1)
        confidence = min(0.99, 0.7 + page_ratio * 0.25)
        candidates.append(
            WatermarkCandidate(
                id="artifact:watermark",
                kind="artifact",
                label="PDF Watermark Artifact",
                pages=pages,
                occurrence_count=len(artifact_units),
                confidence=round(confidence, 3),
                can_auto_remove=confidence >= 0.85,
                reason=f"检测到 PDF Watermark Artifact，跨 {len(pages)} 页出现 {len(artifact_units)} 次。",
            )
        )

    grouped_xobjects: dict[tuple[int, str], list[ContentUnit]] = defaultdict(list)
    for unit in units:
        if unit.kind == "xobject" and unit.resource_name and unit.resource_xref is not None:
            grouped_xobjects[(unit.resource_xref, unit.resource_name)].append(unit)

    min_pages = max(2, min(page_count, 3))
    for (resource_xref, resource_name), matches in grouped_xobjects.items():
        pages = sorted({unit.page for unit in matches})
        if len(pages) < min_pages:
            continue
        page_ratio = len(pages) / max(page_count, 1)
        confidence = min(0.9, 0.45 + page_ratio * 0.45)
        if confidence < 0.85:
            continue
        candidates.append(
            WatermarkCandidate(
                id=f"xobject:{resource_xref}",
                kind="xobject",
                label=f"重复 XObject {resource_name}",
                pages=pages,
                occurrence_count=len(matches),
                confidence=round(confidence, 3),
                can_auto_remove=False,
                reason=f"检测到重复 XObject 调用，跨 {len(pages)} 页出现 {len(matches)} 次；需要预览确认后删除。",
            )
        )

    return sorted(candidates, key=lambda item: item.confidence, reverse=True)


def find_wps_watermark_candidate(doc: fitz.Document) -> WatermarkCandidate | None:
    from .content_units import extract_document_units

    units = extract_document_units(doc)
    wps_units = [
        unit
        for unit in units
        if unit.kind == "artifact" and unit.is_watermark_artifact and _WPS_IMAGE_ARTIFACT_RE.search(unit.data)
    ]
    if not wps_units:
        return None

    pages = sorted({unit.page for unit in wps_units})
    page_ratio = len(pages) / max(doc.page_count, 1)
    confidence = min(0.99, 0.7 + page_ratio * 0.25)
    return WatermarkCandidate(
        id="image:wps-watermark",
        kind="image",
        label="WPS 图片水印",
        pages=pages,
        occurrence_count=len(wps_units),
        confidence=round(confidence, 3),
        can_auto_remove=confidence >= 0.85,
        reason=f"检测到 WPS Watermark artifact，跨 {len(pages)} 页重复，并使用重复图片对象。",
    )

def find_repeated_text_candidates(spans: list[TextSpan], page_count: int) -> list[WatermarkCandidate]:
    grouped: dict[str, list[TextSpan]] = defaultdict(list)
    for item in spans:
        text = "".join(item.text.split())
        if text:
            grouped[text].append(item)

    candidates: list[WatermarkCandidate] = []
    min_pages = max(2, min(page_count, 3))

    for text, matches in grouped.items():
        pages = sorted({item.page for item in matches})
        if len(pages) < min_pages:
            continue

        avg_size = sum(item.size for item in matches) / len(matches)
        light_ratio = sum(1 for item in matches if _is_light_color(item.color)) / len(matches)
        repeated_ratio = len(pages) / max(page_count, 1)

        if avg_size < 30 or light_ratio < 0.8:
            continue

        confidence = min(0.99, 0.45 + repeated_ratio * 0.35 + min(avg_size / 120, 1) * 0.15 + light_ratio * 0.2)
        can_auto_remove = confidence >= 0.85
        reason = f"文本跨 {len(pages)} 页重复，平均字号 {avg_size:.1f}，浅色比例 {light_ratio:.0%}。"

        candidates.append(
            WatermarkCandidate(
                id=f"text:{text}",
                kind="text",
                label=text,
                pages=pages,
                occurrence_count=len(matches),
                confidence=round(confidence, 3),
                can_auto_remove=can_auto_remove,
                reason=reason,
            )
        )

    return sorted(candidates, key=lambda item: item.confidence, reverse=True)
