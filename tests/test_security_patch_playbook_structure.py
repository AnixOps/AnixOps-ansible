#!/usr/bin/env python3
"""Structure checks for the weekly security patch workflow."""

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
PLAYBOOK = ROOT / "playbooks/maintenance/security-patch.yml"
TASK_DIR = ROOT / "playbooks/maintenance/security-patch"
TASK_FILES = [
    TASK_DIR / "setup.yml",
    TASK_DIR / "scan-before.yml",
    TASK_DIR / "remediate.yml",
    TASK_DIR / "reboot-check.yml",
    TASK_DIR / "scan-after.yml",
    TASK_DIR / "summary.yml",
    TASK_DIR / "failure.yml",
    TASK_DIR / "cleanup.yml",
    TASK_DIR / "report.yml",
]

EXPECTED_DEFAULTS = {
    "security_patch_apply_updates": True,
    "security_patch_allow_reboot": False,
    "security_patch_reboot_timeout": 600,
    "security_patch_trivy_version": "",
    "security_patch_trivy_timeout": "15m",
    "security_patch_trivy_update_db": True,
    "security_patch_trivy_db_repository": "",
    "security_patch_trivy_cache_dir": "/var/cache/trivy",
    "security_patch_trivy_bin": "/usr/local/bin/trivy",
    "security_patch_apt_lock_timeout": 300,
    "security_patch_dnf_security_only": True,
    "security_patch_severity": "HIGH,CRITICAL",
    "security_patch_max_findings_in_report": 10,
}

TASK_KEYWORDS = {
    "name", "when", "vars", "register", "changed_when", "failed_when", "until", "retries", "delay",
    "no_log", "delegate_to", "become", "become_user", "environment", "loop", "loop_control", "tags",
    "block", "rescue", "always", "args", "run_once", "ignore_errors", "ignore_unreachable", "notify",
    "check_mode", "diff", "any_errors_fatal", "throttle", "timeout", "connection", "remote_user", "vars_files",
}


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _include_task_path(task):
    return task["ansible.builtin.include_tasks"]


def _iter_tasks(tasks):
    """Yield every task, descending into block/rescue/always."""
    for task in tasks:
        yield task
        for section in ("block", "rescue", "always"):
            if section in task:
                yield from _iter_tasks(task[section])


def _module_of(task):
    modules = [key for key in task if key not in TASK_KEYWORDS]
    assert len(modules) == 1, f"task {task.get('name')!r} should contain exactly one module key, got {modules}"
    return modules[0]


def _all_tasks():
    playbook = _load(PLAYBOOK)
    for play in playbook:
        for section in ("pre_tasks", "tasks", "post_tasks", "handlers"):
            yield from _iter_tasks(play.get(section) or [])
    for task_file in TASK_FILES:
        yield from _iter_tasks(_load(task_file))


def test_security_patch_playbook_uses_stage_task_files():
    playbook = _load(PLAYBOOK)
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


def test_security_patch_host_play_settings():
    host_play = _load(PLAYBOOK)[0]

    assert host_play["hosts"] == "all:!localhost"
    assert host_play["serial"] == 1
    assert host_play["become"] is True
    assert host_play["gather_facts"] is True
    assert host_play["max_fail_percentage"] == 100
    assert host_play["any_errors_fatal"] is False
    # The one sanctioned ignore_unreachable: report.yml emits placeholder summaries.
    assert host_play["ignore_unreachable"] is True
    assert host_play["tags"] == ["security_patch"]
    assert host_play["tasks"][0]["name"], "the stage block must be named"
    assert [task["name"] for task in host_play["pre_tasks"]] == ["Initialize security patch facts"]


def test_security_patch_localhost_play_settings():
    localhost_play = _load(PLAYBOOK)[1]

    assert localhost_play["hosts"] == "localhost"
    assert localhost_play["connection"] == "local"
    assert localhost_play["become"] is False
    assert localhost_play["gather_facts"] is False
    assert localhost_play["serial"] == 1
    assert "max_fail_percentage" in localhost_play
    assert localhost_play["tags"] == ["security_patch", "report"]
    assert "security_patch_report_path" in localhost_play["vars"]
    assert "security_patch_report_markdown_path" in localhost_play["vars"]


