"""
Token counting utilities.

Uses tiktoken (cl100k_base) as a fast local approximation for both
OpenAI and Anthropic models. Accurate to within ~5% for most content.
"""
from __future__ import annotations

import json
from typing import Any

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
    def _count(text: str) -> int:
        return len(_enc.encode(text))
except ImportError:
    # Fallback: rough approximation (4 chars per token)
    def _count(text: str) -> int:  # type: ignore[misc]
        return max(1, len(text) // 4)


def count_text(text: str) -> int:
    return _count(text)


def count_messages(messages: list[dict]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += _count(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total += _count(block.get("text", "") or json.dumps(block))
        total += 4  # per-message overhead (role tokens + delimiters)
    return total


def count_tools(tools: list[dict]) -> int:
    return _count(json.dumps(tools))


def count_any(obj: Any) -> int:
    if isinstance(obj, str):
        return _count(obj)
    return _count(json.dumps(obj))
