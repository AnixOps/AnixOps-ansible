#!/usr/bin/env python3
"""Flatten Trivy filesystem scan JSON into a compact findings list.

Reads a Trivy JSON report (``trivy fs --format json``) from stdin or ``--input``
and prints a JSON list of findings, one object per vulnerability, with the keys
``id``, ``package``, ``installed_version``, ``fixed_version``, ``severity``,
``title`` and ``target``.

Rows that share the same ``(id, package, installed_version)`` are reported once
(the first occurrence wins), and the list is ordered by severity (CRITICAL first),
then package name, then vulnerability id, so the report embeds the most important
findings first.

Exit codes: 0 success, 1 the input could not be read or parsed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Lower rank sorts first.
SEVERITY_ORDER: dict[str, int] = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
    "UNKNOWN": 4,
}

Finding = dict[str, str]


def severity_rank(severity: str) -> int:
    """Return the sort rank of a Trivy severity string (unknown values sort last)."""
    return SEVERITY_ORDER.get((severity or "").upper(), len(SEVERITY_ORDER))


def finding_sort_key(finding: Finding) -> tuple[int, str, str]:
    """Sort key: severity rank, then package, then vulnerability id."""
    return (
        severity_rank(finding.get("severity", "")),
        finding.get("package", ""),
        finding.get("id", ""),
    )


def dedupe_findings(findings: list[Finding]) -> list[Finding]:
    """Drop rows with an identical (id, package, installed_version), keeping the first."""
    seen: set[tuple[str, str, str]] = set()
    unique: list[Finding] = []
    for finding in findings:
        key = (finding.get("id", ""), finding.get("package", ""), finding.get("installed_version", ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


def summarize_trivy_report(report: dict[str, Any]) -> list[Finding]:
    """Convert a Trivy report into a flat, deduplicated, severity-ordered findings list."""
    findings: list[Finding] = []

    if not isinstance(report, dict):
        return findings

    for result in report.get("Results", []) or []:
        if not isinstance(result, dict):
            continue
        target = result.get("Target", "") or ""
        for vuln in result.get("Vulnerabilities", []) or []:
            if not isinstance(vuln, dict):
                continue
            findings.append(
                {
                    "id": vuln.get("VulnerabilityID", "") or "",
                    "package": vuln.get("PkgName", "") or "",
                    "installed_version": vuln.get("InstalledVersion", "") or "",
                    "fixed_version": vuln.get("FixedVersion", "") or "",
                    "severity": (vuln.get("Severity", "") or "").upper(),
                    "title": vuln.get("Title", "") or "",
                    "target": target,
                }
            )

    # sorted() is stable, so the first occurrence kept by dedupe stays first.
    return sorted(dedupe_findings(findings), key=finding_sort_key)


def load_report(input_path: Path | None) -> dict[str, Any]:
    """Load a Trivy JSON report from stdin or a file."""
    if input_path is None:
        raw = sys.stdin.read()
    else:
        raw = input_path.read_text(encoding="utf-8")

    if not raw.strip():
        raise json.JSONDecodeError("empty input", raw, 0)

    return json.loads(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Summarize a Trivy filesystem scan into a compact JSON list."
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Read Trivy JSON from a file instead of stdin.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Indent the JSON output (for humans; the playbook uses the compact form).",
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
    json.dump(findings, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
