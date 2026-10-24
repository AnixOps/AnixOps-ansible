#!/usr/bin/env python3
"""Structure and hygiene checks for the GitHub Actions workflows and composite actions.

PyYAML loads the ``on`` key as the boolean ``True``; the helpers below account for that.
"""

from __future__ import annotations

import importlib.util
import io
import re
import sys
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = ROOT / ".github" / "workflows"
ACTIONS_DIR = ROOT / ".github" / "actions"
WORKFLOW_FILES = sorted(WORKFLOWS_DIR.glob("*.yml"))
ACTION_FILES = sorted(ACTIONS_DIR.glob("*/action.yml"))

# Workflows that change real hosts: they serialise per environment+target and never cancel a running job.
DEPLOY_WORKFLOWS = {"deploy.yml", "lifecycle.yml", "weekly-security-patch.yml", "node-platform-deploy.yml"}
# Reusable workflows inherit the caller's concurrency group.
CONCURRENCY_EXEMPT = {"reusable-lint.yml"}

SITE_TAGS = [
    "common", "node_exporter", "promtail", "firewall", "nginx", "prometheus",
    "loki", "grafana", "postgresql", "v2board", "v2bx", "speedtest",
]
SERVICE_ROLES = {
    "common", "nginx", "node_exporter", "promtail", "prometheus", "loki", "grafana",
    "postgresql", "v2board", "v2bx", "speedtest", "firewall", "acme_ssl",
}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MOJIBAKE_RE = re.compile(
    "|".join(chr(point) for point in (0x923A, 0x93C8, 0x95AE, 0x9428, 0x951B, 0x9286, 0x934F, 0x93B4, 0x6D60, 0x7481, 0x9359))
    + r"|\?[^ -~\n]"  # grep is line-based: a "?" at end of line (e.g. rc=$?) is not mojibake
)


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def workflow_jobs(workflow: dict) -> Dict[str, dict]:
    return workflow["jobs"]


def iter_steps(workflow: dict) -> Iterator[Tuple[str, dict]]:
    for job_id, job in workflow_jobs(workflow).items():
        for step in job.get("steps") or []:
            yield job_id, step


def iter_action_steps(action: dict) -> Iterator[dict]:
    yield from action["runs"]["steps"]


def iter_run_blocks(document: dict, is_action: bool = False) -> Iterator[Tuple[str, str]]:
    if is_action:
        for step in iter_action_steps(document):
            if "run" in step:
                yield step.get("name", "<unnamed>"), step["run"]
        return
    for job_id, step in iter_steps(document):
        if "run" in step:
            yield f"{job_id}/{step.get('name', '<unnamed>')}", step["run"]


def iter_uses(document: dict, is_action: bool = False) -> Iterator[str]:
    if is_action:
        for step in iter_action_steps(document):
            if "uses" in step:
                yield step["uses"]
        return
    for job in workflow_jobs(document).values():
        if "uses" in job:
            yield job["uses"]
        for step in job.get("steps") or []:
            if "uses" in step:
                yield step["uses"]


def job_runs_ansible(job: dict) -> bool:
    pattern = re.compile(r"(^|[\s(])ansible(-playbook|-galaxy)?\s")
    return any(pattern.search(step.get("run", "")) for step in job.get("steps") or [])


def job_uses(job: dict, action_path: str) -> bool:
    return any(step.get("uses") == action_path for step in job.get("steps") or [])


