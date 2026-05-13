# Copyright 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only

"""StabilizerIdentifyCommitRange - Maps versions to upstream git tags/commits."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from stabilizer.types import StabilizerState
from stabilizer.utils import (
    add_remote,
    fetch_remote,
    find_tag_for_version,
    get_commits_between,
    get_git_tags,
)


def clone_upstream_repo(state: StabilizerState) -> Path:
    """Clone the upstream repository and add it as a remote to the Ubuntu packaging repo."""
    if state.repository is None:
        raise RuntimeError("No repository info available")

    pkg_path = state.work_dir / state.package
    upstream_path = state.work_dir / f"{state.package}-upstream"

    # Clone upstream repo separately for tag access
    if upstream_path.exists():
        # Already cloned, just make sure it is up to date
        subprocess.run(
            ["git", "fetch", "--all"],
            capture_output=True,
            text=True,
            cwd=str(upstream_path),
        )
    else:
        subprocess.run(
            ["git", "clone", "--bare", state.repository.url, str(upstream_path)],
            capture_output=True,
            text=True,
            check=True,
        )

    # Add as remote to the packaging repo
    add_remote(pkg_path, "upstream", state.repository.url)
    fetch_remote(pkg_path, "upstream")

    return upstream_path


def find_tag_in_repo(repo_path: Path, version: str, package_name: str) -> Optional[str]:
    """Find a tag matching the version, trying package-specific prefixes."""
    tags = get_git_tags(repo_path)

    # Try exact match first
    tag = find_tag_for_version(tags, version)
    if tag:
        return tag

    # Try package-specific prefixes (e.g., "jq-1.6", "dovecot-2.3.19")
    for prefix in [f"{package_name}-", f"{package_name}_"]:
        tagged = find_tag_for_version(tags, f"{prefix}{version}")
        if tagged:
            return tagged

    # Try fuzzy matching for common patterns
    for tag in tags:
        # Remove common prefixes
        clean = tag
        for p in ["v", "release-", "rel-", f"{package_name}-", f"{package_name}_"]:
            if clean.startswith(p):
                clean = clean[len(p):]
        if clean == version:
            return tag

    return None


def run(state: StabilizerState) -> StabilizerState:
    """Find tags/commits for the target and source versions in the upstream repo."""
    upstream_path = clone_upstream_repo(state)

    if state.target_version is None or state.source_version is None:
        raise RuntimeError("Version information not available")

    target_tag = find_tag_in_repo(
        upstream_path,
        state.target_version.upstream_version,
        state.package,
    )
    source_tag = find_tag_in_repo(
        upstream_path,
        state.source_version.upstream_version,
        state.package,
    )

    if target_tag is None:
        raise RuntimeError(
            f"Could not find tag for {state.package} {state.target_version.upstream_version} "
            f"in upstream repository"
        )
    if source_tag is None:
        raise RuntimeError(
            f"Could not find tag for {state.package} {state.source_version.upstream_version} "
            f"in upstream repository"
        )

    state.target_tag = target_tag
    state.source_tag = source_tag

    # Get all commits between the two tags from the upstream repo
    state.all_commits = get_commits_between(upstream_path, target_tag, source_tag)

    return state
