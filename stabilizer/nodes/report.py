# Copyright 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only

"""StabilizerReport - Final summary report."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from stabilizer.types import StabilizerState


def run(state: StabilizerState) -> StabilizerState:
    """Generate final summary report."""
    console = Console()

    console.print("\n" + "=" * 60)
    console.print(f"[bold]Stabilizer Report: {state.package}[/bold]")
    console.print(f"Target: {state.target_release} ({state.target_version.version if state.target_version else 'N/A'})")
    console.print(f"Source: {state.source_release} ({state.source_version.version if state.source_version else 'N/A'})")
    console.print("=" * 60)

    # Summary statistics
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Total commits analyzed: {len(state.all_commits)}")
    console.print(f"  Safe changes identified: {len(state.safe_changes)}")
    console.print(f"  Applicable changes: {len(state.applicable_changes)}")
    console.print(f"  Testable changes: {len(state.testable_changes)}")
    console.print(f"  SRU bug templates generated: {len(state.sru_bugs)}")

    # SRU bugs
    if state.sru_bugs:
        console.print("\n[bold green]Generated SRU Bug Templates:[/bold green]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Filename")
        table.add_column("Title")
        table.add_column("Commits")

        for bug in state.sru_bugs:
            table.add_row(
                bug.filename,
                bug.title,
                f"{len(bug.commits)} commit(s)",
            )
        console.print(table)

    # Exclusions
    if state.exclusions:
        console.print("\n[bold yellow]Excluded Changes:[/bold yellow]")
        table = Table(show_header=True, header_style="bold yellow")
        table.add_column("Change")
        table.add_column("Stage")
        table.add_column("Reason")

        for exc in state.exclusions:
            table.add_row(
                exc.change_title[:60],
                exc.stage,
                exc.reason[:80],
            )
        console.print(table)

    # Output location
    console.print(f"\n[bold]Output directory:[/bold] {state.output_dir}")

    return state
