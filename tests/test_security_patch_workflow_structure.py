#!/usr/bin/env python3
"""Structure checks for the weekly security patch workflow."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent


def test_security_patch_workflow_uses_ephemeral_artifacts():
    workflow = yaml.safe_load((ROOT / ".github/workflows/weekly-security-patch.yml").read_text(encoding="utf-8"))
    steps = {step["name"]: step for step in workflow["jobs"]["security-patch"]["steps"]}

    assert "inventory_path=\"$RUNNER_TEMP/github-actions-hosts.yml\"" in steps["Create inventory from config"]["run"]
    assert "INVENTORY_PATH=\"$RUNNER_TEMP/github-actions-hosts.yml\"" in steps["Run security patch playbook"]["run"]
    assert "REPORT_PATH=\"$RUNNER_TEMP/security-patch-report.json\"" in steps["Run security patch playbook"]["run"]
    assert steps["Create or update security patch issue"]["env"]["REPORT_PATH"] == "${{ runner.temp }}/security-patch-report.json"
    assert steps["Create or update security patch issue"]["run"] == "python3 scripts/upsert_security_patch_issue.py"
