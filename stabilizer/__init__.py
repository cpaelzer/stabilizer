# Copyright 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only

"""Stabilizer - SRU candidate identification and paperwork generation system.

This project implements an agentic system that proactively identifies safe,
applicable, and testable upstream changes that can be backported as Stable
Release Updates (SRUs) to older Ubuntu releases without requiring bug reports
or manual fix discovery.

The system follows the specified roles:
- StabilizerVersionIdentifier
- StabilizerGetRepository (with LLM assistance to resolve watch/control hints)
- StabilizerIdentifyCommitRange
- StabilizerIdentifySafeChanges (LLM-powered SRU principles assessment)
- StabilizerIdentifyApplicableFixes
- StabilizerIdentifyTestableChanges (LLM-powered test plan generation)
- StabilizerPreparePaperwork (generates SRU bug template files)
- StabilizerReport (rich console report with exclusions)

All source files include the required copyright header and SPDX license.
The architecture uses a simple custom Python orchestrator with rich console
output for visibility rather than heavy frameworks like LangGraph. This was
chosen to keep the project maintainable by Ubuntu developers while still
providing excellent debugging and state visibility.

See README.md for usage instructions and DESIGN.md for the complete decision
log including: model selection, orchestration choice, dependency strategy,
output format, and testing priorities.

All new Python files carry: "Copyright 2026 Canonical Ltd." and
"SPDX-License-Identifier: GPL-3.0-only"
"""
