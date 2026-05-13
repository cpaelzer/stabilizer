# Copyright 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only

"""StabilizerIdentifyApplicableFixes - Tests cherry-pick applicability."""

from __future__ import annotations

from stabilizer.types import ApplicableChange, ChangeGroup, CommitInfo, ExclusionRecord, StabilizerState
from stabilizer.utils import (
    add_remote,
    checkout_branch,
    cherry_pick_dry_run,
    fetch_remote,
)


def run(state: StabilizerState) -> StabilizerState:
    """Test if commits apply cleanly via cherry-pick.

    Runs before safe change classification to reduce LLM calls - only
    applicable commits will be sent to the LLM for SRU safety analysis.
    """
    if not state.all_commits:
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
    for commit in state.all_commits:
        # Create minimal ChangeGroup for single commit
        change_group = ChangeGroup(
            commits=[commit],
            title=commit.subject,
        )

        success, output = cherry_pick_dry_run(pkg_path, commit.sha)
        if success:
            applicable.append(
                ApplicableChange(
                    change_group=change_group,
                    applies_cleanly=True,
                    cherry_pick_output=output,
                )
            )
        else:
            state.exclusions.append(
                ExclusionRecord(
                    change_title=commit.subject,
                    stage="applicable",
                    reason=f"Cherry-pick failed: {output[:200]}",
                )
            )

    state.applicable_changes = applicable
    print(
        f"  [dim]→ Found {len(applicable)} applicable changes, "
        f"excluded {len([e for e in state.exclusions if e.stage == 'applicable'])}[/dim]"
    )
    return state
