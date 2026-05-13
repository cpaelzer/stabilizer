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
    console.print(
        f"Target: {state.target_release} ({state.target_version.version if state.target_version else 'N/A'})"
    )
    console.print(
        f"Source: {state.source_release} ({state.source_version.version if state.source_version else 'N/A'})"
    )
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

    # Exclusions - grouped by stage with clear reasoning
    if state.exclusions:
        console.print("\n[bold yellow]Changes Evaluated But Not Selected:[/bold yellow]")
        console.print("  (These were considered but did not meet SRU criteria)")

        # Group exclusions by stage
        by_stage: dict[str, list] = {}
        for exc in state.exclusions:
            by_stage.setdefault(exc.stage, []).append(exc)

        for stage, exclusions in by_stage.items():
            console.print(
                f"\n  [yellow]{stage.replace('_', ' ').title()}:[/yellow] {len(exclusions)} change(s) excluded"
            )
            table = Table(show_header=True, header_style="bold yellow", show_lines=True)
            table.add_column("Change", width=50)
            table.add_column("Reason", width=60)

            for exc in exclusions[:8]:  # Limit to prevent flooding console
                table.add_row(
                    exc.change_title[:47] + ("..." if len(exc.change_title) > 47 else ""),
                    exc.reason[:57] + ("..." if len(exc.reason) > 57 else ""),
                )
            console.print(table)

            if len(exclusions) > 8:
                console.print(f"    ... and {len(exclusions) - 8} more exclusions")

        console.print(
            "\n[yellow]Note:[/yellow] SRU requires changes to be safe, applicable, and testable."
        )
        console.print("  Only changes that pass all three filters generate SRU bug templates.")

    # Output location
    console.print(f"\n[bold]Output directory:[/bold] {state.output_dir}")

    return state
