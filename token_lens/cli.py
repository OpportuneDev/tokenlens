"""
CLI entry point: token-lens <request.json>
"""
from __future__ import annotations

import json
import sys


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: token-lens <request.json> [--monthly-calls N] [--provider anthropic|openai]")
        print("       cat request.json | token-lens -")
        sys.exit(0)

    monthly_calls = 10_000
    provider = None

    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--monthly-calls" and i + 1 < len(args):
            monthly_calls = int(args[i + 1])
        if arg == "--provider" and i + 1 < len(args):
            provider = args[i + 1]

    path = args[0]
    if path == "-":
        data = json.load(sys.stdin)
    else:
        with open(path) as f:
            data = json.load(f)

    from .core import analyse
    analyse(data, provider=provider, monthly_calls=monthly_calls)
