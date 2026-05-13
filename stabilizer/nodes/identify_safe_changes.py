# Copyright 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only

"""StabilizerIdentifySafeChanges - Classifies commits as safe SRU candidates using LLM."""

from __future__ import annotations

import json
import os

import httpx

from stabilizer.types import ApplicableChange, ChangeGroup, CommitInfo, ExclusionRecord, StabilizerState

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "safe_changes.txt")

# Model for classification - cheaper model sufficient for this task
MODEL = os.environ.get("STABILIZER_SAFE_CHANGES_MODEL", "qwen/qwen3.6-plus")

# Maximum commits to send in a single LLM prompt to avoid context limits
MAX_COMMITS_PER_PROMPT = 80


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


def _call_llm(prompt: str) -> str | None:
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
    except httpx.HTTPStatusError:
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
    """Identify safe SRU changes from applicable commits only.

    This runs after applicability testing to reduce LLM token usage -
    only changes that cherry-pick cleanly are evaluated for SRU safety.
    """
    # Extract commits from applicable_commits (set by previous applicability step)
    if hasattr(state, 'applicable_commits') and state.applicable_commits:
        commits_to_classify = state.applicable_commits
    else:
        commits_to_classify = state.all_commits

    if not commits_to_classify:
        return state

    total_commits = len(commits_to_classify)
    print(f"  Evaluating {total_commits} applicable commits for SRU safety...")

    # Batch if too many commits to avoid context length errors
    if total_commits > MAX_COMMITS_PER_PROMPT:
        print(f"  → Large set ({total_commits} commits), processing in batches of {MAX_COMMITS_PER_PROMPT}")
        safe_changes = _classify_in_batches(commits_to_classify, state.package)
    else:
        prompt = _build_prompt(commits_to_classify, state.package)
        response = _call_llm(prompt)
        safe_changes = _parse_response(response, commits_to_classify) if response else []

    # Convert safe ChangeGroups into ApplicableChange objects
    applicable = []
    safe_shas = {c.sha for g in safe_changes for c in g.commits}
    excluded_count = 0

    for commit in commits_to_classify:
        if commit.sha in safe_shas:
            # Find the corresponding safe group
            for group in safe_changes:
                if any(c.sha == commit.sha for c in group.commits):
                    applicable.append(
                        ApplicableChange(
                            change_group=group,
                            applies_cleanly=True,
                            cherry_pick_output="Previously validated as applicable",
                        )
                    )
                    break
        else:
            state.exclusions.append(
                ExclusionRecord(
                    change_title=commit.subject,
                    stage="safe_changes",
                    reason="Not classified as safe SRU change by LLM analysis",
                )
            )
            excluded_count += 1

    state.safe_changes = safe_changes
    # Create proper ApplicableChange objects with LLM metadata for downstream nodes
    applicable = []
    for group in safe_changes:
        applicable.append(
            ApplicableChange(
                change_group=group,
                applies_cleanly=True,
                cherry_pick_output="Validated as applicable before LLM classification",
            )
        )
    state.applicable_changes = applicable

    print(
        f"  → Found {len(safe_changes)} safe changes, excluded {excluded_count} commits"
    )

    return state


def _classify_in_batches(commits: list[CommitInfo], package: str) -> list[ChangeGroup]:
    """Split large commit sets into batches to avoid context limits."""
    all_safe = []
    batch_size = MAX_COMMITS_PER_PROMPT

    for i in range(0, len(commits), batch_size):
        batch = commits[i : i + batch_size]
        print(f"    Processing batch {i//batch_size + 1} ({len(batch)} commits)")

        prompt = _build_prompt(batch, package)
        response = _call_llm(prompt)

        if response:
            batch_safe = _parse_response(response, batch)
            all_safe.extend(batch_safe)

    return all_safe
