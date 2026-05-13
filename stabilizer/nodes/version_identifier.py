# Copyright 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only

"""StabilizerVersionIdentifier - Gets package versions from rmadison."""

from __future__ import annotations

from stabilizer.types import StabilizerState
from stabilizer.utils import get_package_versions


def run(state: StabilizerState) -> StabilizerState:
    """Identify versions in target and source releases using rmadison."""
    releases = [state.target_release, state.source_release]
    versions = get_package_versions(state.package, releases)

    target_ver = versions.get(state.target_release)
    source_ver = versions.get(state.source_release)

    if target_ver is None:
        raise RuntimeError(
            f"Could not find version of {state.package} in {state.target_release}"
        )
    if source_ver is None:
        raise RuntimeError(
            f"Could not find version of {state.package} in {state.source_release}"
        )

    state.target_version = target_ver
    state.source_version = source_ver

    return state
