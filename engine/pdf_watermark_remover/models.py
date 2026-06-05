from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class PageSize:
    page: int
    width: float
    height: float


@dataclass(frozen=True)
class TextSpan:
    page: int
    text: str
    size: float
    color: int
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class PdfInfo:
    path: str
    page_count: int
    encrypted: bool
    has_text: bool
    page_sizes: list[PageSize]


@dataclass(frozen=True)
class UnitRef:
    page: int
    stream_xref: int
    start: int
    end: int


@dataclass(frozen=True)
class ContentUnit:
    id: str
    kind: Literal["artifact", "xobject", "text", "path"]
    page: int
    stream_xref: int
    start: int
    end: int
    data: bytes
    is_watermark_artifact: bool
    resource_name: str | None = None
    resource_xref: int | None = None


@dataclass(frozen=True)
class WatermarkCandidate:
    id: str
    kind: Literal["text", "image", "vector", "artifact", "xobject"]
    label: str
    pages: list[int]
    occurrence_count: int
    confidence: float
    can_auto_remove: bool
    reason: str


@dataclass(frozen=True)
class DetectionResult:
    pdf: PdfInfo
    candidates: list[WatermarkCandidate]
    recommended_mode: Literal["object", "confirm", "image-fallback", "none"]
    message: str


def to_jsonable(value):
    return asdict(value)
