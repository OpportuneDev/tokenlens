"""
SDK-level monkey patching.

Patches the Anthropic and/or OpenAI SDK at the method level so every call
made by any framework (LangChain, LlamaIndex, CrewAI, etc.) is intercepted
automatically — no client wrapping needed.

Usage:
    import token_lens
    token_lens.patch()          # patches both SDKs if installed

    token_lens.patch("anthropic")   # patch only Anthropic
    token_lens.patch("openai")      # patch only OpenAI
"""
from __future__ import annotations

from typing import Callable
from .core import analyse

_patched: set[str] = set()


def _patch_anthropic(on_analysis: Callable | None = None) -> None:
    try:
        import anthropic.resources.messages
    except ImportError:
        return

    target = anthropic.resources.messages.Messages
    if "anthropic" in _patched:
        return

    original_create = target.create

    def patched_create(self, **kwargs):
        response = original_create(self, **kwargs)
        output_tokens = None
        if hasattr(response, "usage") and response.usage:
            output_tokens = getattr(response.usage, "output_tokens", None)
        result = analyse(kwargs, output_tokens=output_tokens, provider="anthropic")
        if on_analysis:
            on_analysis(result)
        return response

    target.create = patched_create
    _patched.add("anthropic")


def _patch_openai(on_analysis: Callable | None = None) -> None:
    try:
        import openai.resources.chat.completions
    except ImportError:
        return

    target = openai.resources.chat.completions.Completions
    if "openai" in _patched:
        return

    original_create = target.create

    def patched_create(self, **kwargs):
        response = original_create(self, **kwargs)
        output_tokens = None
        if hasattr(response, "usage") and response.usage:
            output_tokens = getattr(response.usage, "completion_tokens", None)
        result = analyse(kwargs, output_tokens=output_tokens, provider="openai")
        if on_analysis:
            on_analysis(result)
        return response

    target.create = patched_create
    _patched.add("openai")


def patch(provider: str = "all", on_analysis: Callable | None = None) -> None:
    """
    Patch the Anthropic and/or OpenAI SDK so every LLM call is analysed.

    Args:
        provider:    "all" (default), "anthropic", or "openai"
        on_analysis: optional callback receiving a RequestAnalysis object
                     after each call. Use this to log/store results instead
                     of printing them.
    """
    if provider in ("all", "anthropic"):
        _patch_anthropic(on_analysis)
    if provider in ("all", "openai"):
        _patch_openai(on_analysis)


def unpatch() -> None:
    """Remove all patches. Restores original SDK methods."""
    if "anthropic" in _patched:
        try:
            import anthropic.resources.messages
            import importlib
            importlib.reload(anthropic.resources.messages)
            _patched.discard("anthropic")
        except Exception:
            pass

    if "openai" in _patched:
        try:
            import openai.resources.chat.completions
            import importlib
            importlib.reload(openai.resources.chat.completions)
            _patched.discard("openai")
        except Exception:
            pass
