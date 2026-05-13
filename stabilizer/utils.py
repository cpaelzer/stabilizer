# Copyright 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only

"""Deterministic utility functions for Stabilizer."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from stabilizer.types import CommitInfo, VersionInfo


def run_cmd(
    cmd: list[str], cwd: str | None = None, check: bool = True
) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, check=check)


def parse_rmadison_output(output: str, release: str) -> VersionInfo | None:
    """Parse rmadison output to extract the latest version for a release.

    rmadison output format:
    package | version | suite | source, arch1, arch2, ...
    """
    versions = []
    for line in output.strip().split("\n"):
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue
        _, ver, suite = parts[0], parts[1], parts[2]
        if suite == release or suite.startswith(f"{release}-"):
            versions.append(VersionInfo.from_version_string(release, ver))

    if not versions:
        return None

    return versions[-1]


def get_package_versions(package: str, releases: list[str]) -> dict[str, VersionInfo | None]:
    """Get package versions for multiple releases using rmadison."""
    result = {}
    try:
        proc = run_cmd(["rmadison", "-u", "ubuntu", package] + releases)
        output = proc.stdout
        for release in releases:
            result[release] = parse_rmadison_output(output, release)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"rmadison failed: {e.stderr}") from e
    return result


def clone_package(package: str, work_dir: Path) -> Path:
    """Clone an Ubuntu package using git-ubuntu."""
    target = work_dir / package
    if target.exists():
        return target

    print(f"  → Cloning Ubuntu package {package}...")

    # git-ubuntu clone creates the target directory itself
    # but requires the parent directory to exist AND be the cwd
    work_dir.mkdir(parents=True, exist_ok=True)

    # Ensure we are actually in the directory before running git-ubuntu
    # (git-ubuntu snap calls os.getcwd() during arg parsing)
    old_cwd = os.getcwd()
    try:
        os.chdir(str(work_dir))
        # Run without check=True to capture error output
        proc = run_cmd(["git-ubuntu", "clone", package], cwd=str(work_dir), check=False)
        if proc.returncode != 0:
            error_msg = proc.stderr.strip() or proc.stdout.strip() or "Unknown error"
            raise RuntimeError(f"git-ubuntu clone failed for {package}: {error_msg}")
    finally:
        os.chdir(old_cwd)

    if not target.exists():
        raise RuntimeError(f"git-ubuntu clone did not create expected directory for {package}")

    print(f"  → Successfully cloned {package}")
    return target


def parse_debian_watch(watch_path: Path) -> str | None:
    """Extract upstream URL from debian/watch file.

    Handles both direct URLs and GitHub/GitLab templates.
    """
    if not watch_path.exists():
        return None

    with open(watch_path) as f:
        content = f.read()

    # Check for GitHub template format
    # e.g. "Template: GitHub", "Owner: jqlang", "Project: jq"
    if "Template: GitHub" in content or "Template:Github" in content:
        owner_match = re.search(r"Owner:\s*(\S+)", content)
        project_match = re.search(r"Project:\s*(\S+)", content)
        if owner_match and project_match:
            return f"https://github.com/{owner_match.group(1)}/{project_match.group(1)}"

    # Check for GitLab template format
    if "Template: GitLab" in content:
        host_match = re.search(r"Host:\s*(\S+)", content)
        owner_match = re.search(r"Owner:\s*(\S+)", content)
        project_match = re.search(r"Project:\s*(\S+)", content)
        if owner_match and project_match:
            host = host_match.group(1) if host_match else "gitlab.com"
            return f"https://{host}/{owner_match.group(1)}/{project_match.group(1)}"

    # Try to extract URLs from Download-Url-Mangle or other patterns
    url_patterns = [
        r"https?://github\.com/([^/]+)/([^/@\s]+)",
        r"https?://gitlab\.com/([^/]+)/([^/@\s]+)",
        r"https?://[^/\s]+\.[^/\s]+/([^/\s]+)/([^/\s@]+)",
    ]

    for pattern in url_patterns:
        match = re.search(pattern, content)
        if match:
            groups = match.groups()
            if len(groups) >= 2:
                base = match.group(0).split("@")[0].rstrip("/")
                # Clean up trailing path components that aren't part of repo URL
                parts = base.split("/")
                # For github/gitlab, repo URL is owner/repo
                if "github.com" in base or "gitlab.com" in base:
                    return f"{parts[0]}//{parts[2]}/{parts[3]}"
                return base

    return None


def parse_debian_control(control_path: Path) -> dict[str, str]:
    """Extract relevant fields from debian/control file."""
    fields = {}
    if not control_path.exists():
        return fields

    with open(control_path) as f:
        content = f.read()

    source_stanza = content.split("\n\n")[0]

    for line in source_stanza.split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key in ("Homepage", "Vcs-Git", "Vcs-Browser"):
                fields[key] = value

    return fields


def get_git_tags(repo_path: Path) -> list[str]:
    """Get all git tags in a repository."""
    proc = run_cmd(["git", "tag", "-l"], cwd=str(repo_path))
    return [t.strip() for t in proc.stdout.split("\n") if t.strip()]


def find_tag_for_version(tags: list[str], version: str, package_name: str | None = None) -> str | None:
    """Find a git tag that matches an upstream version with high tolerance.

    Handles package-specific naming (jq-1.6), version prefixes (v1.6, release-1.6),
    release candidates, epochs, and other common patterns.
    """
    if not version or not tags:
        return None

    # Clean version for matching (remove any rc/beta suffixes, epochs, +dfsg, etc.)
    clean_version = re.sub(r"[-+].*$", "", version).strip()
    clean_version = re.sub(r"(rc|beta|alpha|pre|dev)\d*", "", clean_version).strip()

    # Priority order for tag matching
    candidates = []

    # 1. Package-specific tags first (most accurate for many projects)
    if package_name:
        for prefix in [f"{package_name}-", f"{package_name}_"]:
            candidates.append(f"{prefix}{clean_version}")
            candidates.append(f"{prefix}{version}")
            # Also try with rc suffixes if present in original
            if "rc" in version.lower():
                candidates.append(f"{prefix}{version.lower()}")
                candidates.append(f"{prefix}{version}")

    # 2. Common version tag patterns
    for v in [clean_version, version]:
        for prefix in ["v", "V", "release-", "rel-", ""]:
            candidates.append(f"{prefix}{v}")
            if "." in v:
                candidates.append(f"{prefix}{v.replace('.', '_')}")
                candidates.append(f"v{v.replace('.', '_')}")

        # Handle release candidates explicitly
        if "rc" in version.lower():
            rc_match = re.search(r'(rc|beta|alpha)\d*', version, re.IGNORECASE)
            if rc_match:
                rc_part = rc_match.group(0)
                candidates.append(f"{v}{rc_part.lower()}")
                candidates.append(f"v{v}{rc_part.lower()}")

    # 3. Check exact matches first
    for candidate in candidates:
        if candidate in tags:
            return candidate

    # 4. Fuzzy matching as fallback - prefer tags that contain the version
    for tag in tags:
        tag_clean = re.sub(r"[-+](rc|beta|alpha|dfsg|ubuntu|debian).*", "", tag, flags=re.IGNORECASE).strip()
        if tag_clean == clean_version or tag_clean.endswith(clean_version):
            return tag
        if clean_version in tag_clean and len(tag_clean) < len(clean_version) + 10:  # Reasonable closeness
            return tag

    # 5. Last resort: substring match
    for tag in tags:
        if clean_version in tag or version in tag:
            return tag

    return None


def get_commits_between(repo_path: Path, from_ref: str, to_ref: str) -> list[CommitInfo]:
    """Get all commits between two git refs with full details."""
    commits = []

    proc = run_cmd(
        ["git", "log", "--format=%H", "--no-merges", f"{from_ref}..{to_ref}"], cwd=str(repo_path)
    )

    shas = [s.strip() for s in proc.stdout.strip().split("\n") if s.strip()]

    for sha in shas:
        proc = run_cmd(
            ["git", "log", "-1", "--format=%H%n%h%n%s%n%b%n%an%n%ai", sha], cwd=str(repo_path)
        )

        lines = proc.stdout.strip().split("\n")
        if len(lines) < 6:
            continue

        commits.append(
            CommitInfo(
                sha=lines[0],
                short_sha=lines[1],
                subject=lines[2],
                body="\n".join(lines[3:-2]),
                author=lines[-2],
                date=lines[-1],
            )
        )

    return commits


def get_diff_stat(repo_path: Path, sha: str) -> str:
    """Get the diff stat for a commit."""
    proc = run_cmd(["git", "diff", "--stat", f"{sha}^", sha], cwd=str(repo_path))
    return proc.stdout.strip()


def cherry_pick_dry_run(repo_path: Path, sha: str) -> tuple[bool, str]:
    """Test if a commit can be cherry-picked cleanly.

    Returns (success, output).
    """
    proc = run_cmd(["git", "rev-parse", "HEAD"], cwd=str(repo_path))
    original_head = proc.stdout.strip()

    try:
        proc = run_cmd(["git", "cherry-pick", "--no-commit", sha], cwd=str(repo_path))
        success = proc.returncode == 0
        output = proc.stdout + proc.stderr

        run_cmd(["git", "reset", "--hard", original_head], cwd=str(repo_path))
        run_cmd(["git", "clean", "-fd"], cwd=str(repo_path))

        return success, output
    except subprocess.CalledProcessError as e:
        run_cmd(["git", "reset", "--hard", original_head], cwd=str(repo_path))
        run_cmd(["git", "clean", "-fd"], cwd=str(repo_path))
        return False, e.stdout + e.stderr


def checkout_branch(repo_path: Path, branch: str) -> None:
    """Checkout a specific branch."""
    run_cmd(["git", "checkout", branch], cwd=str(repo_path))


def add_remote(repo_path: Path, name: str, url: str) -> None:
    """Add a git remote."""
    try:
        run_cmd(["git", "remote", "add", name, url], cwd=str(repo_path))
    except subprocess.CalledProcessError:
        pass


def fetch_remote(repo_path: Path, remote: str) -> None:
    """Fetch from a remote."""
    run_cmd(["git", "fetch", remote], cwd=str(repo_path))
