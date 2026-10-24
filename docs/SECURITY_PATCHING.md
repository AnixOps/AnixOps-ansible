# Weekly Security Patching | 每周安全补丁

`playbooks/maintenance/security-patch.yml` scans every Linux host for OS package
vulnerabilities with [Trivy](https://github.com/aquasecurity/trivy), installs the
available fixes, rescans, and publishes one JSON report plus a Markdown summary.
GitHub Actions (`.github/workflows/weekly-security-patch.yml`) turns the report into
a single "backlog" issue, so notifications stay inside the project.

## What a run does

For each host, one at a time (`serial: 1`):

| Stage | File | What happens |
| --- | --- | --- |
| setup | `security-patch/setup.yml` | gather facts, validate the OS family (Debian/RedHat), create the Trivy cache dir, install or re-install Trivy (`security_patch_trivy_version` pin), verify `trivy --version`, refresh the vulnerability DB once (`trivy image --download-db-only`) |
| scan-before | `security-patch/scan-before.yml` | `trivy fs /` (OS packages only, chosen severities, JSON) summarised by `scripts/summarize_trivy.py` |
| remediate | `security-patch/remediate.yml` | apply updates when allowed and patchable findings exist, detect pending reboots (`security-patch/reboot-check.yml`), optionally reboot |
| scan-after | `security-patch/scan-after.yml` | identical rescan so the before/after counts are comparable |
| summary | `security-patch/summary.yml` | build the per-host summary dictionary |
| failure (rescue) | `security-patch/failure.yml` | record a `scan_failed` summary with the error message of the task that failed |
| cleanup (always) | `security-patch/cleanup.yml` | remove the temporary installer |

Then, on `localhost`, `security-patch/report.yml` aggregates every host summary into
`security-patch-report.json` (`schema_version: 1`) and `security-patch-report.md`.

Design points that keep the run honest:

* Every per-host failure is caught by the block/rescue and turned into a
  `scan_failed` summary. Fact gathering happens inside that block on purpose: under
  `serial: 1` a host that fails outside it would end the whole playbook before the
  report play runs.
* `ignore_unreachable: true` on the host play is the one sanctioned exception to the
  repo's "fail loudly" rule. An unreachable host stays in the play, fails the facts
  check, is recorded by `failure.yml` with `unreachable: true`, and shows up in the
  report and the issue instead of disappearing. Hosts that produced no summary at all
  (for example excluded by `--limit`) get a placeholder entry. Both are counted in
  `unreachable_count`.
* Package manager failures do not abort the host either: `remediate.yml` records
  `security_patch_update_result = {rc, changed, stdout, stderr}` (rc is synthesised
  for the apt module, which returns none) and the post-scan still runs, so the host
  ends up as `needs_attention` with the reason "package update command failed".
* The raw Trivy JSON is large, so the tasks carrying it run with `no_log: true`;
  explicit verification tasks produce readable failure reasons (return code plus the
  last 500 characters of stderr) that end up in `alert_reason`.

## Variables

The defaults live in the `security_patch_defaults` dictionary of the playbook; the
first pre_task resolves the effective `security_patch_<knob>` per host with
`| default(...)`. Because of that indirection every knob can be set per host or group
in the inventory (`security_patch_allow_reboot: true` in `group_vars/web_servers`) as
well as globally with `-e security_patch_<knob>=...` (extra-vars also reach the report
play). Plain play-level `vars` would shadow inventory values, which is why the knobs
are not defined that way.

| Variable | Default | Meaning |
| --- | --- | --- |
| `security_patch_apply_updates` | `true` | `false` = scan-only: report findings, never install packages or reboot |
| `security_patch_allow_reboot` | `false` | `true` = reboot (`ansible.builtin.reboot`, `reboot_timeout` below) when updates were applied successfully and the OS says a reboot is required |
| `security_patch_reboot_timeout` | `600` | seconds to wait for the host to come back |
| `security_patch_severity` | `"HIGH,CRITICAL"` | Trivy `--severity` filter |
| `security_patch_max_findings_in_report` | `10` | post-remediation findings embedded per host in the report |
| `security_patch_apt_lock_timeout` | `300` | seconds to wait for the dpkg/apt lock |
| `security_patch_dnf_security_only` | `true` | RedHat: `dnf --security` (security errata only); set `false` to apply every update |
| `security_patch_install_dnf_utils` | `true` | RedHat: install `dnf-utils` so `needs-restarting -r` works |
| `security_patch_trivy_version` | `""` | release tag to install (`v0.56.2` or `0.56.2`); empty = latest. A mismatching installed binary is replaced |
| `security_patch_trivy_install_script` | upstream `contrib/install.sh` | installer URL (`get_url`, 3 retries) |
| `security_patch_trivy_installer_checksum` | `""` | optional `get_url` checksum for the installer (`sha256:<hex>`) |
| `security_patch_trivy_installer_path` | `/tmp/trivy-install.sh` | where the installer is staged (removed by cleanup) |
| `security_patch_trivy_bin` | `/usr/local/bin/trivy` | binary path (`-b` for the installer, `creates:` guard) |
| `security_patch_trivy_cache_dir` | `/var/cache/trivy` | `--cache-dir` for DB and scans |
| `security_patch_trivy_update_db` | `true` | refresh the DB once in setup (3 retries) and scan with `--skip-db-update` |
| `security_patch_trivy_db_repository` | `""` | optional `--db-repository` (mirror) |
| `security_patch_trivy_timeout` | `"15m"` | Trivy `--timeout` for DB refresh and scans |
| `security_patch_trivy_skip_dirs` | `/var/lib/docker`, `/var/lib/containerd`, `/snap` | `--skip-dirs` list (container layers are not host packages); the cache dir is always added |
| `security_patch_target_group` | `all` | inventory group the report covers (hosts without a summary become placeholders) |
| `security_patch_report_path` | `<repo>/security-patch-report.json` | JSON report path (report play) |
| `security_patch_report_markdown_path` | `<report>.md` | Markdown twin of the report |

### Remediation details

* Debian/Ubuntu: `ansible.builtin.apt` with `upgrade: dist`, `update_cache: true`,
  `lock_timeout`, `dpkg_options: force-confdef,force-confold`, `autoremove: true`,
  `DEBIAN_FRONTEND=noninteractive`, 3 retries. Reboot detection:
  `/var/run/reboot-required`.
* RedHat family: `ansible.builtin.dnf` with `name: "*"`, `state: latest`,
  `update_only: true` (never installs new packages), `security: true`, `bugfix: false`,
  3 retries. Reboot detection: `needs-restarting -r` (exit 1 = reboot needed).
  Note: distributions without security errata metadata will see nothing to apply with
  `security: true`; set `security_patch_dnf_security_only: false` there.
* Updates run only when `security_patch_apply_updates` is true AND the pre-scan found
  at least one finding with a fixed version.

### Scan-only mode

```bash
ansible-playbook playbooks/maintenance/security-patch.yml \
  -i inventories/production/hosts.yml --limit "all,localhost" \
  -e security_patch_apply_updates=false
```

No packages are installed and no host is rebooted. Hosts with findings are reported
as `needs_attention` with the reason "updates were not applied (scan-only mode) and
vulnerabilities remain"; the report carries `apply_updates: false` and the Markdown /
issue body say "Mode: scan-only".

### Reboot policy

* Reboots are off by default. A host that needs one is reported as `patched` with the
  reason "security updates were applied successfully; reboot required to complete",
  `reboot_required: true`, and is counted in `reboot_required_count`.
* With `-e security_patch_allow_reboot=true` the host is rebooted (and the reboot flag
  re-checked afterwards) only when updates were applied in this run (`update_rc == 0`
  and not scan-only). Hosts are patched one at a time, so at most one host is
  rebooting at any moment. `rebooted: true` is recorded per host and summed in
  `rebooted_count`.
* Recommended: enable reboots for stateless groups (`web_servers`, `proxy_servers`)
  and keep them disabled for `postgres_servers` / `observability`, rebooting those in
  a planned window.

## Report schema (`schema_version: 1`)

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-08T04:00:00Z",
  "target_group": "all",
  "apply_updates": true,
  "severity": "HIGH,CRITICAL",
  "total_hosts": 3, "clean_count": 1, "patched_count": 1,
  "needs_attention_count": 1, "scan_failed_count": 0, "alert_count": 1,
  "unreachable_count": 0, "reboot_required_count": 1, "rebooted_count": 0,
  "hosts": [
    {
      "host": "web-1", "os_family": "Debian", "pkg_mgr": "apt",
      "status": "patched",
      "alert_reason": "security updates were applied successfully; reboot required to complete",
      "before_count": 4, "before_patchable_count": 4, "before_unpatchable_count": 0,
      "after_count": 0, "after_patchable_count": 0, "after_unpatchable_count": 0,
      "update_rc": 0, "update_changed": true,
      "reboot_required": true, "rebooted": false,
      "apply_updates": true, "severity": "HIGH,CRITICAL", "trivy_version": "0.56.2",
      "unreachable": false,
      "findings": []
    }
  ]
}
```

Host `status` values: `clean` (nothing found), `patched` (findings before, none
after), `needs_attention` (findings remain), `scan_failed` (a stage failed, host
unreachable, or no summary at all). `findings` lists the remaining post-remediation
findings (deduplicated, CRITICAL first, capped by
`security_patch_max_findings_in_report`).

## GitHub issue and step summary

`scripts/upsert_security_patch_issue.py` runs after the playbook (`if: always()`):

* `needs_attention` / `scan_failed` hosts -> creates the backlog issue (title
  `AnixOps security patch backlog`, labels `security,automation` via `--labels`; if
  GitHub rejects the labels with 422 the issue is created without them) or appends the
  latest report as a comment to the open one.
* no alert hosts -> comments on and closes the open issue; nothing happens when none
  is open.
* report missing/unparsable -> the failure is filed in the issue.
* The issue body starts with the marker `<!-- anixops-security-patch -->`; the script
  finds "its" issue by marker + title and falls back to the exact title.
* When `GITHUB_STEP_SUMMARY` is set the rendered Markdown is appended to it. The
  playbook's own `<report>.md` can be appended as well:
  `cat "$REPORT_PATH.md" >> "$GITHUB_STEP_SUMMARY"` (same table, no marker).
* Transient API errors (5xx, 429, secondary rate limits / `Retry-After`) are retried
  with exponential backoff (4 retries, capped at 60 s).
* `--dry-run` renders the body without calling GitHub. Exit codes: `0` issue state
  matches the report, `1` invalid invocation, `2` GitHub API failure after retries.

## Runbook: a `needs_attention` issue was opened

1. Open the issue; the table shows status, before/after counts and the reason per
   host. The "Alert details" section lists up to five remaining findings per host
   (id, package, installed and fixed version, severity).
2. Act on the reason:
   * **patchable vulnerabilities remain after remediation**: the fix exists but was
     not installed. Typical causes: the package is held (`apt-mark showhold`), a
     pinned repository, or a Trivy fixed version that the distribution ships under a
     different version string. Fix the hold/pin and rerun for that host:
     `ansible-playbook playbooks/maintenance/security-patch.yml -i ... --limit "<host>,localhost"`.
   * **package update command failed and vulnerabilities remain**: `update_rc` is
     non-zero. Run the playbook with `-vv` for that host (the apt/dnf output is kept in
     `security_patch_update_result.stdout/stderr`) or run `apt-get dist-upgrade` /
     `dnf update --security` manually; common causes are a broken mirror, a full disk
     or a held dpkg lock (raise `security_patch_apt_lock_timeout`).
   * **vulnerabilities remain without a package fix**: nothing to install yet. Track
     the CVE; narrow the severity filter (`-e security_patch_severity=CRITICAL`) if
     HIGH unfixed CVEs cause noise, and consider mitigations for CRITICAL ones.
   * **updates were not applied (scan-only mode)**: expected in scan-only runs; rerun
     with updates enabled.
   * **security updates were applied successfully; reboot required to complete**
     (status `patched`, not an alert): schedule the reboot or rerun with
     `-e security_patch_allow_reboot=true --limit "<host>,localhost"`.
3. `scan_failed` hosts: the reason is the failing task's message. "host unreachable or
   fact gathering failed" means SSH/python problems (check the inventory and
   `ssh -p <port> <user>@<host>`); "Trivy ... scan failed (rc=...)" includes Trivy's
   stderr (disk full in `/var/cache/trivy`, DB download blocked, unsupported OS);
   "summarize_trivy.py failed" points at the controller's Python.
4. Rerun the affected hosts. The next clean run comments on the issue and closes it
   automatically; do not close it by hand unless the host was decommissioned (then
   remove it from the inventory so it stops producing placeholder entries).

## Manual run

```bash
# Full run for one group, with reboots allowed
ansible-playbook playbooks/maintenance/security-patch.yml \
  -i inventories/production/hosts.yml \
  --limit "web_servers,localhost" \
  -e security_patch_target_group=web_servers \
  -e security_patch_allow_reboot=true \
  -e security_patch_report_path=/tmp/security-patch-report.json

