# Copyright 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only

"""StabilizerIdentifySafeChanges - Classifies commits as safe SRU candidates using LLM."""

from __future__ import annotations

import json
import os
from typing import Optional

import httpx

from stabilizer.types import ChangeGroup, CommitInfo, ExclusionRecord, StabilizerState

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "safe_changes.txt")

# Model for classification - cheaper model sufficient for this task
MODEL = os.environ.get("STABILIZER_SAFE_CHANGES_MODEL", "qwen/qwen3.6-plus")


def _build_commit_text(commit: CommitInfo) -> str:
    """Format a commit for LLM analysis."""
    text = f"Commit: {commit.short_sha}\n"
    text += f"Subject: {commit.subject}\n"
    text += f"Author: {commit.author}\n"
    text += f"Date: {commit.date}\n"
    if commit.body:
        text += f"Body:\n{commit.body}\n"
    return text


def _build_prompt(commits: list[CommitInfo], package: str) -> str:
    """Build the prompt for safe change classification."""
    with open(PROMPT_PATH) as f:
        template = f.read()

    commits_text = "\n---\n".join(_build_commit_text(c) for c in commits)

    return template.format(package=package, commits_text=commits_text)


def _call_llm(prompt: str) -> Optional[str]:
    """Call OpenRouter API for classification."""
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
            "max_tokens": 4000,
        },
        timeout=120,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(f"OpenRouter API error {response.status_code}: {response.text}")
        raise
    data = response.json()
    return data["choices"][0]["message"]["content"]


def _parse_response(response: str, commits: list[CommitInfo]) -> list[ChangeGroup]:
    """Parse LLM response into ChangeGroup objects."""
    try:
        # Try to find JSON in the response
        start = response.find("[")
        end = response.rfind("]") + 1
        if start == -1 or end == 0:
            return []

        json_str = response[start:end]
        items = json.loads(json_str)

        # Build a map of sha -> commit
        sha_map = {c.short_sha: c for c in commits}
        sha_map.update({c.sha: c for c in commits})

        groups = []
        for item in items:
            shas = item.get("commits", [])
            if not shas:
                continue

            commit_list = []
            for sha in shas:
                if sha in sha_map:
                    commit_list.append(sha_map[sha])

            if not commit_list:
                continue

            group = ChangeGroup(
                commits=commit_list,
                title=item.get("title", ""),
                impact=item.get("impact", ""),
                regression_risk=item.get("regression_risk", ""),
            )
            groups.append(group)

        return groups
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def run(state: StabilizerState) -> StabilizerState:
    """Identify safe SRU changes from the commit range."""
    if not state.all_commits:
        return state

    # Report progress during LLM classification
    print(f"  [dim]Evaluating {len(state.all_commits)} commits for SRU safety...[/dim]")

    prompt = _build_prompt(state.all_commits, state.package)
    response = _call_llm(prompt)

    if response is None:
        return state

    safe_changes = _parse_response(response, state.all_commits)
    state.safe_changes = safe_changes

    # Record excluded commits
    safe_shas = {c.sha for g in safe_changes for c in g.commits}
    excluded_count = 0
    for commit in state.all_commits:
        if commit.sha not in safe_shas:
            state.exclusions.append(ExclusionRecord(
                change_title=commit.subject,
                stage="safe_changes",
                reason="Not classified as safe SRU change by LLM analysis",
            ))
            excluded_count += 1

    print(f"  [dim]→ Found {len(safe_changes)} safe changes, excluded {excluded_count} commits[/dim]")

    return state
