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

# Pricing per million tokens, by role.
# Source: provider pricing pages — update as pricing changes.
# Structure: { model_key: (input_price, output_price) }
_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus":    (15.0,  75.0),
    "claude-sonnet":  ( 3.0,  15.0),
    "claude-haiku":   ( 0.25,  1.25),
    "gpt-4o":         ( 2.5,  10.0),
    "gpt-4o-mini":    ( 0.15,  0.60),
    "gpt-4-turbo":    (10.0,  30.0),
    "gpt-3.5-turbo":  ( 0.5,   1.50),
}
_DEFAULT_PRICING = (3.0, 15.0)  # Sonnet fallback


def _get_pricing(model: str) -> tuple[float, float]:
    """Returns (input_price_per_token, output_price_per_token)."""
    for key, (inp, out) in _PRICING.items():
        if key in model.lower():
            return inp / 1_000_000, out / 1_000_000
    return _DEFAULT_PRICING[0] / 1_000_000, _DEFAULT_PRICING[1] / 1_000_000


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
    input_cpt, output_cpt = _get_pricing(analysis.model)

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
    flag_table.add_column("Severity",       style="bold", width=8)
    flag_table.add_column("Pattern",        style="bold cyan")
    flag_table.add_column("Tokens wasted",  justify="right")
    flag_table.add_column("Cost wasted",    justify="right")
    flag_table.add_column("Detail")
    flag_table.add_column("Fix")

    flags_sorted = sorted(
        analysis.waste_flags,
        key=lambda f: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[f.severity.value],
    )
    for flag in flags_sorted:
        sc = _severity_color(flag.severity)
        # Waste is in input tokens unless it's a verbose output flag
        cpt = output_cpt if flag.pattern == "VERBOSE_OUTPUT" else input_cpt
        call_cost = flag.tokens_wasted * cpt
        flag_table.add_row(
            f"[{sc}]{flag.severity.value}[/{sc}]",
            flag.pattern,
            str(flag.tokens_wasted),
            f"${call_cost:.6f}",
            flag.detail[:55] + ("…" if len(flag.detail) > 55 else ""),
            flag.fix[:55] + ("…" if len(flag.fix) > 55 else ""),
        )

    # Total: input waste + output waste (verbose output flag)
    input_waste = sum(f.tokens_wasted for f in flags_sorted if f.pattern != "VERBOSE_OUTPUT")
    output_waste = sum(f.tokens_wasted for f in flags_sorted if f.pattern == "VERBOSE_OUTPUT")
    total_waste_cost = (input_waste * input_cpt) + (output_waste * output_cpt)
    console.print(flag_table)
    console.print(f"  [bold]Cost wasted this call:[/bold] [red]${total_waste_cost:.6f}[/red]  "
                  f"[dim](input @ ${input_cpt*1_000_000:.2f}/MTok, "
                  f"output @ ${output_cpt*1_000_000:.2f}/MTok)[/dim]\n")


def _plain_report(analysis: RequestAnalysis) -> None:
    input_cpt, output_cpt = _get_pricing(analysis.model)
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
        cpt = output_cpt if flag.pattern == "VERBOSE_OUTPUT" else input_cpt
        call_cost = flag.tokens_wasted * cpt
        print(f"  [{flag.severity.value}] {flag.pattern} — {flag.tokens_wasted} tokens (${call_cost:.6f})")
        print(f"    {flag.detail}")
        print(f"    Fix: {flag.fix}")

    input_waste = sum(f.tokens_wasted for f in analysis.waste_flags if f.pattern != "VERBOSE_OUTPUT")
    output_waste = sum(f.tokens_wasted for f in analysis.waste_flags if f.pattern == "VERBOSE_OUTPUT")
    total = (input_waste * input_cpt) + (output_waste * output_cpt)
    print(f"\nCost wasted this call: ${total:.6f} "
          f"(input @ ${input_cpt*1_000_000:.2f}/MTok, output @ ${output_cpt*1_000_000:.2f}/MTok)\n")
