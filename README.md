# Stabilizer - SRU Automation System

Automated identification and preparation of Stable Release Update (SRU) candidates for Ubuntu packages.
Eliminates manual issue reporting and fix discovery by proactively analyzing upstream changes between Ubuntu releases.

## Overview

Stabilizer automates the following SRU steps:
- Identifying potential commits
- Balancing impact vs. regression risk to justify changes
- Finding ways to test and verify each change
- Preparing SRU paperwork (bug templates)

Input: A Ubuntu source package name, target release, and source release.
Output: SRU bug template files (`.bug`) for each qualified fix.

## Installation

### Prerequisites

1. **git-ubuntu** (snap):
   ```bash
   sudo snap install git-ubuntu --classic
   ```

2. **Ubuntu package dependencies**:
   ```bash
   sudo apt install python3-launchpadlib python3-debian python3-rich python3-git devscripts ubuntu-dev-tools python3-pydantic
   ```

3. **Python 3.12+** (available on Ubuntu 24.04+)

4. **OpenRouter API key** (for LLM-powered analysis):
   ```bash
   export OPENROUTER_API_KEY="your-key-here"
   ```

## Usage

```bash
# Basic usage
python -m stabilizer run --package jq --target noble --source jammy

# With explicit output directory
python -m stabilizer run --package jq --target noble --source jammy --output ./output

# Multiple packages
python -m stabilizer run --package dovecot --target noble --source resolute
```

## Architecture

The system follows a pipeline of specialized nodes orchestrated by a central coordinator:

1. **StabilizerVersionIdentifier** - Gets package versions from rmadison/Launchpad
2. **StabilizerGetRepository** - Detects upstream git repository via debian/watch and debian/control
3. **StabilizerIdentifyCommitRange** - Maps versions to upstream git tags/commits
4. **StabilizerIdentifySafeChanges** - Classifies commits as safe SRU candidates (LLM-powered)
5. **StabilizerIdentifyApplicableFixes** - Tests cherry-pick applicability
6. **StabilizerIdentifyTestableChanges** - Generates test plans (LLM-powered)
7. **StabilizerPreparePaperwork** - Creates SRU bug template files
8. **StabilizerReport** - Final summary report

### Design Decisions

See [DESIGN.md](DESIGN.md) for the complete decision log including framework selection rationale.

## License

GPL-3.0-only - Copyright 2026 Canonical Ltd.
