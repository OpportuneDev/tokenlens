"""
CLI entry point: token-lens <request.json> | token-lens dashboard
"""
from __future__ import annotations

import json
import sys


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print("Usage:")
        print("  token-lens dashboard              Launch the visual dashboard")
        print("  token-lens <request.json>         Analyse a saved request file")
        print("  cat request.json | token-lens -   Analyse from stdin")
        sys.exit(0)

    if args[0] == "dashboard":
        import subprocess
        import os
        dashboard_path = str(__import__("pathlib").Path(__file__).parent / "dashboard.py")
        subprocess.run(["streamlit", "run", dashboard_path], check=True)
        return

    provider = None
    path = args[0]
    for i, arg in enumerate(args):
        if arg == "--provider" and i + 1 < len(args):
            provider = args[i + 1]

    if path == "-":
        data = json.load(sys.stdin)
    else:
        with open(path) as f:
            data = json.load(f)

    from .core import analyse
    analyse(data, provider=provider)
