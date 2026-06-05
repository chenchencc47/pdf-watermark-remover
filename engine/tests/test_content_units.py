from pdf_watermark_remover.content_units import extract_document_units, extract_units_from_stream
from pdf_watermark_remover.detect import find_unit_watermark_candidates
from pdf_watermark_remover.models import ContentUnit
from pdf_watermark_remover.remove import remove_text_watermarks, remove_unit_watermark_artifacts_from_page


def test_extracts_watermark_artifact_with_spaced_dictionary():
    stream = (
        b"0 0 0 RG\n"
        b"/Artifact <</Subtype/Watermark/Type/Pagination>> BDC\n"
        b"q 293.676 -293.676 -151.802 -151.802 232.682 643.703 cm\r"
        b"/KSPX1 Do Q\r"
        b"EMC\n"
        b"BT /F1 12 Tf (Body) Tj ET\n"
    )
    units = extract_units_from_stream(stream, page_number=1, stream_xref=7)
    assert len(units) == 2
    artifact = units[0]
    assert artifact.kind == "artifact"
    assert artifact.page == 1
    assert artifact.stream_xref == 7
    assert artifact.is_watermark_artifact is True
    assert artifact.resource_name == "KSPX1"
    assert artifact.data.startswith(b"/Artifact")
    assert artifact.data.rstrip().endswith(b"EMC")


def test_extracts_watermark_artifact_without_extra_spaces():
    stream = (
        b"/Artifact <</Subtype/Watermark/Type/Pagination>>BDC\n"
        b"q\n/KSPE9 gs\n"
        b"0.588544 0.214213 -0.214213 0.588544 119.712723 281.541199 cm\n"
        b"/KSPX8 Do\nQ\nEMC\n"
    )
    units = extract_units_from_stream(stream, page_number=3, stream_xref=13421)
    assert len(units) == 1
    artifact = units[0]
    assert artifact.kind == "artifact"
    assert artifact.page == 3
    assert artifact.stream_xref == 13421
    assert artifact.is_watermark_artifact is True
    assert artifact.resource_name == "KSPX8"


def test_text_object_ignores_et_inside_string_literal():
    stream = b"BT /F1 12 Tf (ET) Tj ET\nq /Im1 Do Q\n"

    units = extract_units_from_stream(stream, page_number=1, stream_xref=7)

    text_units = [unit for unit in units if unit.kind == "text"]
    assert len(text_units) == 1
    assert text_units[0].data == b"BT /F1 12 Tf (ET) Tj ET"


def test_extracts_each_xobject_call_in_one_graphics_block():
    stream = b"q /Im1 Do /Im2 Do Q\n"

    units = extract_units_from_stream(stream, page_number=1, stream_xref=7)

    xobject_units = [unit for unit in units if unit.kind == "xobject"]
    assert [unit.resource_name for unit in xobject_units] == ["Im1", "Im2"]


def test_extracts_minified_path_inside_graphics_block():
    stream = b"q 0 0 m 100 0 l S Q\n"

    units = extract_units_from_stream(stream, page_number=1, stream_xref=7)

    path_units = [unit for unit in units if unit.kind == "path"]
    assert len(path_units) == 1
    assert path_units[0].data == b"0 0 m 100 0 l S"


def test_extracts_nested_marked_content_inside_watermark_artifact():
    stream = (
        b"/Artifact <</Subtype/Watermark>> BDC\n"
        b"/Span <<>> BDC\n"
        b"q /Im1 Do Q\n"
        b"EMC\n"
        b"q /Im2 Do Q\n"
        b"EMC\n"
        b"BT /F1 12 Tf (Body) Tj ET\n"
    )

    units = extract_units_from_stream(stream, page_number=1, stream_xref=7)

    assert len(units) == 2
    artifact = units[0]
    assert artifact.kind == "artifact"
    assert artifact.is_watermark_artifact is True
    assert artifact.resource_name == "Im1"
    assert artifact.data.rstrip().endswith(b"q /Im2 Do Q\nEMC")


