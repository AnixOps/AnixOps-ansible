#!/usr/bin/env python3
"""Tests for the weekly security patch helper scripts."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import upsert_security_patch_issue as upsert  # noqa: E402
from summarize_trivy import dedupe_findings, severity_rank, summarize_trivy_report  # noqa: E402
from upsert_security_patch_issue import (  # noqa: E402
    ISSUE_MARKER,
    GitHubAPIError,
    TransportError,
    append_step_summary,
    create_issue,
    github_request,
    parse_labels,
    render_failure_body,
    render_report_body,
    select_existing_issue,
    strip_marker,
    upsert_issue,
)


# --------------------------------------------------------------------------- helpers


class FakeTransport:
    """Scripted transport: returns the queued (status, headers, body) tuples in order."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("transport called more often than scripted")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def body(self, index):
        return json.loads(self.requests[index].data.decode("utf-8"))


def _vuln(vuln_id, pkg, installed, fixed="", severity="HIGH", title=""):
    return {
        "VulnerabilityID": vuln_id,
        "PkgName": pkg,
        "InstalledVersion": installed,
        "FixedVersion": fixed,
        "Severity": severity,
        "Title": title,
    }


# ------------------------------------------------------------------ summarize_trivy


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


def test_summarize_trivy_report_dedupes_identical_rows():
    report = {
        "Results": [
            {
                "Target": "ubuntu 22.04",
                "Vulnerabilities": [
                    _vuln("CVE-2024-0001", "libssl3", "3.0.2", "3.0.3", title="first"),
                    _vuln("CVE-2024-0001", "libssl3", "3.0.2", "3.0.3", title="duplicate"),
                    _vuln("CVE-2024-0001", "libssl3", "3.0.1", "3.0.3", title="other version"),
                    _vuln("CVE-2024-0001", "openssl", "3.0.2", "3.0.3", title="other package"),
                ],
            },
            {"Target": "second result", "Vulnerabilities": [_vuln("CVE-2024-0001", "libssl3", "3.0.2", "3.0.3")]},
        ]
    }

    findings = summarize_trivy_report(report)

    keys = [(f["id"], f["package"], f["installed_version"]) for f in findings]
    assert len(keys) == len(set(keys)) == 3
    first = next(f for f in findings if f["package"] == "libssl3" and f["installed_version"] == "3.0.2")
    assert first["title"] == "first"


def test_dedupe_findings_keeps_first_occurrence():
    rows = [
        {"id": "A", "package": "p", "installed_version": "1", "title": "one"},
        {"id": "A", "package": "p", "installed_version": "1", "title": "two"},
        {"id": "B", "package": "p", "installed_version": "1", "title": "three"},
    ]

    assert [row["title"] for row in dedupe_findings(rows)] == ["one", "three"]


def test_summarize_trivy_report_orders_by_severity_then_package():
    report = {
        "Results": [
            {
                "Target": "/",
                "Vulnerabilities": [
                    _vuln("CVE-3", "zlib", "1", severity="LOW"),
                    _vuln("CVE-2", "bash", "1", severity="high"),
                    _vuln("CVE-1", "openssl", "1", severity="CRITICAL"),
                    _vuln("CVE-4", "curl", "1", severity="MEDIUM"),
                    _vuln("CVE-5", "apt", "1", severity="HIGH"),
                    _vuln("CVE-6", "weird", "1", severity="BOGUS"),
                ],
            }
        ]
    }

    findings = summarize_trivy_report(report)

    assert [f["id"] for f in findings] == ["CVE-1", "CVE-5", "CVE-2", "CVE-4", "CVE-3", "CVE-6"]
    assert findings[2]["severity"] == "HIGH"  # normalised to upper case
    assert severity_rank("critical") < severity_rank("HIGH") < severity_rank("unknown") <= severity_rank("")


