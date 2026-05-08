#!/usr/bin/env python3
"""Structure checks for the weekly security patch workflow."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent


def _include_task_path(task):
    return task["ansible.builtin.include_tasks"]


def test_security_patch_playbook_uses_stage_task_files():
    playbook = yaml.safe_load((ROOT / "playbooks/maintenance/security-patch.yml").read_text(encoding="utf-8"))
    host_play = playbook[0]
    localhost_play = playbook[1]

    assert len(host_play["tasks"]) == 1

    host_block = host_play["tasks"][0]
    assert [task["name"] for task in host_block["block"]] == [
        "Run security patch setup tasks",
        "Run pre-remediation security patch scan",
        "Run remediation tasks",
        "Run post-remediation security patch scan",
        "Build host summary",
    ]
    assert [_include_task_path(task) for task in host_block["block"]] == [
        "{{ playbook_dir }}/security-patch/setup.yml",
        "{{ playbook_dir }}/security-patch/scan-before.yml",
        "{{ playbook_dir }}/security-patch/remediate.yml",
        "{{ playbook_dir }}/security-patch/scan-after.yml",
        "{{ playbook_dir }}/security-patch/summary.yml",
    ]
    assert [task["name"] for task in host_block["rescue"]] == ["Record scan failure summary"]
    assert _include_task_path(host_block["rescue"][0]) == "{{ playbook_dir }}/security-patch/failure.yml"
    assert [task["name"] for task in host_block["always"]] == ["Remove temporary Trivy installer"]
    assert _include_task_path(host_block["always"][0]) == "{{ playbook_dir }}/security-patch/cleanup.yml"

    localhost_task_names = [task["name"] for task in localhost_play["tasks"]]
    assert localhost_task_names == ["Assemble security patch report"]
    assert _include_task_path(localhost_play["tasks"][0]) == "{{ playbook_dir }}/security-patch/report.yml"


def test_security_patch_task_files_parse():
    task_files = [
        ROOT / "playbooks/maintenance/security-patch/setup.yml",
        ROOT / "playbooks/maintenance/security-patch/scan-before.yml",
        ROOT / "playbooks/maintenance/security-patch/remediate.yml",
        ROOT / "playbooks/maintenance/security-patch/scan-after.yml",
        ROOT / "playbooks/maintenance/security-patch/summary.yml",
        ROOT / "playbooks/maintenance/security-patch/failure.yml",
        ROOT / "playbooks/maintenance/security-patch/cleanup.yml",
        ROOT / "playbooks/maintenance/security-patch/report.yml",
    ]

    for task_file in task_files:
        parsed = yaml.safe_load(task_file.read_text(encoding="utf-8"))
        assert isinstance(parsed, list)
