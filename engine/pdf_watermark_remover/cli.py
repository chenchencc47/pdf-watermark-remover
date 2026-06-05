from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from typing import Any

from .models import DetectionResult, PdfInfo, WatermarkCandidate


def _suppress_mupdf_console_messages() -> None:
    import fitz

    fitz.TOOLS.mupdf_display_errors(False)
    fitz.TOOLS.mupdf_display_warnings(False)


def _camelize_key(key: str) -> str:
    parts = key.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


def _camelize(value: Any) -> Any:
    if isinstance(value, dict):
        return {_camelize_key(key): _camelize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_camelize(item) for item in value]
    return value


def _print_json(payload: object) -> None:
    sys.stdout.buffer.write(json.dumps(_camelize(payload), ensure_ascii=True).encode("ascii"))
    sys.stdout.buffer.write(b"\n")


def _error(code: str, message: str, exit_code: int) -> int:
    _print_json({"error": {"code": code, "message": message}})
    return exit_code


def _parse_candidate_ids(value: str) -> list[str]:
    parsed = json.loads(value)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("candidate_ids must be a JSON string array")
    return parsed


def _page_sizes(info: PdfInfo) -> list[tuple[float, float]]:
    return [(page_size.width, page_size.height) for page_size in info.page_sizes]


def _link_count(pdf_path: str) -> int:
    import fitz

    with fitz.open(pdf_path) as doc:
        return sum(len(page.get_links()) for page in doc)


def _normalized_body_text(pdf_path: str, ignored_texts: set[str] | None = None) -> str:
    import fitz

    with fitz.open(pdf_path) as doc:
        text = " ".join(" ".join(page.get_text("text").split()) for page in doc).strip()
    for ignored_text in ignored_texts or set():
        normalized_ignored_text = " ".join(ignored_text.split())
        if normalized_ignored_text:
            text = text.replace(normalized_ignored_text, " ")
    return " ".join(text.split())


def _delete_output_if_exists(output_path: str) -> None:
    if os.path.exists(output_path):
        os.remove(output_path)


def detect_candidates(pdf_path: str) -> tuple[PdfInfo, list[WatermarkCandidate]]:
    import fitz

    from .content_units import extract_document_units
    from .detect import find_repeated_text_candidates, find_unit_watermark_candidates
    from .inspect_pdf import inspect_document

    with fitz.open(pdf_path) as doc:
        info, spans = inspect_document(doc, pdf_path)
        candidates = find_repeated_text_candidates(spans, info.page_count)
        candidates.extend(find_unit_watermark_candidates(extract_document_units(doc), doc.page_count))
    candidates.sort(key=lambda item: item.confidence, reverse=True)
    return info, candidates


def detect_command(pdf_path: str) -> int:
    if not os.path.exists(pdf_path):
        return _error("file_not_found", f"PDF 文件不存在：{pdf_path}", 2)

    try:
        info, candidates = detect_candidates(pdf_path)
        auto_candidates = [item for item in candidates if item.can_auto_remove]
        if not candidates:
            mode = "none"
            message = "未检测到高置信度水印。"
        elif auto_candidates:
            mode = "object"
            top = auto_candidates[0]
            message = f"检测到 {len(candidates)} 个水印候选，推荐对象级删除：{top.label}。"
        else:
            mode = "confirm"
            message = f"检测到 {len(candidates)} 个低置信度候选，需要确认。"

        result = DetectionResult(pdf=info, candidates=candidates, recommended_mode=mode, message=message)
        _print_json(asdict(result))
        return 0
    except Exception as exc:
        return _error("inspect_failed", str(exc), 1)


def preview_command(pdf_path: str, candidate_ids: str, page: int) -> int:
    if not os.path.exists(pdf_path):
        return _error("file_not_found", f"PDF 文件不存在：{pdf_path}", 2)
    try:
        from .render import render_preview

        ids = _parse_candidate_ids(candidate_ids)
        _print_json(render_preview(pdf_path, ids, page))
        return 0
    except Exception as exc:
        return _error("preview_failed", str(exc), 1)


def export_command(pdf_path: str, candidate_ids: str, output_path: str) -> int:
    if not os.path.exists(pdf_path):
        return _error("file_not_found", f"PDF 文件不存在：{pdf_path}", 2)
    try:
        from .inspect_pdf import inspect_pdf
        from .remove import remove_text_watermarks
        from .verify_export import verify_export_result

        ids = _parse_candidate_ids(candidate_ids)
        ignored_texts = {candidate_id.removeprefix("text:") for candidate_id in ids if candidate_id.startswith("text:")}
        original_info = inspect_pdf(pdf_path)[0]
        removed = remove_text_watermarks(pdf_path, output_path, ids)
        try:
            output_info = inspect_pdf(output_path)[0]
            verification = verify_export_result(
                removed_count=removed,
                original_page_count=original_info.page_count,
                output_page_count=output_info.page_count,
                original_page_sizes=_page_sizes(original_info),
                output_page_sizes=_page_sizes(output_info),
                original_link_count=_link_count(pdf_path),
                output_link_count=_link_count(output_path),
                original_body_text=_normalized_body_text(pdf_path, ignored_texts),
                output_body_text=_normalized_body_text(output_path),
            )
            if verification.ok:
                remaining_ids = {candidate.id for candidate in detect_candidates(output_path)[1]}
                stable_ids = {candidate_id for candidate_id in ids if not candidate_id.startswith("xobject:")}
                if remaining_ids & stable_ids:
                    _delete_output_if_exists(output_path)
                    return _error("export_verification_failed", "导出后仍检测到所选水印候选。", 1)
        except Exception:
            _delete_output_if_exists(output_path)
            raise
        if not verification.ok:
            _delete_output_if_exists(output_path)
            return _error("export_verification_failed", verification.message, 1)
        _print_json({"outputPath": output_path, "removedCount": removed, "pageCount": output_info.page_count})
        return 0
    except Exception as exc:
        return _error("export_failed", str(exc), 1)


def main(argv: list[str] | None = None) -> int:
    _suppress_mupdf_console_messages()
    parser = argparse.ArgumentParser(prog="pdf-watermark-engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect_parser = subparsers.add_parser("detect")
    detect_parser.add_argument("pdf_path")

    preview_parser = subparsers.add_parser("preview")
    preview_parser.add_argument("pdf_path")
    preview_parser.add_argument("candidate_ids")
    preview_parser.add_argument("page", type=int)

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("pdf_path")
    export_parser.add_argument("candidate_ids")
    export_parser.add_argument("output_path")

    args = parser.parse_args(argv)

    if args.command == "detect":
        return detect_command(args.pdf_path)
    if args.command == "preview":
        return preview_command(args.pdf_path, args.candidate_ids, args.page)
    if args.command == "export":
        return export_command(args.pdf_path, args.candidate_ids, args.output_path)
    return _error("unknown_command", args.command, 2)


if __name__ == "__main__":
    sys.exit(main())