def test_security_patch_variable_defaults():
    host_play = _load(PLAYBOOK)[0]
    host_vars = host_play["vars"]

    for name, expected in EXPECTED_DEFAULTS.items():
        assert name in host_vars, f"missing default for {name}"
        assert host_vars[name] == expected, f"{name} default changed: {host_vars[name]!r} != {expected!r}"

    # The report play mirrors the knobs it records; they must agree with the host play.
    localhost_vars = _load(PLAYBOOK)[1]["vars"]
    for name in ("security_patch_apply_updates", "security_patch_severity"):
        assert localhost_vars[name] == host_vars[name]

    # Mode and reboot knobs must gate the remediation tasks.
    remediate_text = (TASK_DIR / "remediate.yml").read_text(encoding="utf-8")
    assert "security_patch_apply_updates | bool" in remediate_text
    assert "security_patch_allow_reboot | bool" in remediate_text
    assert "ansible.builtin.reboot" in remediate_text
    assert "security_patch_apt_lock_timeout" in remediate_text


def test_security_patch_task_files_parse():
    for task_file in TASK_FILES:
        parsed = _load(task_file)
        assert isinstance(parsed, list), f"{task_file.name} must be a task list"
        assert parsed, f"{task_file.name} must not be empty"

    assert (TASK_DIR / "report.md.j2").is_file()


def test_security_patch_tasks_follow_repo_conventions():
    tasks = list(_all_tasks())
    assert tasks

    for task in tasks:
        name = task.get("name")
        assert name, f"unnamed task: {task}"
        assert name[0].isupper(), f"task name must start with an uppercase letter: {name!r}"
        assert not name.startswith("{{"), f"task name must not start with Jinja: {name!r}"
        assert "ignore_errors" not in task, f"ignore_errors is forbidden: {name!r}"

        module = _module_of(task)
        assert "." in module, f"module must use its FQCN: {module} in {name!r}"

        args = task[module] if isinstance(task[module], dict) else {}
        if module in ("ansible.builtin.command", "ansible.builtin.shell"):
            assert "changed_when" in task or "creates" in args or "removes" in args, (
                f"{module} task {name!r} needs changed_when or creates/removes"
            )
            assert "argv" in args, f"{module} task {name!r} should use the argv form"
        if module in ("ansible.builtin.get_url", "ansible.builtin.apt", "ansible.builtin.dnf"):
            assert task.get("retries", 0) >= 3 and "until" in task, f"{module} task {name!r} needs retries/until"
        if module in ("ansible.builtin.copy", "ansible.builtin.template", "ansible.builtin.file") and (
            args.get("state") not in ("absent",)
        ):
            assert "mode" in args, f"{module} task {name!r} needs an explicit mode"


def test_security_patch_yaml_uses_true_false_booleans():
    pattern = re.compile(r":\s+(yes|no|Yes|No|True|False)\s*$")
    for path in [PLAYBOOK, *TASK_FILES]:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            assert not pattern.search(line), f"{path.name}:{number} uses a non true/false boolean: {line.strip()}"


def test_security_patch_summary_schemas_agree():
    """pre_tasks init, summary.yml, failure.yml and the report placeholder share one key set."""
    playbook = _load(PLAYBOOK)
    init_keys = set(playbook[0]["pre_tasks"][0]["ansible.builtin.set_fact"]["security_patch_summary"])

    key_pattern = re.compile(r"^\s*'([a-z_]+)':", re.MULTILINE)
    summary_keys = set(key_pattern.findall((TASK_DIR / "summary.yml").read_text(encoding="utf-8")))
    failure_keys = set(key_pattern.findall((TASK_DIR / "failure.yml").read_text(encoding="utf-8")))

    report_tasks = _load(TASK_DIR / "report.yml")
    collect = next(task for task in report_tasks if task["name"] == "Collect host summaries")
    placeholder_keys = set(collect["vars"]["security_patch_placeholder_summary"])

    required = {
        "host", "status", "alert_reason", "before_count", "after_count", "reboot_required", "rebooted",
        "apply_updates", "severity", "trivy_version", "update_rc", "findings", "placeholder",
    }
    assert required <= init_keys
    assert init_keys == summary_keys == failure_keys == placeholder_keys

    report_keys = set(key_pattern.findall((TASK_DIR / "report.yml").read_text(encoding="utf-8")))
    assert {
        "schema_version", "generated_at", "target_group", "apply_updates", "total_hosts", "clean_count",
        "patched_count", "alert_count", "unreachable_count", "rebooted_count", "reboot_required_count", "hosts",
    } <= report_keys