def test_summarize_trivy_report_tolerates_missing_or_null_sections():
    assert summarize_trivy_report({}) == []
    assert summarize_trivy_report({"Results": None}) == []
    assert summarize_trivy_report({"Results": [{"Target": "x", "Vulnerabilities": None}, "junk"]}) == []
    assert summarize_trivy_report(None) == []  # type: ignore[arg-type]


# -------------------------------------------------------------- issue selection


def test_select_existing_issue_ignores_pull_requests():
    issues = [
        {"title": "AnixOps security patch backlog", "number": 1, "pull_request": {"url": "https://example.invalid"}},
        {"title": "Other", "number": 2},
        {"title": "AnixOps security patch backlog", "number": 3},
    ]

    issue = select_existing_issue(issues, "AnixOps security patch backlog")

    assert issue["number"] == 3


def test_select_existing_issue_prefers_marker_match():
    title = "AnixOps security patch backlog"
    issues = [
        {"title": title, "number": 1, "body": "created by a human, no marker"},
        {"title": "Unrelated", "number": 2, "body": ISSUE_MARKER},
        {"title": title, "number": 5, "body": f"{ISSUE_MARKER}\n# Security patch report"},
    ]

    assert select_existing_issue(issues, title)["number"] == 5
    # Fallback to the exact title when no issue carries the marker (pre-marker issues).
    assert select_existing_issue(issues[:2], title)["number"] == 1
    assert select_existing_issue([], title) is None


def test_parse_labels_splits_and_dedupes():
    assert parse_labels("security, automation,,security ") == ["security", "automation"]
    assert parse_labels("") == []
    assert parse_labels(None) == []


# ------------------------------------------------------------------- rendering


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


def test_render_report_body_includes_marker_mode_and_new_counters():
    report = {
        "schema_version": 1,
        "generated_at": "2026-05-08T04:00:00Z",
        "target_group": "web_servers",
        "apply_updates": False,
        "severity": "CRITICAL",
        "total_hosts": 1,
        "unreachable_count": 1,
        "reboot_required_count": 0,
        "rebooted_count": 0,
        "hosts": [
            {
                "host": "server-c",
                "status": "scan_failed",
                "before_count": 0,
                "after_count": 0,
                "reboot_required": False,
                "alert_reason": "no host summary was produced (unreachable or failed before reporting)",
                "unreachable": True,
                "update_rc": 0,
            }
        ],
    }

    body, alert_hosts = render_report_body(report, "https://example.invalid/run/2")

    assert body.startswith(ISSUE_MARKER)
    assert "- Mode: scan-only (no packages were updated)" in body
    assert "- Severity filter: CRITICAL" in body
    assert "- Unreachable hosts: 1" in body
    assert [host["host"] for host in alert_hosts] == ["server-c"]


def test_render_report_body_escapes_pipes_in_cells():
    report = {"hosts": [{"host": "h", "status": "needs_attention", "alert_reason": "a | b", "update_rc": 100}]}

    body, _ = render_report_body(report, "u")

    assert "| h | needs_attention | 0 | 0 | no | a / b |" in body
    assert "- Package update exit code: 100" in body


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
    assert body.startswith(ISSUE_MARKER)


def test_strip_marker_removes_only_the_marker_line():
    body = f"{ISSUE_MARKER}\n# Title\n\ntext"

    assert strip_marker(body) == "# Title\n\ntext"


# ------------------------------------------------------------ retry behaviour


def test_github_request_retries_server_errors_with_backoff():
    transport = FakeTransport(
        [
            (502, {}, "bad gateway"),
            (503, {}, '{"message": "unavailable"}'),
            (200, {"X-Test": "1"}, '{"ok": true}'),
        ]
    )
    sleeps = []

    payload, headers = github_request(
        "GET", "/repos/o/r/issues", "tok", transport=transport, sleep=sleeps.append, backoff=2.0
    )

    assert payload == {"ok": True}
    assert headers["X-Test"] == "1"
    assert len(transport.requests) == 3
    assert sleeps == [2.0, 4.0]
    assert transport.requests[0].get_header("Authorization") == "Bearer tok"


