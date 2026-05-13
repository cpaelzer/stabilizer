# Copyright 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only

"""StabilizerIdentifyTestableChanges - Generates test plans for applicable changes using LLM."""

from __future__ import annotations

import json
import os

import httpx

from stabilizer.types import ApplicableChange, ExclusionRecord, StabilizerState, TestableChange

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "testable_changes.txt")

# Stronger model for test plan generation
MODEL = os.environ.get("STABILIZER_TESTABLE_MODEL", "qwen/qwen3.6-plus")

# Maximum changes to send in a single LLM prompt to avoid context limits
MAX_CHANGES_PER_PROMPT = 50


def _build_change_text(change: ApplicableChange) -> str:
    """Format a change for LLM analysis."""
    change_group = change.change_group
    text = f"Title: {change_group.title}\n"
    text += f"Impact: {change_group.impact}\n"
    text += "Commits:\n"
    for commit in change_group.commits:
        text += f"  - {commit.short_sha}: {commit.subject}\n"
        if commit.body:
            text += f"    {commit.body[:200]}\n"
    return text


def _build_prompt(changes: list, package: str, target_release: str) -> str:
    """Build the prompt for test plan generation."""
    with open(PROMPT_PATH) as f:
        template = f.read()

    changes_text = "\n---\n".join(_build_change_text(c) for c in changes)

    return template.format(
        package=package,
        release=target_release,
        changes_text=changes_text,
    )


def _call_llm(prompt: str) -> str | None:
    """Call OpenRouter API for test plan generation."""
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


def _parse_response(response: str, changes: list) -> list[TestableChange]:
    """Parse LLM response into TestableChange objects."""
    try:
        start = response.find("[")
        end = response.rfind("]") + 1
        if start == -1 or end == 0:
            return []

        json_str = response[start:end]
        items = json.loads(json_str)

        result = []
        for i, item in enumerate(items):
            if i >= len(changes):
                break

            applicable = changes[i]
            testable = item.get("testable", True)
            test_desc = item.get("test_description", "")
            expected_without = item.get("expected_without_fix", "")
            expected_with = item.get("expected_with_fix", "")

            tc = TestableChange(
                applicable_change=applicable,
                test_description=test_desc,
                expected_without_fix=expected_without,
                expected_with_fix=expected_with,
                testable=testable,
                test_exclusion_reason=item.get("exclusion_reason", "") if not testable else "",
            )
            result.append(tc)

        return result
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def run(state: StabilizerState) -> StabilizerState:
    """Generate test plans for safe AND applicable changes.

    Only changes that both cherry-pick cleanly AND were classified as safe
    SRU candidates by the LLM will have test plans generated. This avoids
    wasting LLM tokens on changes that are not safe for SRU.
    """
    if not state.applicable_changes or not state.safe_changes:
        # If we have no safe changes, nothing to test
        state.testable_changes = []
        return state

    # Create lookup of safe change groups by title or commit SHAs
    safe_titles = {g.title for g in state.safe_changes}
    safe_shas = {c.sha for g in state.safe_changes for c in g.commits}

    # Filter applicable changes to only those that are also safe
    safe_applicable = []
    for ac in state.applicable_changes:
        cg = ac.change_group
        if (cg.title in safe_titles or
            any(c.sha in safe_shas for c in cg.commits)):
            safe_applicable.append(ac)

    total_to_test = len(safe_applicable)
    print(
        f"  [dim]Generating test plans for {total_to_test} safe+applicable changes...[/dim]"
    )

    # Batch if too many changes to avoid context length errors
    if total_to_test > MAX_CHANGES_PER_PROMPT:
        print(f"  [dim]→ Large set ({total_to_test} changes), processing in batches of {MAX_CHANGES_PER_PROMPT}[/dim]")
        testable_changes = _generate_test_plans_in_batches(safe_applicable, state.package, state.target_release)
    else:
        prompt = _build_prompt(
            safe_applicable,
            state.package,
            state.target_release,
        )
        response = _call_llm(prompt)
        testable_changes = _parse_response(response, safe_applicable) if response else []

    state.testable_changes = testable_changes

    # Record excluded changes
    excluded_testable = 0
    for tc in testable_changes:
        if not tc.testable:
            state.exclusions.append(
                ExclusionRecord(
                    change_title=tc.applicable_change.change_group.title,
                    stage="testable",
                    reason=tc.test_exclusion_reason or "Not testable",
                )
            )
            excluded_testable += 1

    print(
        f"  [dim]→ Found {len([tc for tc in testable_changes if tc.testable])} testable changes, excluded {excluded_testable}[/dim]"
    )
    return state


def _generate_test_plans_in_batches(
    changes: list[ApplicableChange], package: str, target_release: str
) -> list[TestableChange]:
    """Split large sets of changes into batches for test plan generation."""
    all_testable = []
    batch_size = MAX_CHANGES_PER_PROMPT

    for i in range(0, len(changes), batch_size):
        batch = changes[i : i + batch_size]
        print(f"  [dim]  Processing test plan batch {i//batch_size + 1} ({len(batch)} changes)[/dim]")

        prompt = _build_prompt(batch, package, target_release)
        response = _call_llm(prompt)

        if response:
            batch_testable = _parse_response(response, batch)
            all_testable.extend(batch_testable)

    return all_testable

