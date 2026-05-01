"""
Transparent SDK wrappers.

Usage:
    from token_lens import DiagnosticWrapper
    import anthropic

    client = DiagnosticWrapper(anthropic.Anthropic())
    response = client.messages.create(model="claude-sonnet-4-6", ...)

Also works with OpenAI:
    import openai
    client = DiagnosticWrapper(openai.OpenAI())
    response = client.chat.completions.create(model="gpt-4o", ...)
"""
from __future__ import annotations

from typing import Any

from .core import analyse


class _MessagesProxy:
    def __init__(self, messages, silent: bool):
        self._messages = messages
        self._silent = silent

    def create(self, **kwargs) -> Any:
        response = self._messages.create(**kwargs)
        output_tokens = None
        if hasattr(response, "usage") and response.usage:
            output_tokens = getattr(response.usage, "output_tokens", None)
        analyse(kwargs, output_tokens=output_tokens, provider="anthropic", print_result=not self._silent)
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._messages, name)


class _ChatCompletionsProxy:
    def __init__(self, completions, silent: bool):
        self._completions = completions
        self._silent = silent

    def create(self, **kwargs) -> Any:
        response = self._completions.create(**kwargs)
        output_tokens = None
        if hasattr(response, "usage") and response.usage:
            output_tokens = getattr(response.usage, "completion_tokens", None)
        analyse(kwargs, output_tokens=output_tokens, provider="openai", print_result=not self._silent)
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._completions, name)


class _ChatProxy:
    def __init__(self, chat, silent: bool):
        self.completions = _ChatCompletionsProxy(chat.completions, silent)
        self._chat = chat

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)


class DiagnosticWrapper:
    """
    Drop-in wrapper for Anthropic or OpenAI client.
    Reports token waste after every call. No configuration needed.

    Args:
        client: An anthropic.Anthropic() or openai.OpenAI() instance
        silent: Suppress printed reports (analysis still runs, result still returned)
    """

    def __init__(self, client: Any, silent: bool = False):
        self._client = client

        client_type = type(client).__module__ or ""
        if "anthropic" in client_type or hasattr(client, "messages"):
            self.messages = _MessagesProxy(client.messages, silent)
        if "openai" in client_type or hasattr(client, "chat"):
            self.chat = _ChatProxy(client.chat, silent)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)
