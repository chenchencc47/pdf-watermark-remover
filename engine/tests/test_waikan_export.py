from pathlib import Path

import fitz
import pytest

from pdf_watermark_remover.content_units import extract_document_units
from pdf_watermark_remover.detect import find_unit_watermark_candidates
from pdf_watermark_remover.remove import remove_text_watermarks


WAIKAN_SAMPLE = Path(r"E:/study/单词/外刊阅读/讲义及笔记/27外刊阅读第二篇讲义【外刊课程讲义】(1).pdf")


pytestmark = pytest.mark.skipif(
    not WAIKAN_SAMPLE.exists(),
    reason="External waikan handout sample is not available on this machine.",
)


def _normalized_page_text(doc: fitz.Document, page_index: int) -> str:
    return "".join(doc[page_index].get_text("text").split())


def _page_sizes(doc: fitz.Document) -> list[tuple[float, float]]:
    return [(round(page.rect.width, 2), round(page.rect.height, 2)) for page in doc]


def _link_count(doc: fitz.Document) -> int:
    return sum(len(page.get_links()) for page in doc)


def _watermark_artifact_count(doc: fitz.Document) -> int:
    count = 0
    for page in doc:
        count += page.read_contents().count(b"/Subtype/Watermark")
    return count


def test_waikan_watermark_artifact_is_detected_as_an_auto_candidate():
    with fitz.open(WAIKAN_SAMPLE) as doc:
        candidates = find_unit_watermark_candidates(extract_document_units(doc), doc.page_count)

    assert candidates
    candidate = candidates[0]
    assert candidate.id == "artifact:watermark"
    assert candidate.kind == "artifact"
    assert candidate.occurrence_count == 8
    assert candidate.can_auto_remove is True


def test_waikan_watermark_artifact_is_removed_without_removing_document_content(tmp_path):
    output = tmp_path / "waikan.no-watermark.pdf"

    removed = remove_text_watermarks(str(WAIKAN_SAMPLE), str(output), ["artifact:watermark"])

    assert removed == 8
    with fitz.open(WAIKAN_SAMPLE) as original, fitz.open(output) as exported:
        assert _watermark_artifact_count(original) == 8
        assert _watermark_artifact_count(exported) == 0
        assert exported.page_count == original.page_count
        assert _page_sizes(exported) == _page_sizes(original)
        assert _link_count(exported) == _link_count(original)

        changed_pages = []
        for page_index in range(original.page_count):
            if _normalized_page_text(exported, page_index) != _normalized_page_text(original, page_index):
                changed_pages.append(page_index + 1)

        assert changed_pages == []
