# Copyright 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only

"""StabilizerOrchestrator - Main coordinator with Rich progress display."""

from __future__ import annotations

import tempfile
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from stabilizer.nodes import (
    get_repository,
    identify_applicable_fixes,
    identify_commit_range,
    identify_safe_changes,
    identify_testable_changes,
    prepare_paperwork,
    report,
    version_identifier,
)
from stabilizer.types import StabilizerState

PHASES = [
    ("Identifying versions", version_identifier.run),
    ("Detecting upstream repository", get_repository.run),
    ("Identifying commit range", identify_commit_range.run),
    ("Classifying safe changes", identify_safe_changes.run),
    ("Testing cherry-pick applicability", identify_applicable_fixes.run),
    ("Generating test plans", identify_testable_changes.run),
    ("Preparing SRU paperwork", prepare_paperwork.run),
    ("Generating report", report.run),
]


def run(
    package: str,
    target_release: str,
    source_release: str,
    output_dir: Path = Path("output"),
) -> StabilizerState:
    """Run the full Stabilizer pipeline with rich progress reporting."""
    console = Console()
    state = StabilizerState(
        package=package,
        target_release=target_release,
        source_release=source_release,
        output_dir=output_dir,
    )

    console.print(
        f"\n[bold cyan]Stabilizer: Analyzing {package} ({target_release} → {source_release})[/bold cyan]\n"
    )

    # Use temporary directory for work files with automatic cleanup
    with tempfile.TemporaryDirectory(prefix="stabilizer-") as temp_dir:
        state.work_dir = Path(temp_dir)
        console.print(f"[dim]Working directory: {state.work_dir}[/dim]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            for phase_name, phase_func in PHASES:
                task = progress.add_task(f"[cyan]{phase_name}...", total=None)
                state.current_phase = phase_name

                try:
                    state = phase_func(state)
                    # Report phase outcome
                    _report_phase_outcome(console, phase_name, state)
                    progress.update(task, description=f"[green]✓ {phase_name}")
                except Exception as e:
                    progress.update(task, description=f"[red]✗ {phase_name}: {e}")
                    console.print(f"\n[red]Error in phase '{phase_name}': {e}[/red]")
                    raise

    return state


def _report_phase_outcome(console: Console, phase_name: str, state: StabilizerState) -> None:
    """Report the outcome of a phase with relevant details."""
    if phase_name == "Identifying versions":
        if state.target_version and state.source_version:
            console.print(
                f"  [green]✓[/green] Found versions: "
                f"[cyan]{state.target_release}[/cyan]={state.target_version.version} "
                f"[cyan]{state.source_release}[/cyan]={state.source_version.version}"
            )
    elif phase_name == "Detecting upstream repository":
        if state.repository:
            console.print(
                f"  [green]✓[/green] Upstream: {state.repository.url} (from {state.repository.source})"
            )
    elif phase_name == "Identifying commit range":
        if state.target_tag and state.source_tag:
            console.print(
                f"  [green]✓[/green] Found tags: "
                f"{state.target_tag}..{state.source_tag} "
                f"({len(state.all_commits)} commits)"
            )
    elif phase_name == "Classifying safe changes":
        console.print(
            f"  [green]✓[/green] Safe changes: {len(state.safe_changes)} "
            f"(excluded: {len([e for e in state.exclusions if e.stage == 'safe_changes'])})"
        )
    elif phase_name == "Testing cherry-pick applicability":
        console.print(
            f"  [green]✓[/green] Applicable: {len(state.applicable_changes)} "
            f"(excluded: {len([e for e in state.exclusions if e.stage == 'applicable'])})"
        )
    elif phase_name == "Generating test plans":
        console.print(
            f"  [green]✓[/green] Testable: {len(state.testable_changes)} "
            f"(excluded: {len([e for e in state.exclusions if e.stage == 'testable'])})"
        )
    elif phase_name == "Preparing SRU paperwork":
        console.print(f"  [green]✓[/green] Generated {len(state.sru_bugs)} SRU bug templates")
