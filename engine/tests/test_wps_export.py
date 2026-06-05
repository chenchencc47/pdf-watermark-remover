from pathlib import Path

import fitz

from pdf_watermark_remover.detect import find_wps_watermark_candidate
from pdf_watermark_remover.remove import remove_text_watermarks


ROOT = Path(__file__).resolve().parents[3]
CLEAN_SAMPLE = ROOT / "3000 Textbook.no-watermark.pdf"
WPS_SAMPLE = Path(r"C:/Users/10263/Desktop/3000 Textbook.no-watermark_加水印.pdf")


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


def test_wps_image_watermark_is_detected_as_an_auto_candidate():
    assert WPS_SAMPLE.exists()

    with fitz.open(WPS_SAMPLE) as doc:
        candidate = find_wps_watermark_candidate(doc)

    assert candidate is not None
    assert candidate.id == "image:wps-watermark"
    assert candidate.kind == "image"
    assert candidate.label == "WPS 图片水印"
    assert candidate.occurrence_count == 364
    assert candidate.can_auto_remove is True


def test_wps_image_watermark_is_removed_without_removing_document_content(tmp_path):
    assert CLEAN_SAMPLE.exists()
    assert WPS_SAMPLE.exists()
    output = tmp_path / "wps.no-watermark.pdf"

    removed = remove_text_watermarks(str(WPS_SAMPLE), str(output), ["image:wps-watermark"])

    assert removed == 364
    with fitz.open(WPS_SAMPLE) as wps, fitz.open(output) as exported:
        assert _watermark_artifact_count(wps) == 364
        assert _watermark_artifact_count(exported) == 0
        assert exported.page_count == wps.page_count
        assert _page_sizes(exported) == _page_sizes(wps)
        assert _link_count(exported) == _link_count(wps)

        changed_pages = []
        for page_index in range(wps.page_count):
            if _normalized_page_text(exported, page_index) != _normalized_page_text(wps, page_index):
                changed_pages.append(page_index + 1)

        assert changed_pages == []
