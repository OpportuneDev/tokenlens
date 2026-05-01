"""
Decomposes a raw LLM API request into labeled token segments.
Supports Anthropic and OpenAI request formats.
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from .models import TokenSegment
from .tokenizer import count_text, count_messages, count_tools, count_any

# Heuristics for detecting injected errors in message content
_ERROR_PATTERNS = re.compile(
    r"(error|exception|traceback|stack trace|500|502|503|failed|4\d\d\s)",
    re.IGNORECASE,
)


def _is_anthropic(request: dict) -> bool:
    return "system" in request or (
        "messages" in request
        and any(m.get("role") == "user" for m in request.get("messages", []))
        and "model" in request
        and "claude" in request.get("model", "").lower()
    )


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
        return " ".join(parts)
    return ""


def _has_cache_control(content: Any) -> bool:
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and "cache_control" in block:
                return True
    return False


def decompose(request: dict, provider: str | None = None) -> tuple[list[TokenSegment], str]:
    """
    Returns (segments, detected_provider).
    Provider is 'anthropic' or 'openai'.
    """
    model = request.get("model", "unknown")
    messages: list[dict] = request.get("messages", [])
    tools: list[dict] = request.get("tools") or request.get("functions") or []
    segments: list[TokenSegment] = []

    if provider is None:
        provider = "anthropic" if _is_anthropic(request) else "openai"

    # ── System prompt ────────────────────────────────────────────────────────
    system_text = ""
    system_cached = False

    if provider == "anthropic":
        raw_system = request.get("system", "")
        system_text = _extract_text(raw_system)
        system_cached = _has_cache_control(raw_system)
    else:
        # OpenAI: system is first message with role=system
        sys_msgs = [m for m in messages if m.get("role") == "system"]
        if sys_msgs:
            system_text = _extract_text(sys_msgs[0].get("content", ""))

    if system_text:
        sys_tokens = count_text(system_text)
        segments.append(TokenSegment(
            name="system_prompt",
            tokens=sys_tokens,
            details={"cached": system_cached, "chars": len(system_text)},
        ))

    # ── Conversation history (all but last user turn) ────────────────────────
    non_system = [m for m in messages if m.get("role") != "system"]
    # Last message is the current user turn; everything before is history
    history_msgs = non_system[:-1] if len(non_system) > 1 else []
    current_msg  = non_system[-1] if non_system else None

    # Detect errors embedded in history
    error_tokens = 0
    error_count = 0
    for msg in history_msgs:
        text = _extract_text(msg.get("content", ""))
        if _ERROR_PATTERNS.search(text):
            error_count += 1
            error_tokens += count_text(text)

    if history_msgs:
        hist_tokens = count_messages(history_msgs)
        segments.append(TokenSegment(
            name="conversation_history",
            tokens=hist_tokens,
            details={
                "turns": len(history_msgs),
                "error_turns": error_count,
                "error_tokens": error_tokens,
            },
        ))

    # ── Current user message ─────────────────────────────────────────────────
    if current_msg:
        cur_tokens = count_messages([current_msg])
        segments.append(TokenSegment(
            name="user_message",
            tokens=cur_tokens,
            details={"role": current_msg.get("role", "user")},
        ))

    # ── Tool definitions ─────────────────────────────────────────────────────
    if tools:
        tool_tokens = count_tools(tools)
        segments.append(TokenSegment(
            name="tool_definitions",
            tokens=tool_tokens,
            details={"count": len(tools), "names": [t.get("name", "") for t in tools]},
        ))

    return segments, provider
