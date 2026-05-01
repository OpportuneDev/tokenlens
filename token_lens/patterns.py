"""
Waste pattern detection.
Each checker receives the segment list and full request, returns WasteFlag | None.
"""
from __future__ import annotations

from .models import TokenSegment, WasteFlag, WasteSeverity

# ── Thresholds (override via config) ────────────────────────────────────────
SYSTEM_PROMPT_CACHE_THRESHOLD = 200    # tokens — below this, caching isn't worth it
HISTORY_TURN_WARN  = 10               # turns
HISTORY_TURN_HIGH  = 20               # turns
TOOL_TOKEN_WARN    = 800              # tokens
TOOL_TOKEN_HIGH    = 2000             # tokens
ERROR_TOKEN_WARN   = 200              # tokens of error content in history
OUTPUT_RATIO_WARN  = 0.6              # output/input ratio
LARGE_MSG_WARN     = 2000             # single message tokens (likely RAG dump)


def _seg(segments: list[TokenSegment], name: str) -> TokenSegment | None:
    for s in segments:
        if s.name == name:
            return s
    return None


def check_uncached_system_prompt(segments, request, output_tokens=None):
    s = _seg(segments, "system_prompt")
    if not s:
        return None
    if s.details.get("cached"):
        return None
    if s.tokens < SYSTEM_PROMPT_CACHE_THRESHOLD:
        return None
    return WasteFlag(
        pattern="UNCACHED_SYSTEM_PROMPT",
        severity=WasteSeverity.HIGH,
        tokens_wasted=s.tokens,
        detail=f"System prompt is {s.tokens} tokens and not cached. "
               f"Repeated verbatim on every call.",
        fix='Add cache_control: {"type": "ephemeral"} to your system prompt block.',
    )


def check_unbounded_history(segments, request, output_tokens=None):
    s = _seg(segments, "conversation_history")
    if not s:
        return None
    turns = s.details.get("turns", 0)
    if turns < HISTORY_TURN_WARN:
        return None
    severity = WasteSeverity.HIGH if turns >= HISTORY_TURN_HIGH else WasteSeverity.MEDIUM
    # Rough estimate: last 8 turns cover ~80% of relevant context
    safe_turns = 8
    safe_tokens = int(s.tokens * (safe_turns / turns))
    wasted = s.tokens - safe_tokens
    return WasteFlag(
        pattern="UNBOUNDED_HISTORY",
        severity=severity,
        tokens_wasted=wasted,
        detail=f"{turns} turns of history in context. "
               f"Last {safe_turns} turns likely cover all relevant context.",
        fix=f"Truncate history to last {safe_turns} turns, or summarize older turns into a digest.",
    )


def check_error_accumulation(segments, request, output_tokens=None):
    s = _seg(segments, "conversation_history")
    if not s:
        return None
    error_tokens = s.details.get("error_tokens", 0)
    error_count  = s.details.get("error_turns", 0)
    if error_tokens < ERROR_TOKEN_WARN:
        return None
    return WasteFlag(
        pattern="ERROR_ACCUMULATION",
        severity=WasteSeverity.MEDIUM,
        tokens_wasted=error_tokens,
        detail=f"{error_count} message(s) containing error content "
               f"({error_tokens} tokens) are being re-sent every turn.",
        fix="Strip error bodies to status + one line before injecting into context. "
            "On retries, summarise what failed instead of pasting the raw response.",
    )


def check_tool_overhead(segments, request, output_tokens=None):
    s = _seg(segments, "tool_definitions")
    if not s:
        return None
    if s.tokens < TOOL_TOKEN_WARN:
        return None
    severity = WasteSeverity.HIGH if s.tokens >= TOOL_TOKEN_HIGH else WasteSeverity.MEDIUM
    count = s.details.get("count", 0)
    return WasteFlag(
        pattern="LARGE_TOOL_DEFINITIONS",
        severity=severity,
        tokens_wasted=s.tokens,
        detail=f"{count} tool definitions consume {s.tokens} tokens on every call, "
               f"whether used or not.",
        fix="Implement dynamic tool loading: classify intent first, then inject only "
            "the tools relevant to that intent.",
    )


def check_verbose_output(segments, request, output_tokens=None):
    if output_tokens is None:
        return None
    total_input = sum(s.tokens for s in segments)
    if total_input == 0:
        return None
    ratio = output_tokens / total_input
    if ratio < OUTPUT_RATIO_WARN:
        return None
    return WasteFlag(
        pattern="VERBOSE_OUTPUT",
        severity=WasteSeverity.MEDIUM,
        tokens_wasted=int(output_tokens * 0.3),  # conservative: 30% likely avoidable
        detail=f"Output/input ratio is {ratio:.1f}x. "
               f"Output tokens ({output_tokens}) are 3-5x more expensive than input.",
        fix="Add length constraints to your prompt. Use concise response formats "
            "(pipe-delimited, structured fields) instead of prose where possible. "
            "Set max_tokens explicitly.",
    )


def check_large_single_message(segments, request, output_tokens=None):
    flags = []
    for s in segments:
        if s.name in ("conversation_history", "tool_definitions", "system_prompt"):
            continue
        if s.tokens >= LARGE_MSG_WARN:
            flags.append(WasteFlag(
                pattern="LARGE_SINGLE_CONTEXT_BLOCK",
                severity=WasteSeverity.MEDIUM,
                tokens_wasted=int(s.tokens * 0.4),
                detail=f"'{s.name}' is {s.tokens} tokens. "
                       f"May indicate unfiltered RAG chunks or full API response injection.",
                fix="Filter retrieved chunks to the fields/sentences that matter. "
                    "Set a similarity threshold and reduce k in RAG retrieval.",
            ))
    return flags or None


# ── Registry ─────────────────────────────────────────────────────────────────
_CHECKERS = [
    check_uncached_system_prompt,
    check_unbounded_history,
    check_error_accumulation,
    check_tool_overhead,
    check_verbose_output,
    check_large_single_message,
]


def run_all(segments: list[TokenSegment], request: dict, output_tokens: int | None = None) -> list[WasteFlag]:
    flags: list[WasteFlag] = []
    for checker in _CHECKERS:
        result = checker(segments, request, output_tokens)
        if result is None:
            continue
        if isinstance(result, list):
            flags.extend(result)
        else:
            flags.append(result)
    return flags
