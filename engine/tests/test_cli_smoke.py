import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from pdf_watermark_remover.models import PageSize, PdfInfo, TextSpan, WatermarkCandidate


def test_cli_rejects_missing_pdf():
    completed = subprocess.run(
        [sys.executable, "-m", "pdf_watermark_remover.cli", "detect", "missing.pdf"],
        cwd="engine",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["error"]["code"] == "file_not_found"


def test_cli_missing_pdf_stdout_is_utf8_decodable_bytes():
    completed = subprocess.run(
        [sys.executable, "-m", "pdf_watermark_remover.cli", "detect", "missing.pdf"],
        cwd="engine",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert completed.returncode == 2
    payload = json.loads(completed.stdout.decode("utf-8"))
    assert payload["error"]["message"].startswith("PDF 文件不存在")


def test_candidate_ids_are_parsed_as_json_array_so_commas_are_preserved():
    from pdf_watermark_remover.cli import _parse_candidate_ids

    assert _parse_candidate_ids('["text:Volka,English"]') == ["text:Volka,English"]


def test_wps_export_stdout_is_valid_json_even_when_mupdf_reports_warnings(tmp_path):
    sample = Path("C:/Users/10263/Desktop/3000 Textbook.no-watermark_加水印.pdf")
    if not sample.exists():
        pytest.skip("external WPS sample is not available")
    output = tmp_path / "wps.no-watermark.pdf"

    completed = subprocess.run(
        [sys.executable, "-m", "pdf_watermark_remover.cli", "export", str(sample), '["image:wps-watermark"]', str(output)],
        cwd="engine",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout.decode("utf-8"))
    assert payload["removedCount"] == 364
    assert payload["pageCount"] == 364


def test_export_rejects_artifact_candidate_when_no_objects_are_removed(tmp_path):
    sample = Path(__file__).resolve().parents[3] / "3000 Textbook.pdf"
    assert sample.exists()
    output = tmp_path / "sample.no-watermark.pdf"

    completed = subprocess.run(
        [sys.executable, "-m", "pdf_watermark_remover.cli", "export", str(sample), '["artifact:watermark"]', str(output)],
        cwd="engine",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout.decode("utf-8"))
    assert payload["error"]["code"] == "export_verification_failed"
    assert payload["error"]["message"] == "未移除任何水印对象。"
    assert not output.exists()


def test_export_rejects_output_when_link_count_changes(monkeypatch, tmp_path, capsys):
    from pdf_watermark_remover import cli

    sample = tmp_path / "sample.pdf"
    output = tmp_path / "output.pdf"
    sample.write_bytes(b"%PDF sample")
    output.write_bytes(b"stale output")

    original_info = PdfInfo(path=str(sample), page_count=1, encrypted=False, has_text=True, page_sizes=[PageSize(1, 612.0, 792.0)])
    output_info = PdfInfo(path=str(output), page_count=1, encrypted=False, has_text=True, page_sizes=[PageSize(1, 612.0, 792.0)])

    monkeypatch.setattr(cli.os.path, "exists", lambda path: True)
    monkeypatch.setattr("pdf_watermark_remover.inspect_pdf.inspect_pdf", lambda path: (output_info if str(path) == str(output) else original_info, []))
    monkeypatch.setattr("pdf_watermark_remover.remove.remove_text_watermarks", lambda pdf_path, output_path, ids: 1)
    monkeypatch.setattr("pdf_watermark_remover.cli.detect_candidates", lambda path: (output_info, []))
    monkeypatch.setattr("pdf_watermark_remover.cli._link_count", lambda path: 1 if str(path) == str(output) else 2)
    monkeypatch.setattr("pdf_watermark_remover.cli._normalized_body_text", lambda path, ignored_texts=None: "body")

    assert cli.export_command(str(sample), '["artifact:watermark"]', str(output)) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "export_verification_failed"
    assert payload["error"]["message"] == "导出 PDF 链接数量与原文件不一致。"
    assert not output.exists()


def test_export_allows_removed_selected_text_candidate_in_body_comparison(monkeypatch, tmp_path, capsys):
    from pdf_watermark_remover import cli

    sample = tmp_path / "sample.pdf"
    output = tmp_path / "output.pdf"
    sample.write_bytes(b"%PDF sample")
    output.write_bytes(b"stale output")

    original_info = PdfInfo(path=str(sample), page_count=1, encrypted=False, has_text=True, page_sizes=[PageSize(1, 612.0, 792.0)])
    output_info = PdfInfo(path=str(output), page_count=1, encrypted=False, has_text=True, page_sizes=[PageSize(1, 612.0, 792.0)])

    def normalized_body_text(path, ignored_texts=None):
        if str(path) == str(sample) and ignored_texts == {"VolkaEnglish"}:
            return "same body"
        if str(path) == str(sample):
            return "same body VolkaEnglish"
        return "same body"

    monkeypatch.setattr(cli.os.path, "exists", lambda path: True)
    monkeypatch.setattr("pdf_watermark_remover.inspect_pdf.inspect_pdf", lambda path: (output_info if str(path) == str(output) else original_info, []))
    monkeypatch.setattr("pdf_watermark_remover.remove.remove_text_watermarks", lambda pdf_path, output_path, ids: 1)
    monkeypatch.setattr("pdf_watermark_remover.cli.detect_candidates", lambda path: (output_info, []))
    monkeypatch.setattr("pdf_watermark_remover.cli._link_count", lambda path: 0)
    monkeypatch.setattr("pdf_watermark_remover.cli._normalized_body_text", normalized_body_text)

    assert cli.export_command(str(sample), '["text:VolkaEnglish"]', str(output)) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["outputPath"] == str(output)
    assert payload["removedCount"] == 1
    assert payload["pageCount"] == 1


def test_export_deletes_output_when_post_save_text_verification_raises(monkeypatch, tmp_path, capsys):
    from pdf_watermark_remover import cli

    sample = tmp_path / "sample.pdf"
    output = tmp_path / "output.pdf"
    sample.write_bytes(b"%PDF sample")

    info = PdfInfo(path=str(sample), page_count=1, encrypted=False, has_text=True, page_sizes=[PageSize(1, 612.0, 792.0)])

    def remove_text_watermarks(pdf_path, output_path, ids):
        Path(output_path).write_bytes(b"%PDF output")
        return 1

    def normalized_body_text(path, ignored_texts=None):
        if str(path) == str(output):
            raise RuntimeError("text read failed")
        return "body"

    monkeypatch.setattr(cli.os.path, "exists", lambda path: True)
    monkeypatch.setattr("pdf_watermark_remover.inspect_pdf.inspect_pdf", lambda path: (info, []))
    monkeypatch.setattr("pdf_watermark_remover.remove.remove_text_watermarks", remove_text_watermarks)
    monkeypatch.setattr("pdf_watermark_remover.cli._link_count", lambda path: 0)
    monkeypatch.setattr("pdf_watermark_remover.cli._normalized_body_text", normalized_body_text)

    assert cli.export_command(str(sample), '["artifact:watermark"]', str(output)) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "export_failed"
    assert not output.exists()



def test_export_rejects_output_when_selected_candidate_is_still_detected(monkeypatch, tmp_path, capsys):
    from pdf_watermark_remover import cli

    sample = tmp_path / "sample.pdf"
    output = tmp_path / "output.pdf"
    sample.write_bytes(b"%PDF sample")
    output.write_bytes(b"stale output")

    selected = WatermarkCandidate(
        id="artifact:watermark",
        kind="artifact",
        label="PDF Watermark Artifact",
        pages=[1],
        occurrence_count=1,
        confidence=0.95,
        can_auto_remove=True,
        reason="still present",
    )
    info = PdfInfo(path=str(sample), page_count=1, encrypted=False, has_text=True, page_sizes=[PageSize(1, 612.0, 792.0)])

    monkeypatch.setattr(cli.os.path, "exists", lambda path: True)
    monkeypatch.setattr("pdf_watermark_remover.inspect_pdf.inspect_pdf", lambda path: (info, []))
    monkeypatch.setattr("pdf_watermark_remover.remove.remove_text_watermarks", lambda pdf_path, output_path, ids: 1)
    monkeypatch.setattr("pdf_watermark_remover.cli._link_count", lambda path: 0)
    monkeypatch.setattr("pdf_watermark_remover.cli._normalized_body_text", lambda path, ignored_texts=None: "body")
    monkeypatch.setattr("pdf_watermark_remover.cli.detect_candidates", lambda path: (info, [selected]))

    assert cli.export_command(str(sample), '["artifact:watermark"]', str(output)) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "export_verification_failed"
    assert payload["error"]["message"] == "导出后仍检测到所选水印候选。"
    assert not output.exists()


def test_detect_command_recommends_highest_confidence_unit_candidate(monkeypatch, tmp_path, capsys):
    from pdf_watermark_remover import cli

    @dataclass
    class FakeDoc:
        page_count: int = 3

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    low_text = WatermarkCandidate(
        id="text:Low",
        kind="text",
        label="Low",
        pages=[1, 2, 3],
        occurrence_count=3,
        confidence=0.86,
        can_auto_remove=True,
        reason="low",
    )
    high_unit = WatermarkCandidate(
        id="artifact:watermark",
        kind="artifact",
        label="PDF Watermark Artifact",
        pages=[1, 2, 3],
        occurrence_count=3,
        confidence=0.95,
        can_auto_remove=True,
        reason="high",
    )

    monkeypatch.setattr(cli.os.path, "exists", lambda path: True)
    monkeypatch.setitem(sys.modules, "fitz", type("FakeFitz", (), {"open": lambda self, path: FakeDoc()})())
    monkeypatch.setattr(
        "pdf_watermark_remover.inspect_pdf.inspect_document",
        lambda doc, path: (
            PdfInfo(path=str(tmp_path / "sample.pdf"), page_count=3, encrypted=False, has_text=True, page_sizes=[PageSize(1, 1, 1)]),
            [TextSpan(page=1, text="Low", size=1, color=0, bbox=(0, 0, 1, 1))],
        ),
    )
    monkeypatch.setattr("pdf_watermark_remover.detect.find_repeated_text_candidates", lambda spans, page_count: [low_text])
    monkeypatch.setattr("pdf_watermark_remover.content_units.extract_document_units", lambda doc: [])
    monkeypatch.setattr("pdf_watermark_remover.detect.find_unit_watermark_candidates", lambda units, page_count: [high_unit])

    assert cli.detect_command(str(tmp_path / "sample.pdf")) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["candidates"][0]["id"] == "artifact:watermark"
    assert payload["message"].endswith("PDF Watermark Artifact。")


def test_detect_command_recommends_highest_confidence_auto_candidate(monkeypatch, tmp_path, capsys):
    from pdf_watermark_remover import cli

    @dataclass
    class FakeDoc:
        page_count: int = 3

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    auto_text = WatermarkCandidate(
        id="text:VolkaEnglish",
        kind="text",
        label="VolkaEnglish",
        pages=[1, 2, 3],
        occurrence_count=3,
        confidence=0.86,
        can_auto_remove=True,
        reason="auto",
    )
    manual_unit = WatermarkCandidate(
        id="xobject:42",
        kind="xobject",
        label="重复 XObject Im12",
        pages=[1, 2, 3],
        occurrence_count=3,
        confidence=0.99,
        can_auto_remove=False,
        reason="manual",
    )

    monkeypatch.setattr(cli.os.path, "exists", lambda path: True)
    monkeypatch.setitem(sys.modules, "fitz", type("FakeFitz", (), {"open": lambda self, path: FakeDoc()})())
    monkeypatch.setattr(
        "pdf_watermark_remover.inspect_pdf.inspect_document",
        lambda doc, path: (
            PdfInfo(path=str(tmp_path / "sample.pdf"), page_count=3, encrypted=False, has_text=True, page_sizes=[PageSize(1, 1, 1)]),
            [],
        ),
    )
    monkeypatch.setattr("pdf_watermark_remover.detect.find_repeated_text_candidates", lambda spans, page_count: [auto_text])
    monkeypatch.setattr("pdf_watermark_remover.content_units.extract_document_units", lambda doc: [])
    monkeypatch.setattr("pdf_watermark_remover.detect.find_unit_watermark_candidates", lambda units, page_count: [manual_unit])

    assert cli.detect_command(str(tmp_path / "sample.pdf")) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["candidates"][0]["id"] == "xobject:42"
    assert payload["recommendedMode"] == "object"
    assert payload["message"].endswith("VolkaEnglish。")


def test_detect_command_opens_pdf_once_for_inspection_and_units(monkeypatch, tmp_path, capsys):
    from pdf_watermark_remover import cli

    class FakePage:
        rect = type("Rect", (), {"width": 612.0, "height": 792.0})()

        def get_text(self, mode):
            assert mode == "dict"
            return {"blocks": []}

        def get_images(self, full=True):
            return []

        def get_contents(self):
            return []

    class FakeDoc:
        page_count = 1
        needs_pass = False

        def __init__(self):
            self.closed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()
            return False

        def __iter__(self):
            return iter([FakePage()])

        def close(self):
            self.closed = True

    opened_docs = []

    def fake_open(path):
        doc = FakeDoc()
        opened_docs.append(doc)
        return doc

    monkeypatch.setattr(cli.os.path, "exists", lambda path: True)
    monkeypatch.setitem(sys.modules, "fitz", type("FakeFitz", (), {"open": staticmethod(fake_open)})())

    assert cli.detect_command(str(tmp_path / "sample.pdf")) == 0

    json.loads(capsys.readouterr().out)
    assert len(opened_docs) == 1
    assert opened_docs[0].closed is True
