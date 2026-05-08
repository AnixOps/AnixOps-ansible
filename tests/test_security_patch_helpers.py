#!/usr/bin/env python3
"""Tests for the weekly security patch helper scripts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from summarize_trivy import summarize_trivy_report
from upsert_security_patch_issue import (
    render_failure_body,
    render_report_body,
    select_existing_issue,
)


def test_summarize_trivy_report_flattens_vulnerabilities():
    report = {
        "Results": [
            {
                "Target": "/",
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2024-0001",
                        "PkgName": "openssl",
                        "InstalledVersion": "1.1.1",
                        "FixedVersion": "1.1.2",
                        "Severity": "HIGH",
                        "Title": "Example finding",
                    }
                ],
            }
        ]
    }

    findings = summarize_trivy_report(report)

    assert findings == [
        {
            "id": "CVE-2024-0001",
            "package": "openssl",
            "installed_version": "1.1.1",
            "fixed_version": "1.1.2",
            "severity": "HIGH",
            "title": "Example finding",
            "target": "/",
        }
    ]


def test_select_existing_issue_ignores_pull_requests():
    issues = [
        {"title": "AnixOps security patch backlog", "number": 1, "pull_request": {"url": "https://example.invalid"}},
        {"title": "Other", "number": 2},
        {"title": "AnixOps security patch backlog", "number": 3},
    ]

    issue = select_existing_issue(issues, "AnixOps security patch backlog")

    assert issue["number"] == 3


def test_render_report_body_includes_alert_details():
    report = {
        "generated_at": "2026-05-08T04:00:00Z",
        "target_group": "all",
        "total_hosts": 2,
        "clean_count": 1,
        "patched_count": 1,
        "hosts": [
            {
                "host": "server-a",
                "status": "clean",
                "before_count": 0,
                "after_count": 0,
                "reboot_required": False,
                "alert_reason": "no high or critical OS vulnerabilities found",
            },
            {
                "host": "server-b",
                "status": "needs_attention",
                "before_count": 2,
                "after_count": 1,
                "reboot_required": True,
                "alert_reason": "patchable vulnerabilities remain after remediation",
                "findings": [
                    {
                        "id": "CVE-2024-0002",
                        "package": "bash",
                        "installed_version": "5.0",
                        "fixed_version": "5.1",
                        "severity": "CRITICAL",
                    }
                ],
            },
        ],
    }

    body, alert_hosts = render_report_body(report, "https://example.invalid/run/1")

    assert "Security patch report" in body
    assert "| server-b | needs_attention | 2 | 1 | yes | patchable vulnerabilities remain after remediation |" in body
    assert "## Alert details" in body
    assert "CVE-2024-0002" in body
    assert len(alert_hosts) == 1


def test_render_failure_body_mentions_reason():
    body = render_failure_body(
        "report file was not created",
        "all",
        "https://example.invalid/run/1",
        "failure",
        "2026-05-08T04:00:00Z",
    )

    assert "Security patch workflow failed" in body
    assert "report file was not created" in body
    assert "failure" in body
