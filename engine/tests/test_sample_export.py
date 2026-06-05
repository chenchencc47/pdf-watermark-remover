from pathlib import Path

import fitz

from pdf_watermark_remover.remove import remove_text_watermarks


ROOT = Path(__file__).resolve().parents[3]
SAMPLE = ROOT / "3000 Textbook.pdf"


def _normalized_page_text(doc: fitz.Document, page_index: int) -> str:
    return "".join(doc[page_index].get_text("text").split())


def _page_sizes(doc: fitz.Document) -> list[tuple[float, float]]:
    return [(round(page.rect.width, 2), round(page.rect.height, 2)) for page in doc]


def _link_count(doc: fitz.Document) -> int:
    return sum(len(page.get_links()) for page in doc)


def test_sample_export_removes_watermark_without_removing_body_text_or_links(tmp_path):
    assert SAMPLE.exists()
    output = tmp_path / "sample.no-watermark.pdf"

    removed = remove_text_watermarks(str(SAMPLE), str(output), ["text:VolkaEnglish"])

    assert removed == 363
    with fitz.open(SAMPLE) as original, fitz.open(output) as exported:
        assert exported.page_count == original.page_count
        assert _page_sizes(exported) == _page_sizes(original)
        assert _link_count(exported) == _link_count(original)

        changed_pages = []
        for page_index in range(original.page_count):
            original_text = _normalized_page_text(original, page_index)
            if page_index > 0:
                original_text = original_text.replace("VolkaEnglish", "")
            exported_text = _normalized_page_text(exported, page_index)
            if original_text != exported_text:
                changed_pages.append(page_index + 1)

        assert changed_pages == []
