from pdf_watermark_remover.verify_export import verify_export_result


def test_zero_removed_count_is_rejected():
    result = verify_export_result(
        removed_count=0,
        original_page_count=1,
        output_page_count=1,
        original_page_sizes=[(612.0, 792.0)],
        output_page_sizes=[(612.0, 792.0)],
    )

    assert result.ok is False
    assert result.message == "未移除任何水印对象。"


def test_matching_page_structure_with_removals_is_accepted():
    result = verify_export_result(
        removed_count=3,
        original_page_count=2,
        output_page_count=2,
        original_page_sizes=[(612.0, 792.0), (612.0, 792.0)],
        output_page_sizes=[(612.0, 792.0), (612.0, 792.0)],
    )

    assert result.ok is True
    assert result.message == "导出验证通过。"


def test_page_size_change_is_rejected():
    result = verify_export_result(
        removed_count=1,
        original_page_count=1,
        output_page_count=1,
        original_page_sizes=[(612.0, 792.0)],
        output_page_sizes=[(600.0, 792.0)],
    )

    assert result.ok is False
    assert result.message == "导出 PDF 页面尺寸与原文件不一致。"


def test_link_count_change_is_rejected():
    result = verify_export_result(
        removed_count=1,
        original_page_count=1,
        output_page_count=1,
        original_page_sizes=[(612.0, 792.0)],
        output_page_sizes=[(612.0, 792.0)],
        original_link_count=2,
        output_link_count=1,
    )

    assert result.ok is False
    assert result.message == "导出 PDF 链接数量与原文件不一致。"


def test_body_text_change_is_rejected_for_non_text_watermark_removal():
    result = verify_export_result(
        removed_count=1,
        original_page_count=1,
        output_page_count=1,
        original_page_sizes=[(612.0, 792.0)],
        output_page_sizes=[(612.0, 792.0)],
        original_body_text="Chapter 1 Body Text",
        output_body_text="Chapter 1",
    )

    assert result.ok is False
    assert result.message == "导出 PDF 正文文本与原文件不一致。"


def test_matching_link_count_and_body_text_are_accepted():
    result = verify_export_result(
        removed_count=1,
        original_page_count=1,
        output_page_count=1,
        original_page_sizes=[(612.0, 792.0)],
        output_page_sizes=[(612.0, 792.0)],
        original_link_count=2,
        output_link_count=2,
        original_body_text="Chapter 1 Body Text",
        output_body_text="Chapter 1 Body Text",
    )

    assert result.ok is True
    assert result.message == "导出验证通过。"
