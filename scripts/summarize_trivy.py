#!/usr/bin/env python3
"""Flatten Trivy filesystem scan JSON into a compact findings list."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def summarize_trivy_report(report: dict[str, Any]) -> list[dict[str, str]]:
    """Convert a Trivy report into a flat list of vulnerability findings."""
    findings: list[dict[str, str]] = []

    for result in report.get("Results", []) or []:
        target = result.get("Target", "")
        for vuln in result.get("Vulnerabilities", []) or []:
            findings.append(
                {
                    "id": vuln.get("VulnerabilityID", ""),
                    "package": vuln.get("PkgName", ""),
                    "installed_version": vuln.get("InstalledVersion", ""),
                    "fixed_version": vuln.get("FixedVersion", ""),
                    "severity": vuln.get("Severity", ""),
                    "title": vuln.get("Title", ""),
                    "target": target,
                }
            )

    return findings


def load_report(input_path: Path | None) -> dict[str, Any]:
    """Load a Trivy JSON report from stdin or a file."""
    if input_path is None:
        return json.load(sys.stdin)

    return json.loads(input_path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Summarize a Trivy filesystem scan into a compact JSON list."
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Read Trivy JSON from a file instead of stdin.",
    )
    args = parser.parse_args(argv)

    try:
        report = load_report(args.input)
    except FileNotFoundError as exc:
        print(f"Trivy report file not found: {exc.filename}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"Failed to parse Trivy JSON: {exc}", file=sys.stderr)
        return 1

    findings = summarize_trivy_report(report)
    json.dump(findings, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