def test_extracts_document_unit_resource_xref_from_page_images():
    class FakePage:
        def get_contents(self):
            return [9]

        def get_images(self, full=True):
            assert full is True
            return [(42, 0, 120, 80, 8, "DeviceRGB", "", "Im12", "", 0)]

    class FakeDoc:
        def __iter__(self):
            return iter([FakePage()])

        def xref_stream(self, xref):
            assert xref == 9
            return b"q\n120 0 0 80 40 50 cm\n/Im12 Do\nQ\n"

    units = extract_document_units(FakeDoc())

    assert len(units) == 1
    assert units[0].resource_name == "Im12"
    assert units[0].resource_xref == 42


def test_extracts_plain_xobject_call():
    stream = b"q\n120 0 0 80 40 50 cm\n/Im12 Do\nQ\nBT /F1 12 Tf (Body) Tj ET\n"
    units = extract_units_from_stream(stream, page_number=2, stream_xref=9)
    assert len(units) == 2
    xobject = units[0]
    assert xobject.kind == "xobject"
    assert xobject.resource_name == "Im12"
    assert xobject.is_watermark_artifact is False


def unit(page: int, resource_name: str = "KSPX1", watermark: bool = True) -> ContentUnit:
    return ContentUnit(
        id=f"unit:artifact:{page}:7:10:40",
        kind="artifact",
        page=page,
        stream_xref=7,
        start=10,
        end=40,
        data=b"/Artifact <</Subtype/Watermark/Type/Pagination>> BDC q /KSPX1 Do Q EMC" if watermark else b"q /KSPX1 Do Q",
        is_watermark_artifact=watermark,
        resource_name=resource_name,
        resource_xref=99,
    )


def xobject_unit(page: int, resource_name: str = "Im12", resource_xref: int | None = 42) -> ContentUnit:
    return ContentUnit(
        id=f"unit:xobject:{page}:7:10:18",
        kind="xobject",
        page=page,
        stream_xref=7,
        start=10,
        end=18,
        data=f"/{resource_name} Do".encode("latin1"),
        is_watermark_artifact=False,
        resource_name=resource_name,
        resource_xref=resource_xref,
    )


def test_detects_repeated_watermark_artifact_units_as_auto_candidate():
    candidates = find_unit_watermark_candidates([unit(1), unit(2), unit(3)], page_count=3)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.id == "artifact:watermark"
    assert candidate.kind == "artifact"
    assert candidate.label == "PDF Watermark Artifact"
    assert candidate.pages == [1, 2, 3]
    assert candidate.occurrence_count == 3
    assert candidate.confidence >= 0.9
    assert candidate.can_auto_remove is True


def test_detects_repeated_xobject_resource_as_confirm_candidate():
    candidates = find_unit_watermark_candidates(
        [
            xobject_unit(1, "Im12", 42),
            xobject_unit(2, "Im12", 42),
            xobject_unit(3, "Im12", 42),
            xobject_unit(1, "Im12", 84),
            xobject_unit(2, "Im12", 84),
        ],
        page_count=3,
    )

    xobject_candidates = [candidate for candidate in candidates if candidate.kind == "xobject"]
    assert len(xobject_candidates) == 1
    candidate = xobject_candidates[0]
    assert candidate.id == "xobject:42"
    assert candidate.label == "重复 XObject Im12"
    assert candidate.pages == [1, 2, 3]
    assert candidate.occurrence_count == 3
    assert candidate.confidence >= 0.85
    assert candidate.can_auto_remove is False


def test_defers_repeated_form_xobject_when_xref_is_missing():
    candidates = find_unit_watermark_candidates(
        [xobject_unit(1, "FmWatermark", None), xobject_unit(2, "FmWatermark", None), xobject_unit(3, "FmWatermark", None)],
        page_count=3,
    )

    assert candidates == []


def test_ignores_repeated_xobject_units_below_min_pages():
    candidates = find_unit_watermark_candidates([xobject_unit(1), xobject_unit(2)], page_count=10)
    assert candidates == []


def test_ignores_repeated_xobject_units_below_confidence_threshold():
    candidates = find_unit_watermark_candidates([xobject_unit(1), xobject_unit(2), xobject_unit(3)], page_count=20)
    assert candidates == []


def test_ignores_sparse_unmarked_xobject_units():
    candidate = find_unit_watermark_candidates([unit(1, watermark=False)], page_count=10)
    assert candidate == []


