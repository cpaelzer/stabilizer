# Copyright 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only

"""StabilizerGetRepository - Detects upstream git repository from packaging."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import httpx

from stabilizer.types import RepositoryInfo, StabilizerState
from stabilizer.utils import (
    clone_package,
    parse_debian_control,
)

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "get_repository.txt")

MODEL = os.environ.get("STABILIZER_REPO_MODEL", "qwen/qwen3.6-plus")


def collect_hints(debian_path: Path) -> list[tuple[str, str]]:
    """Collect all hints from debian/watch and debian/control."""
    hints = []

    # debian/watch content
    watch_path = debian_path / "watch"
    if watch_path.exists():
        with open(watch_path) as f:
            hints.append(("debian/watch", f.read()))

    # debian/control fields
    control_fields = parse_debian_control(debian_path / "control")
    for key in ("Homepage", "Vcs-Git", "Vcs-Browser"):
        if key in control_fields:
            hints.append((f"debian/control:{key}", control_fields[key]))

    return hints


def _build_prompt(hints: list[tuple[str, str]], package: str) -> str:
    """Build the prompt for repository identification."""
    with open(PROMPT_PATH) as f:
        template = f.read()

    hints_text = "\n".join(f"### {source}\n{content}" for source, content in hints)

    return template.format(package=package, hints_text=hints_text)


def _call_llm(prompt: str) -> str | None:
    """Call OpenRouter API for repository identification."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY environment variable not set")

    response = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/canonical/stabilizer",
            "X-Title": "Stabilizer SRU Tool",
        },
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 500,
        },
        timeout=60,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        print(f"OpenRouter API error {response.status_code}: {response.text}")
        raise
    data = response.json()
    return data["choices"][0]["message"]["content"]


def _parse_response(response: str) -> RepositoryInfo | None:
    """Parse LLM response into RepositoryInfo."""
    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start == -1 or end == 0:
            return None

        json_str = response[start:end]
        item = json.loads(json_str)

        url = item.get("url", "")
        if not url:
            return None

        # Normalize GitHub URLs
        gh_match = re.match(r"https?://github\.com/([^/]+)/([^/]+)", url)
        if gh_match:
            owner, repo_name = gh_match.groups()
            url = f"https://github.com/{owner}/{repo_name}"

        # Normalize GitLab URLs
        gl_match = re.match(r"https?://gitlab\.com/([^/]+)/([^/]+)", url)
        if gl_match:
            owner, repo_name = gl_match.groups()
            url = f"https://gitlab.com/{owner}/{repo_name}"

        return RepositoryInfo(
            url=url,
            source="LLM analysis of debian/watch and debian/control",
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def run(state: StabilizerState) -> StabilizerState:
    """Detect the upstream git repository from the Ubuntu packaging."""
    # Use the work_dir from orchestrator (temporary directory) if available
    if not state.work_dir:
        work_dir = Path("/tmp/stabilizer-work")
        work_dir.mkdir(parents=True, exist_ok=True)
        state.work_dir = work_dir

    # Clone the Ubuntu package (with better error handling)
    try:
        pkg_path = clone_package(state.package, state.work_dir)
    except Exception as e:
        raise RuntimeError(f"Failed to clone package {state.package}: {e}") from e
    debian_path = pkg_path / "debian"

    # Collect hints from packaging
    hints = collect_hints(debian_path)
    if not hints:
        raise RuntimeError(
            f"Could not find any hints in debian/watch or debian/control for {state.package}."
        )

    print(f"  → Collected {len(hints)} packaging hints (watch/control)")

    # Use LLM to identify upstream repository
    prompt = _build_prompt(hints, state.package)
    response = _call_llm(prompt)

    if response is None:
        raise RuntimeError(
            f"Could not identify upstream repository for {state.package} from packaging hints."
        )

    repo_info = _parse_response(response)
    if repo_info is None:
        raise RuntimeError(
            f"Could not parse upstream repository URL for {state.package} from LLM response."
        )

    print(f"  → LLM identified upstream: {repo_info.url}")

    state.repository = repo_info
    return state
