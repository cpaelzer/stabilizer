# Copyright 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only

"""StabilizerIdentifyTestableChanges - Generates test plans for applicable changes using LLM."""

from __future__ import annotations

import json
import os
from typing import Optional

import httpx

from stabilizer.types import ApplicableChange, ExclusionRecord, StabilizerState, TestableChange

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "testable_changes.txt")

# Stronger model for test plan generation
MODEL = os.environ.get("STABILIZER_TESTABLE_MODEL", "qwen/qwen3.6-plus")


def _build_change_text(change: ApplicableChange) -> str:
    """Format a change for LLM analysis."""
    change_group = change.change_group
    text = f"Title: {change_group.title}\n"
    text += f"Impact: {change_group.impact}\n"
    text += f"Commits:\n"
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


def _call_llm(prompt: str) -> Optional[str]:
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
    except httpx.HTTPStatusError as e:
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
    """Generate test plans for applicable changes."""
    if not state.applicable_changes:
        return state

    prompt = _build_prompt(
        state.applicable_changes,
        state.package,
        state.target_release,
    )
    response = _call_llm(prompt)

    if response is None:
        return state

    testable_changes = _parse_response(response, state.applicable_changes)
    state.testable_changes = testable_changes

    # Record excluded changes
    for i, tc in enumerate(testable_changes):
        if not tc.testable:
            state.exclusions.append(ExclusionRecord(
                change_title=tc.applicable_change.change_group.title,
                stage="testable",
                reason=tc.test_exclusion_reason or "Not testable",
            ))

    return state