def test_removes_watermark_artifact_unit_from_page_stream():
    class FakePage:
        number = 0

        def get_contents(self):
            return [7]

    class FakeDoc:
        def __init__(self):
            self.stream = b"BT /F1 12 Tf (Body) Tj ET\n/Artifact <</Subtype/Watermark/Type/Pagination>> BDC q /KSPX1 Do Q EMC\n"

        def xref_stream(self, xref):
            assert xref == 7
            return self.stream

        def update_stream(self, xref, stream):
            assert xref == 7
            self.stream = stream

    doc = FakeDoc()

    removed = remove_unit_watermark_artifacts_from_page(doc, FakePage())

    assert removed == 1
    assert b"/Subtype/Watermark" not in doc.stream
    assert b"BT /F1 12 Tf (Body) Tj ET" in doc.stream


def test_remove_unit_watermark_artifacts_passes_actual_page_number(monkeypatch):
    from pdf_watermark_remover import content_units

    class FakePage:
        number = 4

        def get_contents(self):
            return [7]

    class FakeDoc:
        def __init__(self):
            self.stream = b"/Artifact <</Subtype/Watermark>> BDC q /KSPX1 Do Q EMC\nBT /F1 12 Tf (Body) Tj ET\n"

        def xref_stream(self, xref):
            assert xref == 7
            return self.stream

        def update_stream(self, xref, stream):
            assert xref == 7
            self.stream = stream

    seen_page_numbers = []

    def fake_extract_units_from_stream(stream, page_number, stream_xref):
        seen_page_numbers.append(page_number)
        return [
            ContentUnit(
                id=f"artifact:{page_number}:{stream_xref}:0:55",
                kind="artifact",
                page=page_number,
                stream_xref=stream_xref,
                start=0,
                end=55,
                data=stream[:55],
                is_watermark_artifact=True,
                resource_name="KSPX1",
            )
        ]

    monkeypatch.setattr(content_units, "extract_units_from_stream", fake_extract_units_from_stream)

    removed = remove_unit_watermark_artifacts_from_page(FakeDoc(), FakePage())

    assert removed == 1
    assert seen_page_numbers == [5]


def test_wps_specific_removal_leaves_generic_watermark_artifact(monkeypatch, tmp_path):
    from pdf_watermark_remover import remove

    class FakePage:
        number = 0

        def get_contents(self):
            return [7]

    class FakeDoc:
        def __init__(self):
            self.stream = (
                b"/Artifact <</Subtype/Watermark/Type/Pagination>> BDC\n"
                b"q\n/KSPE1 gs\n1 0 0 1 0 0 cm\n/KSPX1 Do\nQ\nEMC\n"
                b"/Artifact <</Subtype/Watermark>> BDC\n"
                b"q /ImGeneric Do Q\nEMC\n"
            )
            self.closed = False

        def __iter__(self):
            return iter([FakePage()])

        def xref_stream(self, xref):
            assert xref == 7
            return self.stream

        def update_stream(self, xref, stream):
            assert xref == 7
            self.stream = stream

        def save(self, output_path, garbage, clean, deflate):
            assert output_path == str(tmp_path / "out.pdf")
            assert garbage == 4
            assert clean is True
            assert deflate is True

        def close(self):
            self.closed = True

    doc = FakeDoc()
    monkeypatch.setattr(remove.fitz, "open", lambda path: doc)

    removed = remove_text_watermarks("input.pdf", str(tmp_path / "out.pdf"), ["image:wps-watermark"])

    assert removed == 1
    assert b"/KSPE1 gs" not in doc.stream
    assert b"/KSPX1 Do" not in doc.stream
    assert b"/ImGeneric Do" in doc.stream
    assert b"/Subtype/Watermark" in doc.stream
    assert doc.closed is True


def test_selecting_wps_and_generic_artifact_removes_artifacts_once_per_page(monkeypatch, tmp_path):
    from pdf_watermark_remover import remove

    class FakeDoc:
        def __iter__(self):
            return iter([object()])

        def save(self, output_path, garbage, clean, deflate):
            pass

        def close(self):
            pass

    calls = []

    def fake_remove_unit_watermark_artifacts_from_page(doc, page, *args, **kwargs):
        calls.append((page, args, kwargs))
        return 1

    monkeypatch.setattr(remove.fitz, "open", lambda path: FakeDoc())
    monkeypatch.setattr(remove, "remove_unit_watermark_artifacts_from_page", fake_remove_unit_watermark_artifacts_from_page)

    removed = remove_text_watermarks(
        "input.pdf",
        str(tmp_path / "out.pdf"),
        ["image:wps-watermark", "artifact:watermark"],
    )

    assert removed == 1
    assert len(calls) == 1
    assert calls[0][2] == {}