def load_export_secrets_module():
    script = ACTIONS_DIR / "export-secrets" / "export_secrets.py"
    spec = importlib.util.spec_from_file_location("export_secrets", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # keep __pycache__ out of .github/actions/
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def workflow_ids() -> List[str]:
    return [path.name for path in WORKFLOW_FILES]


# --------------------------------------------------------------------------------------------
# Inventory of files
# --------------------------------------------------------------------------------------------

def test_expected_workflows_and_actions_exist():
    names = {path.name for path in WORKFLOW_FILES}
    assert {
        "ansible-ci.yml", "reusable-lint.yml", "security-scan.yml", "deploy.yml",
        "lifecycle.yml", "weekly-security-patch.yml", "node-platform-deploy.yml",
    } <= names
    actions = {path.parent.name for path in ACTION_FILES}
    assert {"setup-ansible", "export-secrets", "job-summary"} <= actions
    assert (ROOT / ".github" / "dependabot.yml").is_file()


# --------------------------------------------------------------------------------------------
# Per-workflow structure
# --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=workflow_ids())
def test_workflow_parses_with_name_and_triggers(path: Path):
    workflow = load_yaml(path)
    assert isinstance(workflow.get("name"), str) and workflow["name"]
    assert True in workflow, "the `on:` block is missing (PyYAML loads it as the key True)"
    assert workflow["jobs"], "a workflow needs at least one job"


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=workflow_ids())
def test_top_level_permissions_are_least_privilege(path: Path):
    workflow = load_yaml(path)
    permissions = workflow.get("permissions")
    assert isinstance(permissions, dict), "top-level permissions: block is required"
    assert permissions.get("contents") == "read"
    for scope, level in permissions.items():
        assert level in {"read", "write", "none"}, f"unexpected permission level {scope}={level}"
    write_scopes = {scope for scope, level in permissions.items() if level == "write"}
    if path.name == "weekly-security-patch.yml":
        assert write_scopes == {"issues"}
    else:
        assert not write_scopes, f"{path.name} must not request write permissions"


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=workflow_ids())
def test_every_job_has_a_timeout(path: Path):
    workflow = load_yaml(path)
    for job_id, job in workflow_jobs(workflow).items():
        if "uses" in job:
            # Reusable-workflow calls cannot carry timeout-minutes; the callee's jobs do.
            assert job["uses"].startswith("./.github/workflows/"), f"{job_id} must call a local reusable workflow"
            continue
        timeout = job.get("timeout-minutes")
        assert isinstance(timeout, int) and 0 < timeout <= 360, f"{path.name}:{job_id} needs timeout-minutes"


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=workflow_ids())
def test_workflows_default_to_bash(path: Path):
    workflow = load_yaml(path)
    has_run_steps = any("run" in step for _, step in iter_steps(workflow))
    if has_run_steps:
        assert workflow.get("defaults", {}).get("run", {}).get("shell") == "bash"


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=workflow_ids())
def test_concurrency_policy(path: Path):
    workflow = load_yaml(path)
    if path.name in CONCURRENCY_EXEMPT:
        assert "concurrency" not in workflow
        return
    concurrency = workflow.get("concurrency")
    assert isinstance(concurrency, dict) and concurrency.get("group"), f"{path.name} needs a concurrency group"
    if path.name in DEPLOY_WORKFLOWS:
        assert concurrency["cancel-in-progress"] is False, "a running deploy must never be cancelled"
        assert concurrency["group"].startswith("deploy-"), "deploy groups are shared across deploy-type workflows"
    else:
        assert concurrency["cancel-in-progress"] is True


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=workflow_ids())
def test_run_blocks_do_not_hide_failures(path: Path):
    workflow = load_yaml(path)
    for location, run in iter_run_blocks(workflow):
        assert not re.search(r"\beval\b", run), f"{path.name}:{location} uses eval"
        assert not re.search(r"\|\|\s*true\b", run), f"{path.name}:{location} hides a failure with || true"
        if "\n" in run.strip():  # multi-line scripts need strict mode; a one-liner fails on its own exit code
            assert "set -euo pipefail" in run, f"{path.name}:{location} must start with set -euo pipefail"


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=workflow_ids())
def test_no_hardcoded_ssh_key_paths(path: Path):
    workflow = load_yaml(path)
    for location, run in iter_run_blocks(workflow):
        assert "~/.ssh" not in run and ".ssh/id_rsa" not in run, f"{path.name}:{location} writes a hardcoded SSH key path"


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=workflow_ids())
def test_no_untrusted_expressions_inside_run_blocks(path: Path):
    """Inputs and secrets must reach scripts through env:, never by inline expression expansion."""
    workflow = load_yaml(path)
    for location, run in iter_run_blocks(workflow):
        assert "${{" not in run, f"{path.name}:{location} expands an expression inside the script body"


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=workflow_ids())
def test_action_pins(path: Path):
    workflow = load_yaml(path)
    for uses in iter_uses(workflow):
        if uses.startswith("./"):
            assert (ROOT / uses[2:]).exists() or (ROOT / uses[2:] / "action.yml").exists(), f"{uses} missing"
            continue
        ref = uses.split("@", 1)[1] if "@" in uses else ""
        assert ref not in {"", "main", "master"}, f"{path.name}: {uses} is not pinned"
        if uses.startswith("actions/"):
            assert re.match(r"^v\d+", ref) or SHA_RE.match(ref), f"{path.name}: {uses} must pin a major tag or SHA"
        else:
            assert SHA_RE.match(ref), f"{path.name}: third-party action {uses} must be pinned to a full commit SHA"


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=workflow_ids())
def test_jobs_running_ansible_use_the_composite_action(path: Path):
    workflow = load_yaml(path)
    for job_id, job in workflow_jobs(workflow).items():
        if job_runs_ansible(job):
            assert job_uses(job, "./.github/actions/setup-ansible"), f"{path.name}:{job_id} must use setup-ansible"


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=workflow_ids())
def test_jobs_with_ssh_keys_shred_them(path: Path):
    workflow = load_yaml(path)
    for job_id, job in workflow_jobs(workflow).items():
        steps = job.get("steps") or []
        needs_key = any(
            step.get("uses") == "./.github/actions/setup-ansible" and (step.get("with") or {}).get("ssh-private-key")
            for step in steps
        )
        if not needs_key:
            continue
        cleanup = [
            step for step in steps
            if "always()" in str(step.get("if", "")) and "shred" in step.get("run", "") and "RUNNER_TEMP}/ssh" in step.get("run", "")
        ]
        assert cleanup, f"{path.name}:{job_id} must shred ${{RUNNER_TEMP}}/ssh in an if: always() step"
        assert job.get("environment"), f"{path.name}:{job_id} reaches real hosts and must bind a GitHub environment"


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=workflow_ids())
def test_secret_references_go_through_export_secrets(path: Path):
    text = (WORKFLOWS_DIR / path.name).read_text(encoding="utf-8")
    direct = set(re.findall(r"secrets\.([A-Za-z0-9_]+)", text))
    if path.name == "node-platform-deploy.yml":
        # Explicit renamed mapping asserted by tests/test_node_platform_structure.py.
        assert "SSH_PRIVATE_KEY" in direct
        return
    assert direct <= {"SSH_PRIVATE_KEY"}, f"{path.name} maps secrets by hand: {sorted(direct - {'SSH_PRIVATE_KEY'})}"
    workflow = load_yaml(path)
    for job_id, job in workflow_jobs(workflow).items():
        if job.get("environment") == "NodeX":
            assert job_uses(job, "./.github/actions/export-secrets"), f"{path.name}:{job_id} must use export-secrets"
            step = next(s for s in job["steps"] if s.get("uses") == "./.github/actions/export-secrets")
            assert step["with"]["secrets-json"] == "${{ toJSON(secrets) }}"


