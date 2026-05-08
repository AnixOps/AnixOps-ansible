#!/usr/bin/env python3
"""Upsert the weekly security patch GitHub issue from a report file."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API_BASE = "https://api.github.com"
API_VERSION = "2022-11-28"
ISSUE_TITLE = "AnixOps security patch backlog"


def utc_now() -> str:
    """Return a compact UTC timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_report(report_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Load the report or return a failure reason."""
    if not report_path.exists():
        return None, f"report file was not created at {report_path}"

    try:
        return json.loads(report_path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return None, f"report file could not be parsed: {exc}"


def github_request(
    method: str,
    path: str,
    token: str,
    *,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> tuple[Any, urllib.response.addinfourl]:
    """Perform a GitHub REST request and return parsed JSON with headers."""
    url = f"{API_BASE}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "anixops-security-patch",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
            return (json.loads(payload) if payload else None, response.headers)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API request failed: {method} {path} -> {exc.code} {exc.reason}: {detail}"
        ) from exc


def select_existing_issue(issues: list[dict[str, Any]], title: str) -> dict[str, Any] | None:
    """Pick the first open issue with an exact title match."""
    return next(
        (issue for issue in issues if issue.get("title") == title and "pull_request" not in issue),
        None,
    )


def list_open_issues(owner: str, repo: str, token: str) -> list[dict[str, Any]]:
    """List open issues with pagination."""
    issues: list[dict[str, Any]] = []
    page = 1

    while True:
        payload, _ = github_request(
            "GET",
            f"/repos/{owner}/{repo}/issues",
            token,
            params={"state": "open", "per_page": 100, "page": page},
        )
        if not payload:
            break
        issues.extend(payload)
        if len(payload) < 100:
            break
        page += 1

    return issues


def find_existing_issue(owner: str, repo: str, token: str, title: str) -> dict[str, Any] | None:
    """Find an existing backlog issue if one is already open."""
    return select_existing_issue(list_open_issues(owner, repo, token), title)


def render_failure_body(reason: str, target_group: str, run_url: str, job_status: str, generated_at: str) -> str:
    """Render the body for scan/report failures."""
    lines = [
        "# Security patch workflow failed",
        "",
        f"- Generated at: {generated_at}",
        f"- Target group: {target_group}",
        f"- Run: {run_url}",
        f"- Job status: {job_status}",
        "",
        f"- Failure reason: {reason}",
        "",
        "The playbook did not produce a usable report, so host-level findings are unavailable.",
        "Check the workflow logs for the underlying Ansible failure.",
    ]
    return "\n".join(lines)


def render_finding(finding: dict[str, Any]) -> str:
    """Render a single finding as a markdown bullet."""
    fixed = finding.get("fixed_version") or "n/a"
    return (
        f"- {finding.get('id', '')} | {finding.get('package', '')} | "
        f"installed {finding.get('installed_version', '')} | fixed {fixed} | {finding.get('severity', '')}"
    )


def render_report_body(report: dict[str, Any], run_url: str) -> tuple[str, list[dict[str, Any]]]:
    """Render the backlog issue body from a report."""
    hosts = report.get("hosts") or []
    alert_hosts = [host for host in hosts if host.get("status") in {"needs_attention", "scan_failed"}]

    lines = [
        "# Security patch report",
        "",
        f"- Generated at: {report.get('generated_at', '')}",
        f"- Target group: {report.get('target_group', '')}",
        f"- Run: {run_url}",
        f"- Scanned hosts: {report.get('total_hosts', 0)}",
        f"- Clean hosts: {report.get('clean_count', 0)}",
        f"- Patched hosts: {report.get('patched_count', 0)}",
        f"- Alert hosts: {len(alert_hosts)}",
        "",
        "| Host | Status | Before | After | Reboot | Reason |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]

    for host in hosts:
        lines.append(
            f"| {host.get('host', '')} | {host.get('status', '')} | "
            f"{host.get('before_count', 0)} | {host.get('after_count', 0)} | "
            f"{'yes' if host.get('reboot_required') else 'no'} | {host.get('alert_reason', '')} |"
        )

    if alert_hosts:
        lines.append("")
        lines.append("## Alert details")
        for host in alert_hosts:
            lines.append("")
            lines.append(f"### {host.get('host', '')}")
            lines.append(f"- Status: {host.get('status', '')}")
            lines.append(f"- Reason: {host.get('alert_reason', '')}")
            lines.append(f"- Before: {host.get('before_count', 0)} findings")
            lines.append(f"- After: {host.get('after_count', 0)} findings")
            findings = host.get("findings") or []
            if findings:
                lines.append("- Findings:")
                for finding in findings[:5]:
                    lines.append(f"  {render_finding(finding)}")

    return "\n".join(lines), alert_hosts


def upsert_issue(owner: str, repo: str, token: str, title: str, body: str) -> tuple[int, str]:
    """Create a backlog issue or append a comment to the existing one."""
    existing_issue = find_existing_issue(owner, repo, token, title)
    if existing_issue:
        github_request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{existing_issue['number']}/comments",
            token,
            body={"body": body},
        )
        return existing_issue["number"], "updated"

    created, _ = github_request(
        "POST",
        f"/repos/{owner}/{repo}/issues",
        token,
        body={"title": title, "body": body},
    )
    return created["number"], "created"


def close_issue(owner: str, repo: str, token: str, issue_number: int) -> None:
    """Close an existing backlog issue."""
    github_request(
        "PATCH",
        f"/repos/{owner}/{repo}/issues/{issue_number}",
        token,
        body={"state": "closed"},
    )


def parse_repository(repository: str) -> tuple[str, str]:
    """Split the GitHub repository slug into owner and repo."""
    if "/" not in repository:
        raise ValueError(f"Invalid GitHub repository slug: {repository}")
    owner, repo = repository.split("/", 1)
    if not owner or not repo:
        raise ValueError(f"Invalid GitHub repository slug: {repository}")
    return owner, repo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or update the security patch backlog issue.")
    parser.add_argument("--report-path", type=Path, default=None, help="Path to the JSON report.")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"), help="GitHub repository slug.")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"), help="GitHub token with issues:write.")
    parser.add_argument("--run-url", default=os.environ.get("RUN_URL"), help="Workflow run URL.")
    parser.add_argument("--target-group", default=os.environ.get("TARGET_GROUP", "all"), help="Target server group.")
    parser.add_argument("--job-status", default=os.environ.get("JOB_STATUS", "unknown"), help="Job status string.")
    parser.add_argument("--title", default=ISSUE_TITLE, help="Backlog issue title.")
    args = parser.parse_args(argv)

    report_path = args.report_path or (
        Path(os.environ["REPORT_PATH"]) if os.environ.get("REPORT_PATH") else None
    )

    if not report_path:
        print("REPORT_PATH is required.", file=sys.stderr)
        return 1
    if not args.repository:
        print("GITHUB_REPOSITORY is required.", file=sys.stderr)
        return 1
    if not args.token:
        print("GITHUB_TOKEN is required.", file=sys.stderr)
        return 1
    if not args.run_url:
        print("RUN_URL is required.", file=sys.stderr)
        return 1

    try:
        owner, repo = parse_repository(args.repository)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    target_group = args.target_group or "all"
    job_status = args.job_status or "unknown"

    report, failure_reason = load_report(report_path)
    if failure_reason:
        body = render_failure_body(failure_reason, target_group, args.run_url, job_status, utc_now())
        issue_number, action = upsert_issue(owner, repo, args.token, args.title, body)
        print(f"{action.capitalize()} issue #{issue_number} with failure details.")
        return 0

    body, alert_hosts = render_report_body(report, args.run_url)
    existing_issue = find_existing_issue(owner, repo, args.token, args.title)

    if alert_hosts:
        issue_number, action = upsert_issue(owner, repo, args.token, args.title, body)
        print(f"{action.capitalize()} issue #{issue_number} with the latest report.")
        return 0

    if existing_issue:
        github_request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{existing_issue['number']}/comments",
            args.token,
            body={
                "body": (
                    f"Security patch run completed cleanly at {report.get('generated_at', '')} "
                    f"for target group `{report.get('target_group', target_group)}`."
                )
            },
        )
        close_issue(owner, repo, args.token, existing_issue["number"])
        print(f"Closed issue #{existing_issue['number']} because no alerts remain.")
        return 0

    print("No unresolved findings were detected and no backlog issue is open.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
