from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExportVerification:
    ok: bool
    message: str


def verify_export_result(
    removed_count: int,
    original_page_count: int,
    output_page_count: int,
    original_page_sizes: list[tuple[float, float]],
    output_page_sizes: list[tuple[float, float]],
    original_link_count: int | None = None,
    output_link_count: int | None = None,
    original_body_text: str | None = None,
    output_body_text: str | None = None,
) -> ExportVerification:
    if removed_count <= 0:
        return ExportVerification(False, "未移除任何水印对象。")
    if output_page_count != original_page_count:
        return ExportVerification(False, "导出 PDF 页数与原文件不一致。")
    if output_page_sizes != original_page_sizes:
        return ExportVerification(False, "导出 PDF 页面尺寸与原文件不一致。")
    if original_link_count is not None and output_link_count is not None and output_link_count != original_link_count:
        return ExportVerification(False, "导出 PDF 链接数量与原文件不一致。")
    if original_body_text is not None and output_body_text is not None and output_body_text != original_body_text:
        return ExportVerification(False, "导出 PDF 正文文本与原文件不一致。")
    return ExportVerification(True, "导出验证通过。")
