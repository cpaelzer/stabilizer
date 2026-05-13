# Copyright 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only

"""StabilizerOrchestrator - Main coordinator with Rich progress display."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from stabilizer.types import StabilizerState
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
    """Run the full Stabilizer pipeline."""
    console = Console()
    state = StabilizerState(
        package=package,
        target_release=target_release,
        source_release=source_release,
        output_dir=output_dir,
    )

    console.print(f"\n[bold cyan]Stabilizer: Analyzing {package} ({target_release} → {source_release})[/bold cyan]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for phase_name, phase_func in PHASES:
            task = progress.add_task(f"[cyan]{phase_name}...", total=None)
            state.current_phase = phase_name
            state.phase_progress = "Running..."

            try:
                state = phase_func(state)
                progress.update(task, description=f"[green]✓ {phase_name}")
            except Exception as e:
                progress.update(task, description=f"[red]✗ {phase_name}: {e}")
                console.print(f"\n[red]Error in phase '{phase_name}': {e}[/red]")
                raise

    return state
