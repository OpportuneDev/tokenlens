from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class WasteSeverity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class TokenSegment:
    name: str
    tokens: int
    details: dict = field(default_factory=dict)


@dataclass
class WasteFlag:
    pattern: str
    severity: WasteSeverity
    tokens_wasted: int
    detail: str
    fix: str


@dataclass
class RequestAnalysis:
    request_id: str
    model: str
    provider: str
    segments: list[TokenSegment]
    total_input_tokens: int
    output_tokens: Optional[int] = None
    waste_flags: list[WasteFlag] = field(default_factory=list)
    efficiency_score: int = 100
    recoverable_tokens: int = 0
    recoverable_pct: float = 0.0
