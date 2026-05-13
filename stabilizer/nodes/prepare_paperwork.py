# Copyright 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only

"""StabilizerPreparePaperwork - Generates SRU bug template files."""

from __future__ import annotations

import re

from stabilizer.types import SRUBug, StabilizerState


def _generate_bug_title(change: SRUBug) -> str:
    """Generate a filename-safe bug title."""
    title = change.title
    # Remove special characters and replace spaces with hyphens
    title = re.sub(r"[^a-zA-Z0-9\s-]", "", title)
    title = re.sub(r"\s+", "-", title)
    # Truncate if too long
    if len(title) > 80:
        title = title[:80]
    return f"{title}.bug"


def _format_sru_bug(bug: SRUBug) -> str:
    """Format an SRU bug following the official template."""
    template = """[ Impact ]

{impact}

[ Test Plan ]

{test_plan}

[ Where problems could occur ]

{regression_potential}

[ Other Info ]

{other_info}
"""
    return template.format(
        impact=bug.impact,
        test_plan=bug.test_plan,
        regression_potential=bug.regression_potential,
        other_info=bug.other_info,
    )


def run(state: StabilizerState) -> StabilizerState:
    """Generate SRU bug template files for testable changes."""
    output_dir = state.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    for tc in state.testable_changes:
        if not tc.testable:
            continue

        change_group = tc.applicable_change.change_group

        # Build the SRU bug content
        commit_refs = ", ".join(c.short_sha for c in change_group.commits)
        other_info = f"Commits: {commit_refs}\nPackage: {state.package}\nTarget release: {state.target_release}\nSource release: {state.source_release}"

        bug = SRUBug(
            title=change_group.title,
            filename="",
            impact=change_group.impact,
            test_plan=tc.test_description,
            regression_potential=change_group.regression_risk,
            other_info=other_info,
            commits=change_group.commits,
        )
        bug.filename = _generate_bug_title(bug)

        # Write the bug file
        bug_path = output_dir / bug.filename
        with open(bug_path, "w") as f:
            f.write(_format_sru_bug(bug))

        state.sru_bugs.append(bug)

    return state
