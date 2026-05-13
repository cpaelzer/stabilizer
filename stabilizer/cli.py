# Copyright 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only

"""Stabilizer CLI entrypoint."""

from __future__ import annotations

import argparse
from pathlib import Path

from stabilizer.orchestrator import run


def main():
    parser = argparse.ArgumentParser(
        description="Stabilizer - Automated SRU candidate identification and preparation"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run Stabilizer analysis")
    run_parser.add_argument("--package", required=True, help="Ubuntu source package name")
    run_parser.add_argument("--target", required=True, help="Target release (e.g., noble)")
    run_parser.add_argument("--source", required=True, help="Source release (e.g., resolute)")
    run_parser.add_argument(
        "--output",
        default="output",
        help="Output directory for generated files (default: output)",
    )

    args = parser.parse_args()

    if args.command == "run":
        run(
            package=args.package,
            target_release=args.target,
            source_release=args.source,
            output_dir=Path(args.output),
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
