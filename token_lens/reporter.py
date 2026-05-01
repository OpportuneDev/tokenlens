"""
Terminal reporter using Rich.
Falls back to plain text if Rich is not installed.
"""
from __future__ import annotations

from .models import RequestAnalysis, WasteSeverity

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False


def _score_color(score: int) -> str:
    if score >= 80:
        return "green"
    if score >= 50:
        return "yellow"
    return "red"


def _severity_color(sev: WasteSeverity) -> str:
    return {"HIGH": "red", "MEDIUM": "yellow", "LOW": "cyan"}.get(sev.value, "white")


def compute_efficiency_score(analysis: RequestAnalysis) -> int:
    if analysis.total_input_tokens == 0:
        return 100
    waste_ratio = analysis.recoverable_tokens / analysis.total_input_tokens
    return max(0, int(100 - (waste_ratio * 100)))


def print_report(analysis: RequestAnalysis) -> None:
    if _HAS_RICH:
        _rich_report(analysis)
    else:
        _plain_report(analysis)


def _rich_report(analysis: RequestAnalysis) -> None:
    console = Console()

    console.print()
    console.print(Panel(
        f"[bold]token-lens[/bold]  ·  [dim]{analysis.model}[/dim]  ·  "
        f"[dim]{analysis.provider}[/dim]",
        style="bold blue",
    ))

    # ── Token breakdown ───────────────────────────────────────────────────────
    seg_table = Table(title="Token Breakdown", box=box.SIMPLE_HEAD, show_footer=True)
    seg_table.add_column("Segment",      style="cyan",  footer="TOTAL")
    seg_table.add_column("Tokens",       justify="right", footer=str(analysis.total_input_tokens))
    seg_table.add_column("% of context", justify="right", footer="100%")

    for seg in analysis.segments:
        pct = (seg.tokens / analysis.total_input_tokens * 100) if analysis.total_input_tokens else 0
        seg_table.add_row(seg.name, str(seg.tokens), f"{pct:.1f}%")

    if analysis.output_tokens:
        seg_table.add_row(
            "[dim]output (generated)[/dim]",
            f"[dim]{analysis.output_tokens}[/dim]",
            "",
        )

    console.print(seg_table)

    # ── Efficiency score ──────────────────────────────────────────────────────
    score = analysis.efficiency_score
    color = _score_color(score)
    console.print(
        f"\n  Efficiency score: [{color}]{score}/100[/{color}]   "
        f"Recoverable tokens: [yellow]{analysis.recoverable_tokens}[/yellow] "
        f"([yellow]{analysis.recoverable_pct:.1f}%[/yellow])\n"
    )

    # ── Waste flags ───────────────────────────────────────────────────────────
    if not analysis.waste_flags:
        console.print("  [green]No waste patterns detected.[/green]\n")
        return

    flag_table = Table(title="Waste Flags", box=box.SIMPLE_HEAD)
    flag_table.add_column("Severity",      style="bold", width=8)
    flag_table.add_column("Pattern",       style="bold cyan")
    flag_table.add_column("Tokens wasted", justify="right")
    flag_table.add_column("Detail")
    flag_table.add_column("Fix")

    flags_sorted = sorted(
        analysis.waste_flags,
        key=lambda f: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[f.severity.value],
    )
    for flag in flags_sorted:
        sc = _severity_color(flag.severity)
        flag_table.add_row(
            f"[{sc}]{flag.severity.value}[/{sc}]",
            flag.pattern,
            str(flag.tokens_wasted),
            flag.detail[:60] + ("…" if len(flag.detail) > 60 else ""),
            flag.fix[:60] + ("…" if len(flag.fix) > 60 else ""),
        )

    console.print(flag_table)
    console.print()


def _plain_report(analysis: RequestAnalysis) -> None:
    print(f"\n=== token-lens | {analysis.model} | {analysis.provider} ===")
    print(f"\nToken Breakdown (total input: {analysis.total_input_tokens})")
    for seg in analysis.segments:
        pct = (seg.tokens / analysis.total_input_tokens * 100) if analysis.total_input_tokens else 0
        print(f"  {seg.name:<30} {seg.tokens:>6} tokens  ({pct:.1f}%)")
    if analysis.output_tokens:
        print(f"  {'output':<30} {analysis.output_tokens:>6} tokens")

    print(f"\nEfficiency score: {analysis.efficiency_score}/100")
    print(f"Recoverable tokens: {analysis.recoverable_tokens} ({analysis.recoverable_pct:.1f}%)")

    if not analysis.waste_flags:
        print("\nNo waste patterns detected.\n")
        return

    print("\nWaste Flags:")
    for flag in sorted(analysis.waste_flags, key=lambda f: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[f.severity.value]):
        print(f"  [{flag.severity.value}] {flag.pattern} — {flag.tokens_wasted} tokens wasted")
        print(f"    {flag.detail}")
        print(f"    Fix: {flag.fix}")
    print()
