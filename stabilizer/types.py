# Copyright 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only

"""Pydantic models for Stabilizer state and data structures."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field


class VersionInfo(BaseModel):
    """Information about a package version in a specific Ubuntu release."""

    release: str  # e.g. "jammy", "noble"
    version: str  # e.g. "1.6-2.1ubuntu3.2"
    upstream_version: str  # e.g. "1.6" (part before the last dash)

    @classmethod
    def from_version_string(cls, release: str, version: str) -> VersionInfo:
        """Parse a Debian version string to extract upstream version.

        Handles epochs (1:), dfsg repacks (+dfsg*), and other common patterns.
        """
        # Strip epoch (e.g. "1:2.3.21+dfsg1-..." -> "2.3.21+dfsg1-...")
        if ":" in version:
            version = version.split(":", 1)[1]

        # Remove +dfsgN suffixes (common for repackaged upstream tarballs)
        version = re.sub(r"\+dfsg\d*", "", version)

        # Get upstream part before debian revision
        parts = version.rsplit("-", 1)
        upstream = parts[0] if len(parts) > 1 else version

        # Clean any remaining + suffixes
        upstream = upstream.split("+")[0]

        return cls(release=release, version=version, upstream_version=upstream)


class RepositoryInfo(BaseModel):
    """Information about the upstream git repository."""

    url: str
    source: str  # "debian/watch", "debian/control:Homepage", "debian/control:Vcs-Git"
    detected_tags: list[str] = Field(default_factory=list)


class CommitInfo(BaseModel):
    """Information about a single git commit."""

    sha: str
    short_sha: str
    subject: str
    body: str = ""
    author: str = ""
    date: str = ""
    diff_stat: str = ""


class ChangeGroup(BaseModel):
    """A single change or group of related commits that may qualify for SRU."""

    commits: list[CommitInfo]
    title: str
    impact: str = ""  # Why this change is needed
    regression_risk: str = ""  # Why it is safe to apply
    excluded: bool = False
    exclusion_reason: str = ""


class ApplicableChange(BaseModel):
    """A change that applies cleanly via cherry-pick."""

    change_group: ChangeGroup
    applies_cleanly: bool = True
    cherry_pick_output: str = ""


class TestableChange(BaseModel):
    """A change that can be tested with a concrete test plan."""

    applicable_change: ApplicableChange
    test_description: str = ""
    expected_without_fix: str = ""
    expected_with_fix: str = ""
    testable: bool = True
    test_exclusion_reason: str = ""


class SRUBug(BaseModel):
    """A prepared SRU bug template."""

    title: str
    filename: str
    impact: str
    test_plan: str
    regression_potential: str
    other_info: str = ""
    commits: list[CommitInfo] = Field(default_factory=list)


class ExclusionRecord(BaseModel):
    """Record of why a change was excluded."""

    change_title: str
    stage: str  # "safe_changes", "applicable", "testable", "paperwork"
    reason: str


class StabilizerState(BaseModel):
    """Complete state for a Stabilizer run."""

    # Input parameters
    package: str
    target_release: str
    source_release: str

    # Phase outputs
    target_version: VersionInfo | None = None
    source_version: VersionInfo | None = None
    repository: RepositoryInfo | None = None
    target_tag: str | None = None
    source_tag: str | None = None
    all_commits: list[CommitInfo] = Field(default_factory=list)
    safe_changes: list[ChangeGroup] = Field(default_factory=list)
    applicable_changes: list[ApplicableChange] = Field(default_factory=list)
    testable_changes: list[TestableChange] = Field(default_factory=list)
    sru_bugs: list[SRUBug] = Field(default_factory=list)

    # Tracking
    exclusions: list[ExclusionRecord] = Field(default_factory=list)
    output_dir: Path = Path("output")
    work_dir: Path | None = None  # git-ubuntu clone directory

    # Progress
    current_phase: str = "initializing"
    phase_progress: str = ""
