from __future__ import annotations

import re
from dataclasses import dataclass, replace

from .models import ContentUnit

_DO_RE = re.compile(rb"/([A-Za-z0-9_.-]+)\s+Do\b")
_WHITESPACE = b"\x00\t\n\f\r "
_DELIMITERS = b"()<>[]{}/%"
_PATH_CONSTRUCTION_OPS = {b"m", b"l", b"c", b"v", b"y", b"h", b"re"}
_PATH_PAINTING_OPS = {b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*", b"n"}
_NON_PATH_OPS = {
    b"q",
    b"Q",
    b"cm",
    b"Do",
    b"BT",
    b"ET",
    b"Tf",
    b"Tj",
    b"TJ",
    b"Td",
    b"Tm",
    b"BDC",
    b"BMC",
    b"EMC",
    b"gs",
    b"RG",
    b"rg",
}
_MARKED_CONTENT_BEGIN_OPS = {b"BMC", b"BDC"}


@dataclass(frozen=True)
class _Token:
    value: bytes
    start: int
    end: int
    kind: str


def _is_whitespace(byte: int) -> bool:
    return byte in _WHITESPACE


def _is_delimiter(byte: int) -> bool:
    return byte in _DELIMITERS


def _scan_literal_string(stream: bytes, start: int) -> int:
    depth = 1
    index = start + 1
    while index < len(stream) and depth > 0:
        byte = stream[index]
        if byte == ord("\\"):
            index += 2
            continue
        if byte == ord("("):
            depth += 1
        elif byte == ord(")"):
            depth -= 1
        index += 1
    return index


def _scan_hex_string(stream: bytes, start: int) -> int:
    index = start + 1
    while index < len(stream):
        if stream[index] == ord(">"):
            return index + 1
        index += 1
    return index


def _scan_comment(stream: bytes, start: int) -> int:
    index = start + 1
    while index < len(stream) and stream[index] not in b"\r\n":
        index += 1
    return index


def _tokenize(stream: bytes) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    while index < len(stream):
        byte = stream[index]
        if _is_whitespace(byte):
            index += 1
            continue
        if byte == ord("%"):
            index = _scan_comment(stream, index)
            continue
        if byte == ord("("):
            index = _scan_literal_string(stream, index)
            continue
        if stream[index : index + 2] in (b"<<", b">>"):
            tokens.append(_Token(value=stream[index : index + 2], start=index, end=index + 2, kind="delimiter"))
            index += 2
            continue
        if byte == ord("<"):
            index = _scan_hex_string(stream, index)
            continue
        if byte == ord("/"):
            end = index + 1
            while end < len(stream) and not _is_whitespace(stream[end]) and not _is_delimiter(stream[end]):
                end += 1
            tokens.append(_Token(value=stream[index:end], start=index, end=end, kind="name"))
            index = end
            continue
        if _is_delimiter(byte):
            tokens.append(_Token(value=bytes([byte]), start=index, end=index + 1, kind="delimiter"))
            index += 1
            continue

        end = index + 1
        while end < len(stream) and not _is_whitespace(stream[end]) and not _is_delimiter(stream[end]):
            end += 1
        tokens.append(_Token(value=stream[index:end], start=index, end=end, kind="word"))
        index = end
    return tokens


def _is_watermark_artifact(data: bytes) -> bool:
    return b"/Subtype/Watermark" in re.sub(rb"\s+", b"", data)


def _resource_name(data: bytes) -> str | None:
    match = _DO_RE.search(data)
    if not match:
        return None
    return match.group(1).decode("latin1")


def _is_inside(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    return any(range_start <= start and end <= range_end for range_start, range_end in ranges)


def _unit_id(kind: str, page_number: int, stream_xref: int, start: int, end: int) -> str:
    return f"{kind}:{page_number}:{stream_xref}:{start}:{end}"


def _build_unit(
    *,
    kind: str,
    stream: bytes,
    page_number: int,
    stream_xref: int,
    start: int,
    end: int,
    is_watermark_artifact: bool = False,
) -> ContentUnit:
    data = stream[start:end]
    return ContentUnit(
        id=_unit_id(kind, page_number, stream_xref, start, end),
        kind=kind,
        page=page_number,
        stream_xref=stream_xref,
        start=start,
        end=end,
        data=data,
        is_watermark_artifact=is_watermark_artifact,
        resource_name=_resource_name(data),
    )


def _is_artifact_bdc(operands: list[_Token]) -> bool:
    return any(token.kind == "name" and token.value == b"/Artifact" for token in operands)


def _artifact_ranges(tokens: list[_Token]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    operands: list[_Token] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.value == b"BDC" and _is_artifact_bdc(operands):
            depth = 1
            end = token.end
            nested_index = index + 1
            while nested_index < len(tokens):
                nested_token = tokens[nested_index]
                if nested_token.value in _MARKED_CONTENT_BEGIN_OPS:
                    depth += 1
                elif nested_token.value == b"EMC":
                    depth -= 1
                    end = nested_token.end
                    if depth == 0:
                        break
                nested_index += 1
            ranges.append((operands[0].start, end))
            operands = []
            index = nested_index + 1
            continue
        if token.kind == "word":
            operands = []
        else:
            operands.append(token)
        index += 1
    return ranges


def _extract_artifacts(
    stream: bytes,
    tokens: list[_Token],
    page_number: int,
    stream_xref: int,
) -> tuple[list[ContentUnit], list[tuple[int, int]]]:
    ranges = _artifact_ranges(tokens)
    units = [
        _build_unit(
            kind="artifact",
            stream=stream,
            page_number=page_number,
            stream_xref=stream_xref,
            start=start,
            end=end,
            is_watermark_artifact=_is_watermark_artifact(stream[start:end]),
        )
        for start, end in ranges
    ]
    return units, ranges


def _extract_text_units(
    stream: bytes,
    tokens: list[_Token],
    artifact_ranges: list[tuple[int, int]],
    page_number: int,
    stream_xref: int,
) -> list[ContentUnit]:
    units: list[ContentUnit] = []
    text_start: int | None = None
    for token in tokens:
        if text_start is None:
            if token.value == b"BT":
                text_start = token.start
            continue
        if token.value == b"ET":
            if not _is_inside(text_start, token.end, artifact_ranges):
                units.append(
                    _build_unit(
                        kind="text",
                        stream=stream,
                        page_number=page_number,
                        stream_xref=stream_xref,
                        start=text_start,
                        end=token.end,
                    )
                )
            text_start = None
    return units


def _extract_xobject_units(
    stream: bytes,
    tokens: list[_Token],
    artifact_ranges: list[tuple[int, int]],
    page_number: int,
    stream_xref: int,
) -> list[ContentUnit]:
    units: list[ContentUnit] = []
    operands: list[_Token] = []
    for token in tokens:
        if token.value == b"Do":
            name_token = next((operand for operand in reversed(operands) if operand.kind == "name"), None)
            if name_token is not None and not _is_inside(name_token.start, token.end, artifact_ranges):
                units.append(
                    _build_unit(
                        kind="xobject",
                        stream=stream,
                        page_number=page_number,
                        stream_xref=stream_xref,
                        start=name_token.start,
                        end=token.end,
                    )
                )
            operands = []
        elif token.kind == "word":
            operands = []
        else:
            operands.append(token)
    return units


def _extract_path_units(
    stream: bytes,
    tokens: list[_Token],
    artifact_ranges: list[tuple[int, int]],
    page_number: int,
    stream_xref: int,
) -> list[ContentUnit]:
    units: list[ContentUnit] = []
    operands: list[_Token] = []
    path_start: int | None = None

    for token in tokens:
        if token.value in _PATH_CONSTRUCTION_OPS:
            if path_start is None:
                path_start = operands[0].start if operands else token.start
            operands = []
            continue

        if token.value in _PATH_PAINTING_OPS:
            if path_start is not None and not _is_inside(path_start, token.end, artifact_ranges):
                units.append(
                    _build_unit(
                        kind="path",
                        stream=stream,
                        page_number=page_number,
                        stream_xref=stream_xref,
                        start=path_start,
                        end=token.end,
                    )
                )
            operands = []
            path_start = None
            continue

        if token.kind == "word" and token.value in _NON_PATH_OPS:
            operands = []
            path_start = None
        else:
            operands.append(token)

    return units


def extract_units_from_stream(stream: bytes, page_number: int, stream_xref: int) -> list[ContentUnit]:
    tokens = _tokenize(stream)
    artifact_units, artifact_ranges = _extract_artifacts(stream, tokens, page_number, stream_xref)
    units = [
        *artifact_units,
        *_extract_xobject_units(stream, tokens, artifact_ranges, page_number, stream_xref),
        *_extract_text_units(stream, tokens, artifact_ranges, page_number, stream_xref),
        *_extract_path_units(stream, tokens, artifact_ranges, page_number, stream_xref),
    ]
    return sorted(units, key=lambda unit: (unit.start, unit.end, unit.kind))


def _page_image_xrefs(page) -> dict[str, int]:
    image_xrefs: dict[str, int] = {}
    for image in page.get_images(full=True):
        if len(image) > 7:
            image_xrefs[str(image[7])] = int(image[0])
    return image_xrefs


def extract_document_units(doc) -> list[ContentUnit]:
    units: list[ContentUnit] = []
    for page_number, page in enumerate(doc, start=1):
        image_xrefs = _page_image_xrefs(page)
        for stream_xref in page.get_contents():
            for unit in extract_units_from_stream(
                doc.xref_stream(stream_xref),
                page_number=page_number,
                stream_xref=stream_xref,
            ):
                if unit.resource_name in image_xrefs:
                    unit = replace(unit, resource_xref=image_xrefs[unit.resource_name])
                units.append(unit)
    return units
