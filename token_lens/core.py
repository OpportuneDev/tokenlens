from __future__ import annotations

import uuid
from typing import Any

from .analyzer import decompose
from .models import RequestAnalysis
from .patterns import run_all
from .reporter import compute_efficiency_score, print_report
from . import store as _store


def analyse(
    request: dict,
    output_tokens: int | None = None,
    provider: str | None = None,
    print_result: bool = True,
    persist: bool = True,
) -> RequestAnalysis:
    segments, detected_provider = decompose(request, provider)
    total_input = sum(s.tokens for s in segments)
    flags = run_all(segments, request, output_tokens)

    recoverable = sum(f.tokens_wasted for f in flags)
    recoverable_pct = (recoverable / total_input * 100) if total_input else 0.0

    analysis = RequestAnalysis(
        request_id=str(uuid.uuid4())[:8],
        model=request.get("model", "unknown"),
        provider=detected_provider,
        segments=segments,
        total_input_tokens=total_input,
        output_tokens=output_tokens,
        waste_flags=flags,
        recoverable_tokens=min(recoverable, total_input),
        recoverable_pct=min(recoverable_pct, 100.0),
    )
    analysis.efficiency_score = compute_efficiency_score(analysis)

    if print_result:
        print_report(analysis)

    if persist:
        _store.write(analysis)

    return analysis