@pytest.mark.parametrize(
    "path",
    sorted(p for p in (ROOT / ".github").rglob("*") if p.is_file() and p.suffix in {".yml", ".yaml", ".py", ".md"}),
    ids=lambda p: str(p.relative_to(ROOT)),
)
def test_github_files_are_clean_utf8(path: Path):
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), f"{path} has a UTF-8 BOM"
    assert b"\r" not in raw, f"{path} has CRLF line endings"
    assert raw.endswith(b"\n"), f"{path} lacks a trailing newline"
    text = raw.decode("utf-8")
    assert not MOJIBAKE_RE.search(text), f"{path} contains mojibake"
    if path.suffix in {".yml", ".yaml"}:
        assert "\t" not in text, f"{path} contains tabs"


# --------------------------------------------------------------------------------------------
# Workflow-specific contracts
# --------------------------------------------------------------------------------------------

def test_ansible_ci_never_touches_production():
    path = WORKFLOWS_DIR / "ansible-ci.yml"
    text = path.read_text(encoding="utf-8")
    workflow = load_yaml(path)
    assert "secrets." not in text and "environment:" not in text
    for location, run in iter_run_blocks(workflow):
        for line in run.splitlines():
            assert not ("ansible-playbook" in line and "--check" in line), f"{location}: CI must not run check mode against production"
    jobs = workflow_jobs(workflow)
    assert {"lint", "unit-tests", "inventory-drift", "syntax-check", "prepare", "integration-localhost"} <= set(jobs)
    assert jobs["lint"]["uses"] == "./.github/workflows/reusable-lint.yml"
    assert set(workflow[True]) == {"pull_request", "push", "workflow_dispatch"}
    assert jobs["integration-localhost"]["needs"] == "prepare"
    assert jobs["integration-localhost"]["if"] == "needs.prepare.outputs.integration_present == 'true'"
    runs = "\n".join(run for _, run in iter_run_blocks(workflow))
    assert "python3 tools/generate_inventory.py local --check" in runs
    assert "localhost-converge.yml" in runs and "localhost-verify.yml" in runs
    assert "changed=0" in runs
    assert "shellcheck" in runs and "py_compile" in runs and "pytest" in runs


