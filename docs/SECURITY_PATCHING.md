# Weekly Security Patching

This repository includes a weekly Linux security patch workflow for HIGH and CRITICAL OS package vulnerabilities.

## What It Does

- scans hosts with Trivy
- installs available OS updates when fixes exist
- rescans after remediation
- writes a host summary JSON report
- opens or updates a GitHub issue when findings remain

Notifications stay inside the project: unresolved findings become a GitHub issue instead of a separate phone or SMS integration.

## Workflow Shape

The implementation is intentionally split into small stages:

- `playbooks/maintenance/security-patch.yml`
- `playbooks/maintenance/security-patch/setup.yml`
- `playbooks/maintenance/security-patch/scan-before.yml`
- `playbooks/maintenance/security-patch/remediate.yml`
- `playbooks/maintenance/security-patch/scan-after.yml`
- `playbooks/maintenance/security-patch/summary.yml`
- `playbooks/maintenance/security-patch/failure.yml`
- `playbooks/maintenance/security-patch/cleanup.yml`
- `playbooks/maintenance/security-patch/report.yml`

Helper scripts live in `scripts/`:

- `scripts/summarize_trivy.py`
- `scripts/upsert_security_patch_issue.py`

## Manual Run

Use the workflow dispatch input to target a specific server group, or run the playbook directly:

```bash
ansible-playbook playbooks/maintenance/security-patch.yml \
  -i inventories/production/hosts.yml \
  --limit "all,localhost" \
  -e "security_patch_target_group=all"
```

If you only want to validate the helper layer, run the Python tests or parse the stage files with `yaml.safe_load`.
