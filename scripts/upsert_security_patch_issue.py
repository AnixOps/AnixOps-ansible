#!/usr/bin/env python3
"""Upsert the weekly security patch GitHub issue from a report file.

Reads ``security-patch-report.json`` (written by
``playbooks/maintenance/security-patch.yml``) and keeps exactly one open
"backlog" issue in sync with it:

* hosts with status ``needs_attention`` or ``scan_failed`` -> create the issue, or
  add the latest report as a comment to the already open one;
* no alert hosts -> comment on and close the open issue, if any;
* report missing or unparsable -> file the failure in the issue instead.

The issue is recognised by the HTML marker ``<!-- anixops-security-patch -->`` in
its body (exact title match is the fallback for issues created before the marker
existed).  When ``$GITHUB_STEP_SUMMARY`` is set the rendered Markdown is appended
to it so the run summary shows the table without opening the issue.

Transient GitHub API failures (5xx, 429, secondary rate limits) are retried with
exponential backoff.  Creating an issue with labels that do not exist yields a
422; the script then retries once without labels.

Exit codes:
    0  the issue state matches the report (created / updated / closed / nothing to do)
    1  invalid invocation (missing repository, token, run URL or report path)
    2  the GitHub API kept failing after the retries were exhausted
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API_BASE = "https://api.github.com"
API_VERSION = "2022-11-28"
ISSUE_TITLE = "AnixOps security patch backlog"
ISSUE_MARKER = "<!-- anixops-security-patch -->"
DEFAULT_LABELS = "security,automation"
ALERT_STATUSES = frozenset({"needs_attention", "scan_failed"})
USER_AGENT = "anixops-security-patch"

DEFAULT_RETRIES = 4
DEFAULT_BACKOFF_SECONDS = 2.0
MAX_RETRY_DELAY_SECONDS = 60.0
REQUEST_TIMEOUT_SECONDS = 30

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_API_FAILURE = 2

# A transport performs one HTTP exchange and returns (status, headers, body-text).
TransportResponse = tuple[int, Mapping[str, str], str]
Transport = Callable[[urllib.request.Request], TransportResponse]


class TransportError(RuntimeError):
    """The request never produced an HTTP response (DNS, TLS, timeout...)."""


class GitHubAPIError(RuntimeError):
    """The GitHub API answered with a non-success status."""

    def __init__(self, method: str, path: str, status: int, detail: str) -> None:
        self.method = method
        self.path = path
        self.status = status
        self.detail = detail
        super().__init__(f"GitHub API request failed: {method} {path} -> {status}: {detail}")


def utc_now() -> str:
    """Return a compact UTC timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_report(report_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Load the report or return a failure reason."""
    if not report_path.exists():
        return None, f"report file was not created at {report_path}"

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"report file could not be parsed: {exc}"

    if not isinstance(report, dict):
        return None, "report file does not contain a JSON object"
    return report, None


# --------------------------------------------------------------------------- HTTP


def urllib_transport(request: urllib.request.Request) -> TransportResponse:
    """Default transport built on urllib; HTTP errors are returned, not raised."""
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.status, dict(response.headers.items()), response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, dict(exc.headers.items()), body
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise TransportError(str(exc)) from exc


def _header(headers: Mapping[str, str], name: str) -> str | None:
    """Case-insensitive header lookup."""
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value
    return None


def is_retryable(status: int, headers: Mapping[str, str], body: str) -> bool:
    """Server errors, 429 and GitHub's secondary rate limits are worth retrying."""
    if status >= 500:
        return True
    if status == 429:
        return True
    if status == 403:
        if _header(headers, "Retry-After") is not None:
            return True
        if _header(headers, "X-RateLimit-Remaining") == "0":
            return True
        lowered = body.lower()
        return "rate limit" in lowered or "abuse detection" in lowered
    return False


def retry_delay(attempt: int, headers: Mapping[str, str], backoff: float) -> float:
    """Seconds to wait before the next attempt (Retry-After / rate-limit reset win)."""
    retry_after = _header(headers, "Retry-After")
    if retry_after:
        try:
            return min(max(float(retry_after), 0.0), MAX_RETRY_DELAY_SECONDS)
        except ValueError:
            pass

    reset = _header(headers, "X-RateLimit-Reset")
    if reset and _header(headers, "X-RateLimit-Remaining") == "0":
        try:
            return min(max(float(reset) - time.time(), 1.0), MAX_RETRY_DELAY_SECONDS)
        except ValueError:
            pass

    return min(backoff * (2**attempt), MAX_RETRY_DELAY_SECONDS)


def github_request(
    method: str,
    path: str,
    token: str,
    *,
    params: Mapping[str, Any] | None = None,
    body: Mapping[str, Any] | None = None,
    transport: Transport | None = None,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[Any, Mapping[str, str]]:
    """Perform a GitHub REST request with retries; return parsed JSON and headers."""
    transport = transport or urllib_transport
    url = f"{API_BASE}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(dict(params))}"

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": USER_AGENT,
    }
    data: bytes | None = None
    if body is not None:
        data = json.dumps(dict(body)).encode("utf-8")
        headers["Content-Type"] = "application/json"

    last_error: str = "no attempt was made"
    for attempt in range(retries + 1):
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            status, response_headers, text = transport(request)
        except TransportError as exc:
            last_error = f"network error: {exc}"
            if attempt < retries:
                sleep(retry_delay(attempt, {}, backoff))
                continue
            raise GitHubAPIError(method, path, 0, last_error) from exc

        if 200 <= status < 300:
            return (json.loads(text) if text.strip() else None), response_headers

        last_error = text.strip() or "no response body"
        if attempt < retries and is_retryable(status, response_headers, text):
            sleep(retry_delay(attempt, response_headers, backoff))
            continue
        raise GitHubAPIError(method, path, status, last_error)

    raise GitHubAPIError(method, path, 0, last_error)  # pragma: no cover - loop always returns/raises


# -------------------------------------------------------------------------- Issues


def select_existing_issue(
    issues: list[dict[str, Any]],
    title: str,
    marker: str = ISSUE_MARKER,
) -> dict[str, Any] | None:
    """Pick the backlog issue: marker + title first, exact title as fallback; never PRs."""
    candidates = [issue for issue in issues if issue.get("title") == title and "pull_request" not in issue]
    if marker:
        for issue in candidates:
            if marker in (issue.get("body") or ""):
                return issue
    return candidates[0] if candidates else None


def list_open_issues(owner: str, repo: str, token: str, *, transport: Transport | None = None) -> list[dict[str, Any]]:
    """List open issues with pagination."""
    issues: list[dict[str, Any]] = []
    page = 1

    while True:
        payload, _ = github_request(
            "GET",
            f"/repos/{owner}/{repo}/issues",
            token,
            params={"state": "open", "per_page": 100, "page": page},
            transport=transport,
        )
        if not payload:
            break
        issues.extend(payload)
        if len(payload) < 100:
            break
        page += 1

    return issues


def find_existing_issue(
    owner: str, repo: str, token: str, title: str, *, transport: Transport | None = None
) -> dict[str, Any] | None:
    """Find an existing backlog issue if one is already open."""
    return select_existing_issue(list_open_issues(owner, repo, token, transport=transport), title)


def parse_labels(raw: str | None) -> list[str]:
    """Split a comma separated label list, dropping blanks and duplicates."""
    labels: list[str] = []
    for part in (raw or "").split(","):
        label = part.strip()
        if label and label not in labels:
            labels.append(label)
    return labels


def create_issue(
    owner: str,
    repo: str,
    token: str,
    title: str,
    body: str,
    labels: list[str],
    *,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """Create the issue; if GitHub rejects the labels (422) create it without them."""
    payload: dict[str, Any] = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels

    try:
        created, _ = github_request("POST", f"/repos/{owner}/{repo}/issues", token, body=payload, transport=transport)
        return created
    except GitHubAPIError as exc:
        if not labels or exc.status != 422:
            raise
        print(
            f"Warning: GitHub rejected labels {labels} (422); creating the issue without labels.",
            file=sys.stderr,
        )

    created, _ = github_request(
        "POST",
        f"/repos/{owner}/{repo}/issues",
        token,
        body={"title": title, "body": body},
        transport=transport,
    )
    return created


def comment_on_issue(
    owner: str, repo: str, token: str, issue_number: int, body: str, *, transport: Transport | None = None
) -> None:
    """Append a comment to an issue."""
    github_request(
        "POST",
        f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
        token,
        body={"body": body},
        transport=transport,
    )


def close_issue(owner: str, repo: str, token: str, issue_number: int, *, transport: Transport | None = None) -> None:
    """Close an existing backlog issue."""
    github_request(
        "PATCH",
        f"/repos/{owner}/{repo}/issues/{issue_number}",
        token,
        body={"state": "closed", "state_reason": "completed"},
        transport=transport,
    )


def upsert_issue(
    owner: str,
    repo: str,
    token: str,
    title: str,
    body: str,
    labels: list[str] | None = None,
    *,
    transport: Transport | None = None,
    existing_issue: dict[str, Any] | None = None,
) -> tuple[int, str]:
    """Create a backlog issue or append a comment to the existing one."""
    if existing_issue is None:
        existing_issue = find_existing_issue(owner, repo, token, title, transport=transport)
    if existing_issue:
        comment_on_issue(owner, repo, token, existing_issue["number"], body, transport=transport)
        return existing_issue["number"], "updated"

    created = create_issue(owner, repo, token, title, body, labels or [], transport=transport)
    return created["number"], "created"


# ----------------------------------------------------------------------- Rendering


def render_failure_body(reason: str, target_group: str, run_url: str, job_status: str, generated_at: str) -> str:
    """Render the body for scan/report failures."""
    lines = [
        ISSUE_MARKER,
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


def _cell(value: Any) -> str:
    """Make a value safe for a Markdown table cell."""
    return str(value).replace("|", "/").replace("\n", " ")


def render_report_body(report: dict[str, Any], run_url: str) -> tuple[str, list[dict[str, Any]]]:
    """Render the backlog issue body from a report; return it with the alert hosts."""
    hosts = report.get("hosts") or []
    alert_hosts = [host for host in hosts if host.get("status") in ALERT_STATUSES]
    apply_updates = report.get("apply_updates", True)

    lines = [
        ISSUE_MARKER,
        "# Security patch report",
        "",
        f"- Generated at: {report.get('generated_at', '')}",
        f"- Target group: {report.get('target_group', '')}",
        f"- Run: {run_url}",
        f"- Mode: {'remediate' if apply_updates else 'scan-only (no packages were updated)'}",
        f"- Severity filter: {report.get('severity', 'HIGH,CRITICAL')}",
        f"- Scanned hosts: {report.get('total_hosts', 0)}",
        f"- Clean hosts: {report.get('clean_count', 0)}",
        f"- Patched hosts: {report.get('patched_count', 0)}",
        f"- Alert hosts: {len(alert_hosts)}",
        f"- Unreachable hosts: {report.get('unreachable_count', 0)}",
        f"- Reboot required: {report.get('reboot_required_count', 0)}",
        f"- Rebooted: {report.get('rebooted_count', 0)}",
        "",
        "| Host | Status | Before | After | Reboot | Reason |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]

    for host in hosts:
        lines.append(
            f"| {_cell(host.get('host', ''))} | {_cell(host.get('status', ''))} | "
            f"{host.get('before_count', 0)} | {host.get('after_count', 0)} | "
            f"{'yes' if host.get('reboot_required') else 'no'} | {_cell(host.get('alert_reason', ''))} |"
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
            if host.get("update_rc") not in (None, 0, "0"):
                lines.append(f"- Package update exit code: {host.get('update_rc')}")
            if host.get("rebooted"):
                lines.append("- Host was rebooted during the run")
            elif host.get("reboot_required"):
                lines.append("- Reboot required (not performed)")
            if host.get("trivy_version"):
                lines.append(f"- Trivy version: {host.get('trivy_version')}")
            findings = host.get("findings") or []
            if findings:
                lines.append("- Findings:")
                for finding in findings[:5]:
                    lines.append(f"  {render_finding(finding)}")

    return "\n".join(lines), alert_hosts


def strip_marker(body: str) -> str:
    """Remove the HTML marker line (not needed in step summaries)."""
    return "\n".join(line for line in body.split("\n") if line.strip() != ISSUE_MARKER).lstrip("\n")


def append_step_summary(markdown: str, path: str | None = None) -> bool:
    """Append Markdown to $GITHUB_STEP_SUMMARY (or an explicit path). Returns True if written."""
    target = path if path is not None else os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        return False
    try:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(markdown.rstrip("\n") + "\n\n")
    except OSError as exc:
        print(f"Warning: could not write step summary to {target}: {exc}", file=sys.stderr)
        return False
    return True


# ------------------------------------------------------------------------- CLI


def parse_repository(repository: str) -> tuple[str, str]:
    """Split the GitHub repository slug into owner and repo."""
    if "/" not in repository:
        raise ValueError(f"Invalid GitHub repository slug: {repository}")
    owner, repo = repository.split("/", 1)
    if not owner or not repo:
        raise ValueError(f"Invalid GitHub repository slug: {repository}")
    return owner, repo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create or update the security patch backlog issue.",
        epilog="Exit codes: 0 success, 1 invalid invocation, 2 GitHub API failure.",
    )
    parser.add_argument("--report-path", type=Path, default=None, help="Path to the JSON report (env REPORT_PATH).")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"), help="GitHub repository slug.")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"), help="GitHub token with issues:write.")
    parser.add_argument("--run-url", default=os.environ.get("RUN_URL"), help="Workflow run URL.")
    parser.add_argument("--target-group", default=os.environ.get("TARGET_GROUP", "all"), help="Target server group.")
    parser.add_argument("--job-status", default=os.environ.get("JOB_STATUS", "unknown"), help="Job status string.")
    parser.add_argument("--title", default=ISSUE_TITLE, help="Backlog issue title.")
    parser.add_argument(
        "--labels",
        default=os.environ.get("ISSUE_LABELS", DEFAULT_LABELS),
        help=f"Comma separated labels applied when the issue is created (default: {DEFAULT_LABELS}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render the issue body and the step summary but do not call the GitHub API.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    report_path = args.report_path or (
        Path(os.environ["REPORT_PATH"]) if os.environ.get("REPORT_PATH") else None
    )

    if not report_path:
        print("REPORT_PATH is required.", file=sys.stderr)
        return EXIT_USAGE
    if not args.repository:
        print("GITHUB_REPOSITORY is required.", file=sys.stderr)
        return EXIT_USAGE
    if not args.run_url:
        print("RUN_URL is required.", file=sys.stderr)
        return EXIT_USAGE
    if not args.token and not args.dry_run:
        print("GITHUB_TOKEN is required.", file=sys.stderr)
        return EXIT_USAGE

    try:
        owner, repo = parse_repository(args.repository)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE

    target_group = args.target_group or "all"
    job_status = args.job_status or "unknown"
    labels = parse_labels(args.labels)
    token = args.token or ""

    report, failure_reason = load_report(report_path)
    if failure_reason:
        body = render_failure_body(failure_reason, target_group, args.run_url, job_status, utc_now())
        append_step_summary(strip_marker(body))
        if args.dry_run:
            print(body)
            print("Dry run: would file the failure in the backlog issue.")
            return EXIT_OK
        try:
            issue_number, action = upsert_issue(owner, repo, token, args.title, body, labels)
        except GitHubAPIError as exc:
            print(str(exc), file=sys.stderr)
            return EXIT_API_FAILURE
        print(f"{action.capitalize()} issue #{issue_number} with failure details.")
        return EXIT_OK

    body, alert_hosts = render_report_body(report, args.run_url)
    append_step_summary(strip_marker(body))
    # Only a run against `all` can prove the whole backlog is clean; a narrowed run must not close it.
    report_group = report.get("target_group") or target_group

    if args.dry_run:
        print(body)
        print(
            "Dry run: "
            + (f"would create/update the backlog issue ({len(alert_hosts)} alert hosts)." if alert_hosts
               else "no alert hosts; would close an open backlog issue if one exists." if report_group == "all"
               else f"no alert hosts in `{report_group}`; would only comment on an open backlog issue.")
        )
        return EXIT_OK

    try:
        existing_issue = find_existing_issue(owner, repo, token, args.title)

        if alert_hosts:
            issue_number, action = upsert_issue(
                owner, repo, token, args.title, body, labels, existing_issue=existing_issue
            )
            print(f"{action.capitalize()} issue #{issue_number} with the latest report.")
            return EXIT_OK

        if existing_issue and report_group != "all":
            comment_on_issue(
                owner,
                repo,
                token,
                existing_issue["number"],
                (
                    f"Security patch run for target group `{report_group}` completed cleanly at "
                    f"{report.get('generated_at', '')} ({args.run_url}). The issue stays open: only a run "
                    "against `all` can confirm that no alerts remain."
                ),
            )
            print(f"Commented on issue #{existing_issue['number']}; not closing after a narrowed ({report_group}) run.")
            return EXIT_OK

        if existing_issue:
            comment_on_issue(
                owner,
                repo,
                token,
                existing_issue["number"],
                (
                    f"Security patch run completed cleanly at {report.get('generated_at', '')} "
                    f"for target group `{report_group}` ({args.run_url})."
                ),
            )
            close_issue(owner, repo, token, existing_issue["number"])
            print(f"Closed issue #{existing_issue['number']} because no alerts remain.")
            return EXIT_OK
    except GitHubAPIError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_API_FAILURE

    print("No unresolved findings were detected and no backlog issue is open.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
