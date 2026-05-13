# Copyright 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only

"""StabilizerIdentifyApplicableFixes - Tests cherry-pick applicability."""

from __future__ import annotations

from stabilizer.types import ApplicableChange, ExclusionRecord, StabilizerState
from stabilizer.utils import (
    add_remote,
    checkout_branch,
    cherry_pick_dry_run,
    fetch_remote,
)


def run(state: StabilizerState) -> StabilizerState:
    """Test if safe changes apply cleanly via cherry-pick."""
    if not state.safe_changes:
        return state

    pkg_path = state.work_dir / state.package

    # Try multiple candidate branches for the target release in order of preference
    branch_candidates = [
        f"ubuntu/{state.target_release}",
        f"applied/{state.target_release}",
        f"pkg/applied/{state.target_release}-devel",
        f"applied/{state.target_release}-devel",
        state.target_release,
        "ubuntu/devel",
        "main",
        "master",
    ]
    checkout_success = False
    selected_branch = None
    for candidate in branch_candidates:
        try:
            checkout_branch(pkg_path, candidate)
            selected_branch = candidate
            checkout_success = True
            print(f"  [dim]→ Using target branch: {candidate}[/dim]")
            break
        except Exception:
            continue

    if not checkout_success:
        print("  [yellow]Warning: Could not checkout specific target branch, using current checkout[/yellow]")

    # Add upstream remote if not already added
    if state.repository:
        add_remote(pkg_path, "upstream", state.repository.url)
        fetch_remote(pkg_path, "upstream")

    applicable = []
    for change_group in state.safe_changes:
        # Try cherry-picking each commit in the group
        all_apply = True
        cherry_output = ""
        for commit in change_group.commits:
            success, output = cherry_pick_dry_run(pkg_path, commit.sha)
            cherry_output += output
            if not success:
                all_apply = False
                break

        if all_apply:
            applicable.append(
                ApplicableChange(
                    change_group=change_group,
                    applies_cleanly=True,
                    cherry_pick_output=cherry_output,
                )
            )
        else:
            state.exclusions.append(
                ExclusionRecord(
                    change_title=change_group.title,
                    stage="applicable",
                    reason=f"Cherry-pick failed: {cherry_output[:200]}",
                )
            )

    state.applicable_changes = applicable
    return state