def test_reusable_lint_gates():
    workflow = load_yaml(WORKFLOWS_DIR / "reusable-lint.yml")
    assert workflow[True] == {"workflow_call": None}
    steps = {step["name"]: step for _, step in iter_steps(workflow)}
    runs = "\n".join(step.get("run", "") for step in steps.values())
    assert "yamllint -c .yamllint.yml -f github ." in runs
    assert "ansible-lint --offline" in runs
    assert "python3 scripts/check-backup-coverage.py" in runs
    assert not any(step.get("continue-on-error") for step in steps.values()), "lint gates must be real gates"
    assert "\\xEF\\xBB\\xBF" in runs, "BOM guard missing"
    assert "0x923A" in runs, "mojibake guard must be built from code points"


def test_security_scan_gates():
    workflow = load_yaml(WORKFLOWS_DIR / "security-scan.yml")
    jobs = workflow_jobs(workflow)
    assert {"secret-scan", "dependency-audit", "repo-hygiene", "ansible-policy"} <= set(jobs)
    runs = "\n".join(run for _, run in iter_run_blocks(workflow))
    assert "--requirement requirements.txt" in runs and 'pip-audit "${args[@]}"' in runs
    assert "ignore_errors" in runs
    assert "[$FOUND" not in runs and "[ $FOUND" not in runs
    trufflehog = [uses for uses in iter_uses(workflow) if uses.startswith("trufflesecurity/trufflehog@")]
    assert trufflehog and SHA_RE.match(trufflehog[0].split("@", 1)[1])


def test_deploy_workflow_inputs_and_matrix():
    workflow = load_yaml(WORKFLOWS_DIR / "deploy.yml")
    inputs = workflow[True]["workflow_dispatch"]["inputs"]
    assert {"playbook", "target_group", "limit_hosts", "tags", "dry_run", "verbosity", "confirm"} <= set(inputs)
    assert inputs["verbosity"]["options"] == ["v", "vv", "vvv"]
    assert inputs["dry_run"]["type"] == "boolean"
    assert workflow[True]["push"]["tags"] == ["v*"]
    assert "pull_request" not in workflow[True], "PR validation lives in ansible-ci.yml"
    jobs = workflow_jobs(workflow)
    for job_id in ("deploy-manual", "deploy-tag", "health-check-tag"):
        assert jobs[job_id]["environment"] == "NodeX"
    matrix = jobs["deploy-tag"]["strategy"]
    assert matrix["matrix"]["tag"] == SITE_TAGS
    assert matrix["max-parallel"] == 1 and matrix["fail-fast"] is False
    assert jobs["deploy-tag"]["needs"] == "lint"
    assert jobs["health-check-tag"]["needs"] == "deploy-tag"
    runs = "\n".join(run for _, run in iter_run_blocks(workflow))
    assert 'confirm=deploy' in runs
    assert 'args+=(--check --diff)' in runs
    assert "playbooks/maintenance/health-check.yml" in runs
    assert 'ansible-playbook "${args[@]}"' in runs
    assert "GITHUB_STEP_SUMMARY" not in runs, "summaries go through the job-summary action"
    assert all(job_uses(job, "./.github/actions/job-summary") for job_id, job in jobs.items() if "steps" in job)


def test_lifecycle_workflow_contract():
    workflow = load_yaml(WORKFLOWS_DIR / "lifecycle.yml")
    inputs = workflow[True]["workflow_dispatch"]["inputs"]
    assert set(inputs["role"]["options"]) == SERVICE_ROLES
    assert inputs["action"]["options"] == ["status", "deploy", "rollback", "cleanup"]
    job = workflow_jobs(workflow)["lifecycle"]
    assert job["environment"] == "NodeX"
    run = next(step["run"] for step in job["steps"] if step["name"] == "Execute lifecycle action")
    assert run.count("ansible-playbook ") == 1, "site.yml / lifecycle.yml must be invoked exactly once"
    assert 'v2board) site_tags="postgresql,v2board"' in run
    assert "postgresql|v2bx|speedtest" in run
    assert "lifecycle_target_role=" in run and "lifecycle_version=" in run and "cleanup_confirm=yes" in run
    assert job_uses(job, "./.github/actions/job-summary")