def test_github_request_honours_retry_after_for_secondary_rate_limits():
    transport = FakeTransport(
        [
            (403, {"Retry-After": "7"}, '{"message": "You have exceeded a secondary rate limit."}'),
            (429, {"retry-after": "3"}, "slow down"),
            (201, {}, '{"number": 12}'),
        ]
    )
    sleeps = []

    payload, _ = github_request("POST", "/repos/o/r/issues", "tok", body={"title": "t"}, transport=transport, sleep=sleeps.append)

    assert payload == {"number": 12}
    assert sleeps == [7.0, 3.0]


def test_github_request_retries_when_rate_limit_remaining_is_zero():
    transport = FakeTransport(
        [
            (403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "0"}, '{"message": "API rate limit exceeded"}'),
            (200, {}, "[]"),
        ]
    )
    sleeps = []

    payload, _ = github_request("GET", "/x", "tok", transport=transport, sleep=sleeps.append)

    assert payload == []
    assert len(sleeps) == 1 and 1.0 <= sleeps[0] <= 60.0


def test_github_request_does_not_retry_client_errors():
    transport = FakeTransport([(404, {}, '{"message": "Not Found"}')])
    sleeps = []

    with pytest.raises(GitHubAPIError) as excinfo:
        github_request("GET", "/repos/o/r/issues", "tok", transport=transport, sleep=sleeps.append)

    assert excinfo.value.status == 404
    assert "Not Found" in str(excinfo.value)
    assert len(transport.requests) == 1
    assert sleeps == []


def test_github_request_gives_up_after_configured_retries():
    transport = FakeTransport([(500, {}, "boom")] * 3)
    sleeps = []

    with pytest.raises(GitHubAPIError) as excinfo:
        github_request("GET", "/x", "tok", transport=transport, sleep=sleeps.append, retries=2)

    assert excinfo.value.status == 500
    assert len(transport.requests) == 3
    assert len(sleeps) == 2


def test_github_request_retries_transport_errors():
    transport = FakeTransport([TransportError("connection reset"), (200, {}, "null")])
    sleeps = []

    payload, _ = github_request("GET", "/x", "tok", transport=transport, sleep=sleeps.append)

    assert payload is None
    assert len(transport.requests) == 2
    assert len(sleeps) == 1


def test_github_request_raises_after_persistent_transport_errors():
    transport = FakeTransport([TransportError("timed out")] * 2)

    with pytest.raises(GitHubAPIError) as excinfo:
        github_request("GET", "/x", "tok", transport=transport, sleep=lambda _: None, retries=1)

    assert excinfo.value.status == 0
    assert "timed out" in str(excinfo.value)


# -------------------------------------------------------------- labels fallback


def test_create_issue_retries_without_labels_on_422(capsys):
    transport = FakeTransport(
        [
            (422, {}, '{"message": "Validation Failed", "errors": [{"field": "labels"}]}'),
            (201, {}, '{"number": 7}'),
        ]
    )

    created = create_issue("o", "r", "tok", "title", "body", ["security", "automation"], transport=transport)

    assert created["number"] == 7
    assert transport.body(0)["labels"] == ["security", "automation"]
    assert "labels" not in transport.body(1)
    assert transport.body(1) == {"title": "title", "body": "body"}
    assert "rejected labels" in capsys.readouterr().err


def test_create_issue_does_not_mask_422_without_labels():
    transport = FakeTransport([(422, {}, '{"message": "Validation Failed"}')])

    with pytest.raises(GitHubAPIError) as excinfo:
        create_issue("o", "r", "tok", "title", "body", [], transport=transport)

    assert excinfo.value.status == 422
    assert len(transport.requests) == 1