# Report play only (every host becomes a placeholder; handy to test report wiring)
ansible-playbook playbooks/maintenance/security-patch.yml \
  -i inventories/production/hosts.yml --limit "web_servers,localhost" --tags report \
  -e security_patch_target_group=web_servers
```

Always keep `localhost` in `--limit`, otherwise the report play does not run. Plays are
tagged `security_patch` (host play) and `security_patch,report` (report play).

## Validation

```bash
export PATH=$HOME/.local/bin:$PATH
yamllint -c .yamllint.yml playbooks/maintenance/security-patch.yml playbooks/maintenance/security-patch
ansible-lint --offline playbooks/maintenance/security-patch.yml
ansible-playbook --syntax-check playbooks/maintenance/security-patch.yml
python3 -m pytest -q tests/test_security_patch_helpers.py tests/test_security_patch_playbook_structure.py
python3 scripts/summarize_trivy.py --input some-trivy-report.json --pretty
python3 scripts/upsert_security_patch_issue.py --report-path security-patch-report.json \
  --repository owner/repo --run-url https://example.invalid/run/1 --dry-run
```

`tests/test_security_patch_playbook_structure.py` pins the stage structure (one named
block with five includes, rescue and always includes, one include in the report
play), the variable defaults, the repo conventions (FQCN, named tasks, `changed_when`,
retries, modes, no `ignore_errors`) and that the summary schema is identical in the
init, `summary.yml`, `failure.yml` and the report placeholder.