def test_weekly_security_patch_contract():
    workflow = load_yaml(WORKFLOWS_DIR / "weekly-security-patch.yml")
    inputs = workflow[True]["workflow_dispatch"]["inputs"]
    assert inputs["apply_updates"]["type"] == "boolean" and inputs["apply_updates"]["default"] is True
    job = workflow_jobs(workflow)["security-patch"]
    steps = {step["name"]: step for step in job["steps"]}
    assert "security_patch_apply_updates=${APPLY_UPDATES}" in steps["Run security patch playbook"]["run"]
    assert steps["Create or update security patch issue"]["if"] == "always()"
    assert job["env"]["APPLY_UPDATES"] == "${{ github.event.inputs.apply_updates || 'true' }}"
    assert job["env"]["TARGET_GROUP"] == "${{ github.event.inputs.target_group || 'all' }}"


def test_node_platform_workflow_keeps_dedicated_inventory():
    workflow = load_yaml(WORKFLOWS_DIR / "node-platform-deploy.yml")
    job = workflow_jobs(workflow)["deploy"]
    assert job["environment"] == "node-platform"
    assert job["env"]["INVENTORY_PATH"] == "inventories/production/node-platform.actions.yml"
    setup = next(step for step in job["steps"] if step.get("uses") == "./.github/actions/setup-ansible")
    assert setup["with"]["generate-inventory"] == "false"
    runs = "\n".join(step.get("run", "") for step in job["steps"])
    assert 'ansible_ssh_private_key_file=${SSH_KEY_PATH}' in runs


# --------------------------------------------------------------------------------------------
# Composite actions
# --------------------------------------------------------------------------------------------

def test_setup_ansible_action_contract():
    action = load_yaml(ACTIONS_DIR / "setup-ansible" / "action.yml")
    assert set(action["inputs"]) == {"python-version", "ssh-private-key", "generate-inventory", "inventory-mode", "install-collections"}
    assert set(action["outputs"]) == {"inventory-path", "ssh-key-path"}
    text = (ACTIONS_DIR / "setup-ansible" / "action.yml").read_text(encoding="utf-8")
    for exported in ("ANSIBLE_INVENTORY=", "ANSIBLE_PRIVATE_KEY_FILE=", "SSH_KEY_PATH=", "ANSIBLE_HOST_KEY_CHECKING=False", "ANSIBLE_FORCE_COLOR=True"):
        assert exported in text
    assert '${RUNNER_TEMP}/ssh' in text
    for step in iter_action_steps(action):
        if "run" in step:
            assert step["shell"] == "bash" and "set -euo pipefail" in step["run"]
            assert "~/.ssh" not in step["run"] and "id_rsa" not in step["run"]


def test_export_secrets_action_contract():
    action = load_yaml(ACTIONS_DIR / "export-secrets" / "action.yml")
    assert action["inputs"]["secrets-json"]["required"] is True
    pattern = action["inputs"]["allow-pattern"]["default"].strip()
    regex = re.compile(pattern)
    for allowed in ("JP_1_V4_SSH", "ANSIBLE_USER", "ANSIBLE_PORT", "V2BOARD_PG_PASSWORD", "V2BX_API_HOST",
                    "PROMETHEUS_URL", "LOKI_URL", "GRAFANA_ADMIN_PASSWORD", "OBSERVABILITY_SSL_ENABLED",
                    "SSL_CERTIFICATE_PEM", "ACME_EMAIL", "CLOUDFLARE_MESH_TOKEN", "FIREWALL_WHITELIST_IPS",
                    "GLOBAL_WHITELIST_IPS", "NOTIFICATION_WEBHOOK_URL", "SLACK_WEBHOOK_URL",
                    "ANIXOPS_NODE_PLATFORM_API_SECRET", "SMTP_HOST", "VULTR_API_KEY"):
        assert regex.search(allowed), allowed
    for denied in ("github_token", "GITHUB_TOKEN", "SSH_PRIVATE_KEY", "AWS_SECRET_ACCESS_KEY", "DOCKER_PASSWORD",
                   "OLD_V4_SSH_BACKUP", "MY_ANSIBLE_USER", "PROMETHEUS_URL_OLD"):
        assert not regex.search(denied), denied
    run = next(step["run"] for step in iter_action_steps(action) if "run" in step)
    assert 'python3 "${GITHUB_ACTION_PATH}/export_secrets.py"' in run
    assert "${{ toJSON(secrets) }}" not in run and "echo" not in run, "the action must never print values"