def test_upsert_issue_comments_on_existing_issue():
    existing = [{"number": 3, "title": upsert.ISSUE_TITLE, "body": f"{ISSUE_MARKER}\nold"}]
    transport = FakeTransport([(200, {}, json.dumps(existing)), (201, {}, '{"id": 1}')])

    number, action = upsert_issue("o", "r", "tok", upsert.ISSUE_TITLE, "new body", ["security"], transport=transport)

    assert (number, action) == (3, "updated")
    assert transport.requests[1].full_url.endswith("/repos/o/r/issues/3/comments")
    assert transport.body(1) == {"body": "new body"}


def test_upsert_issue_creates_when_none_is_open():
    transport = FakeTransport([(200, {}, "[]"), (201, {}, '{"number": 9}')])

    number, action = upsert_issue("o", "r", "tok", upsert.ISSUE_TITLE, "body", ["security"], transport=transport)

    assert (number, action) == (9, "created")
    assert transport.body(1)["labels"] == ["security"]


# ------------------------------------------------------------- step summary / CLI


def test_append_step_summary_appends_when_env_is_set(tmp_path, monkeypatch):
    summary_file = tmp_path / "summary.md"
    summary_file.write_text("existing\n", encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

    assert append_step_summary("# Report\n| a | b |") is True
    assert summary_file.read_text(encoding="utf-8") == "existing\n# Report\n| a | b |\n\n"


def test_append_step_summary_is_a_noop_without_env(monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    assert append_step_summary("# Report") is False


def test_main_dry_run_renders_report_and_step_summary(tmp_path, monkeypatch, capsys):
    report = {
        "schema_version": 1,
        "generated_at": "2026-05-08T04:00:00Z",
        "target_group": "all",
        "apply_updates": True,
        "total_hosts": 1,
        "hosts": [
            {
                "host": "server-b",
                "status": "needs_attention",
                "before_count": 2,
                "after_count": 1,
                "reboot_required": False,
                "alert_reason": "patchable vulnerabilities remain after remediation",
            }
        ],
    }
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    summary_file = tmp_path / "step-summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    rc = upsert.main(
        [
            "--report-path",
            str(report_path),
            "--repository",
            "owner/repo",
            "--run-url",
            "https://example.invalid/run/3",
            "--dry-run",
        ]
    )

    out = capsys.readouterr().out
    assert rc == upsert.EXIT_OK
    assert "would create/update the backlog issue (1 alert hosts)" in out
    assert "| server-b | needs_attention | 2 | 1 | no |" in out
    written = summary_file.read_text(encoding="utf-8")
    assert "server-b" in written
    assert ISSUE_MARKER not in written


def test_main_dry_run_reports_missing_report_file(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    rc = upsert.main(
        [
            "--report-path",
            str(tmp_path / "missing.json"),
            "--repository",
            "owner/repo",
            "--run-url",
            "https://example.invalid/run/4",
            "--dry-run",
        ]
    )

    assert rc == upsert.EXIT_OK
    assert "report file was not created" in capsys.readouterr().out


def test_main_rejects_missing_configuration(tmp_path, monkeypatch, capsys):
    for name in ("REPORT_PATH", "GITHUB_REPOSITORY", "GITHUB_TOKEN", "RUN_URL"):
        monkeypatch.delenv(name, raising=False)

    assert upsert.main([]) == upsert.EXIT_USAGE
    assert "REPORT_PATH is required" in capsys.readouterr().err

    rc = upsert.main(["--report-path", str(tmp_path / "r.json"), "--repository", "owner/repo", "--run-url", "u"])
    assert rc == upsert.EXIT_USAGE
    assert "GITHUB_TOKEN is required" in capsys.readouterr().err

    rc = upsert.main(["--report-path", str(tmp_path / "r.json"), "--repository", "bad-slug", "--run-url", "u", "--token", "t"])
    assert rc == upsert.EXIT_USAGE
