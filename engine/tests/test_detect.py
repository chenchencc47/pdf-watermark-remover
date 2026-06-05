from pdf_watermark_remover.detect import find_repeated_text_candidates, find_wps_watermark_candidate
from pdf_watermark_remover.models import TextSpan


def span(page: int, text: str, size: float, color: int, bbox=(10.0, 10.0, 200.0, 100.0)) -> TextSpan:
    return TextSpan(page=page, text=text, size=size, color=color, bbox=bbox)


def test_repeated_large_light_text_becomes_auto_candidate():
    spans = [
        span(1, "VolkaEnglish", 86.2, 15264493),
        span(2, "VolkaEnglish", 86.2, 15264493),
        span(3, "VolkaEnglish", 86.2, 15264493),
        span(1, "Daily life", 12.0, 0),
        span(2, "School and time", 12.0, 0),
    ]

    result = find_repeated_text_candidates(spans=spans, page_count=3)

    assert len(result) == 1
    candidate = result[0]
    assert candidate.id == "text:VolkaEnglish"
    assert candidate.label == "VolkaEnglish"
    assert candidate.kind == "text"
    assert candidate.occurrence_count == 3
    assert candidate.confidence >= 0.85
    assert candidate.can_auto_remove is True


def test_normal_repeated_small_black_text_is_not_auto_candidate():
    spans = [
        span(1, "Chapter", 12.0, 0),
        span(2, "Chapter", 12.0, 0),
        span(3, "Chapter", 12.0, 0),
    ]

    result = find_repeated_text_candidates(spans=spans, page_count=3)

    assert result == []


def test_wps_legacy_helper_ignores_generic_watermark_artifacts():
    class FakePage:
        def get_contents(self):
            return [7]

        def get_images(self, full=True):
            return []

    class FakeDoc:
        page_count = 1

        def __iter__(self):
            return iter([FakePage()])

        def xref_stream(self, xref):
            assert xref == 7
            return b"/Artifact <</Subtype/Watermark/Type/Pagination>> BDC q /Logo Do Q EMC"

    assert find_wps_watermark_candidate(FakeDoc()) is None