def test_export_secrets_script_filters_and_writes_heredocs(capsys):
    module = load_export_secrets_module()
    action = load_yaml(ACTIONS_DIR / "export-secrets" / "action.yml")
    pattern = action["inputs"]["allow-pattern"]["default"].strip()
    secrets = {
        "github_token": "ghs_should_never_leak",
        "SSH_PRIVATE_KEY": "-----BEGIN KEY-----\nabc\n-----END KEY-----",
        "JP_1_V4_SSH": "203.0.113.10",
        "ANSIBLE_USER": "root",
        "V2BOARD_PG_PASSWORD": "",
        "SSL_CERTIFICATE_PEM": "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n",
        "Bad Name_V4_SSH": "x",
    }
    selected = module.select_secrets(secrets, pattern)
    assert list(selected) == ["ANSIBLE_USER", "JP_1_V4_SSH", "SSL_CERTIFICATE_PEM"]

    handle = io.StringIO()
    written = module.write_github_env(selected, handle)
    rendered = handle.getvalue()
    assert written == ["ANSIBLE_USER", "JP_1_V4_SSH", "SSL_CERTIFICATE_PEM"]
    blocks = re.findall(r"^([A-Z0-9_]+)<<(\S+)\n(.*?)\n\2\n", rendered, flags=re.S | re.M)
    assert [(name, value) for name, _, value in blocks] == [
        ("ANSIBLE_USER", "root"),
        ("JP_1_V4_SSH", "203.0.113.10"),
        ("SSL_CERTIFICATE_PEM", "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n"),
    ]
    assert len({delimiter for _, delimiter, _ in blocks}) == 3, "every block uses a fresh delimiter"

    print(module.summarise(written, len(secrets)))
    out = capsys.readouterr().out
    assert "JP_1_V4_SSH" in out
    for value in ("203.0.113.10", "ghs_should_never_leak", "MIIB"):
        assert value not in out, "values must never be printed"


def test_export_secrets_main_requires_github_env(monkeypatch, tmp_path, capsys):
    module = load_export_secrets_module()
    env_file = tmp_path / "github_env"
    out_file = tmp_path / "github_output"
    monkeypatch.setenv("SECRETS_JSON", '{"JP_1_V4_SSH": "203.0.113.10", "DOCKER_PASSWORD": "nope", "github_token": "t"}')
    monkeypatch.setenv("ALLOW_PATTERN", r"^[A-Z0-9_]+_V4_SSH$")
    monkeypatch.setenv("GITHUB_ENV", str(env_file))
    monkeypatch.setenv("GITHUB_OUTPUT", str(out_file))
    assert module.main() == 0
    env_text = env_file.read_text(encoding="utf-8")
    assert env_text.startswith("JP_1_V4_SSH<<") and "203.0.113.10" in env_text
    assert "DOCKER_PASSWORD" not in env_text and "github_token" not in env_text
    assert "exported-names=JP_1_V4_SSH" in out_file.read_text(encoding="utf-8")
    assert "203.0.113.10" not in capsys.readouterr().out

    monkeypatch.delenv("GITHUB_ENV")
    assert module.main() == 1
    monkeypatch.setenv("GITHUB_ENV", str(env_file))
    monkeypatch.setenv("SECRETS_JSON", "not json")
    assert module.main() == 1


def test_job_summary_action_contract():
    action = load_yaml(ACTIONS_DIR / "job-summary" / "action.yml")
    assert set(action["inputs"]) == {"title", "status", "fields"}
    run = next(step["run"] for step in iter_action_steps(action) if "run" in step)
    assert "GITHUB_STEP_SUMMARY" in run and "set -euo pipefail" in run
    assert "${{" not in run


# --------------------------------------------------------------------------------------------
# Dependabot
# --------------------------------------------------------------------------------------------

def test_dependabot_covers_actions_and_pip():
    config = load_yaml(ROOT / ".github" / "dependabot.yml")
    assert config["version"] == 2
    by_ecosystem = {entry["package-ecosystem"]: entry for entry in config["updates"]}
    assert set(by_ecosystem) == {"github-actions", "pip"}
    for entry in by_ecosystem.values():
        assert entry["schedule"]["interval"] == "weekly"
    assert "/.github/actions/*" in by_ecosystem["github-actions"]["directories"]
