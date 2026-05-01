"""
Persists RequestAnalysis objects to a local JSON file.
Written to after every call when storage is enabled.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from .models import RequestAnalysis, TokenSegment, WasteFlag, WasteSeverity

_DEFAULT_PATH = Path.home() / ".tokenlens" / "session.json"


def _analysis_to_dict(a: RequestAnalysis) -> dict:
    return {
        "ts": time.time(),
        "request_id": a.request_id,
        "model": a.model,
        "provider": a.provider,
        "total_input_tokens": a.total_input_tokens,
        "output_tokens": a.output_tokens,
        "efficiency_score": a.efficiency_score,
        "recoverable_tokens": a.recoverable_tokens,
        "recoverable_pct": a.recoverable_pct,
        "segments": [{"name": s.name, "tokens": s.tokens} for s in a.segments],
        "flags": [
            {
                "pattern": f.pattern,
                "severity": f.severity.value,
                "tokens_wasted": f.tokens_wasted,
                "detail": f.detail,
                "fix": f.fix,
            }
            for f in a.waste_flags
        ],
    }


def write(analysis: RequestAnalysis, path: Path = _DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except Exception:
            existing = []
    existing.append(_analysis_to_dict(analysis))
    path.write_text(json.dumps(existing, indent=2))


def read(path: Path = _DEFAULT_PATH) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


def clear(path: Path = _DEFAULT_PATH) -> None:
    if path.exists():
        path.write_text("[]")