def test_remove_text_watermarks_closes_document_when_removal_raises(monkeypatch, tmp_path):
    from pdf_watermark_remover import remove

    class FakeDoc:
        def __init__(self):
            self.closed = False

        def __iter__(self):
            return iter([object()])

        def close(self):
            self.closed = True

    doc = FakeDoc()
    monkeypatch.setattr(remove.fitz, "open", lambda path: doc)
    monkeypatch.setattr(remove, "_remove_volka_english_blocks", lambda doc, page: (_ for _ in ()).throw(RuntimeError("boom")))

    try:
        remove_text_watermarks("input.pdf", str(tmp_path / "output.pdf"), ["text:VolkaEnglish"])
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("Expected RuntimeError")

    assert doc.closed is True


def test_remove_text_watermarks_does_not_match_xobject_by_numeric_resource_name(monkeypatch, tmp_path):
    from pdf_watermark_remover import remove

    class FakePage:
        number = 0

        def get_contents(self):
            return [7]

        def get_images(self, full=True):
            assert full is True
            return [(84, 0, 120, 80, 8, "DeviceRGB", "", "42", "", 0)]

    class FakeDoc:
        def __init__(self):
            self.stream = b"q /42 Do Q\nBT /F1 12 Tf (Body) Tj ET\n"
            self.closed = False

        def __iter__(self):
            return iter([FakePage()])

        def xref_stream(self, xref):
            assert xref == 7
            return self.stream

        def save(self, output_path, garbage, clean, deflate):
            assert output_path == str(tmp_path / "out.pdf")

        def close(self):
            self.closed = True

    doc = FakeDoc()
    monkeypatch.setattr(remove.fitz, "open", lambda path: doc)

    removed = remove_text_watermarks("input.pdf", str(tmp_path / "out.pdf"), ["xobject:42"])

    assert removed == 0
    assert b"/42 Do" in doc.stream
    assert doc.closed is True


    from pdf_watermark_remover import remove

    class FakeDoc:
        def __init__(self):
            self.closed = False

        def __iter__(self):
            return iter([])

        def close(self):
            self.closed = True

    doc = FakeDoc()
    monkeypatch.setattr(remove.fitz, "open", lambda path: doc)

    try:
        remove_text_watermarks("input.pdf", str(tmp_path / "out.pdf"), ["xobject:FmWatermark"])
    except ValueError as exc:
        assert str(exc) == "Unsupported xobject candidate id: xobject:FmWatermark"
    else:
        raise AssertionError("Expected ValueError")

    assert doc.closed is True


def test_remove_text_watermarks_removes_selected_xobject_units(monkeypatch, tmp_path):
    from pdf_watermark_remover import remove

    class FakePage:
        number = 0

        def get_contents(self):
            return [7]

        def get_images(self, full=True):
            assert full is True
            return [(42, 0, 120, 80, 8, "DeviceRGB", "", "ImWatermark", "", 0)]

    class FakeDoc:
        def __init__(self):
            self.stream = b"q /ImWatermark Do Q\nq /ImOther Do Q\nBT /F1 12 Tf (Body) Tj ET\n"
            self.closed = False

        def __iter__(self):
            return iter([FakePage()])

        def xref_stream(self, xref):
            assert xref == 7
            return self.stream

        def update_stream(self, xref, stream):
            assert xref == 7
            self.stream = stream

        def save(self, output_path, garbage, clean, deflate):
            assert output_path == str(tmp_path / "out.pdf")

        def close(self):
            self.closed = True

    doc = FakeDoc()
    monkeypatch.setattr(remove.fitz, "open", lambda path: doc)

    removed = remove_text_watermarks("input.pdf", str(tmp_path / "out.pdf"), ["xobject:42"])

    assert removed == 1
    assert b"/ImWatermark Do" not in doc.stream
    assert b"/ImOther Do" in doc.stream
    assert b"BT /F1 12 Tf (Body) Tj ET" in doc.stream
    assert doc.closed is True
