#!/usr/bin/env python3
"""Tests for scripts/check-backup-coverage.py (the backup coverage gate)."""

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check-backup-coverage.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_backup_coverage", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cbc = _load_module()


# --- fixtures -----------------------------------------------------------------
def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return path


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A minimal repository layout: roles/ and playbooks/ under tmp_path."""
    (tmp_path / "roles").mkdir()
    (tmp_path / "playbooks").mkdir()
    (tmp_path / "scripts").mkdir()
    return tmp_path


def run_scan(repo: Path, allowlist=()):
    cbc._ROLE_VARS_CACHE.clear()
    return cbc.scan(repo, repo / "roles", [repo / "playbooks"], allowlist)


# --- role task files ----------------------------------------------------------
def test_template_under_etc_without_backup_is_reported(repo):
    write(
        repo / "roles/nginx/tasks/main.yml",
        """
        ---
        - name: Install nginx
          ansible.builtin.apt:
            name: nginx

        - name: Deploy nginx.conf
          ansible.builtin.template:
            src: nginx.conf.j2
            dest: /etc/nginx/nginx.conf
            mode: "0644"
        """,
    )
    report = run_scan(repo)
    assert not report.ok
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.path == "roles/nginx/tasks/main.yml"
    assert finding.task == "Deploy nginx.conf"
    assert finding.dest == "/etc/nginx/nginx.conf"
    assert finding.kind == cbc.KIND_MISSING
    assert finding.line == 6
    assert report.tasks_checked == 1
    assert report.files_scanned == 1


def test_backup_true_and_non_etc_destinations_pass(repo):
    write(
        repo / "roles/node_exporter/tasks/main.yml",
        """
        - name: Deploy unit file
          ansible.builtin.template:
            src: node_exporter.service.j2
            dest: /etc/systemd/system/node_exporter.service
            backup: true

        - name: Install binary
          ansible.builtin.copy:
            src: /tmp/node_exporter
            dest: /usr/local/bin/node_exporter
            remote_src: true
            mode: "0755"

        - name: Legacy yes spelling is still a backup
          copy:
            src: a
            dest: /etc/a.conf
            backup: yes
        """,
    )
    report = run_scan(repo)
    assert report.ok, report.findings
    assert report.tasks_checked == 3


def test_block_rescue_always_are_walked(repo):
    write(
        repo / "roles/common/tasks/main.yml",
        """
        - name: Configure
          block:
            - name: In block
              ansible.builtin.template:
                src: a.j2
                dest: /etc/a.conf
          rescue:
            - name: In rescue
              ansible.builtin.copy:
                src: b
                dest: /etc/b.conf
          always:
            - name: Nested block
              block:
                - name: In always
                  template:
                    src: c.j2
                    dest: /etc/c.conf
        """,
    )
    report = run_scan(repo)
    assert sorted(f.task for f in report.findings) == ["In always", "In block", "In rescue"]


def test_free_form_string_args_and_task_level_args_block(repo):
    write(
        repo / "roles/x/tasks/main.yml",
        """
        - name: Free form without backup
          template: src=a.j2 dest=/etc/a.conf mode=0644

        - name: Free form with backup
          template: src=a.j2 dest=/etc/b.conf backup=true

        - name: Args block carries backup
          ansible.builtin.copy:
            src: c
            dest: /etc/c.conf
          args:
            backup: true
        """,
    )
    report = run_scan(repo)
    assert [f.task for f in report.findings] == ["Free form without backup"]


def test_explicit_backup_false_is_reported_as_disabled(repo):
    write(
        repo / "roles/x/tasks/main.yml",
        """
        - name: Disabled on purpose but undocumented
          ansible.builtin.template:
            src: a.j2
            dest: /etc/a.conf
            backup: false
        """,
    )
    report = run_scan(repo)
    assert len(report.findings) == 1
    assert report.findings[0].kind == cbc.KIND_DISABLED


def test_static_content_and_backup_copies_are_not_configuration(repo):
    write(
        repo / "roles/x/tasks/main.yml",
        """
        - name: Backup copy of sshd_config
          copy:
            src: /etc/ssh/sshd_config
            dest: /etc/ssh/sshd_config.backup.{{ ansible_date_time.epoch }}
            remote_src: true

        - name: Static page
          template:
            src: index.html.j2
            dest: /etc/nginx/html/index.html

        - name: Binary
          copy:
            src: x
            dest: /usr/local/bin/x
        """,
    )
    report = run_scan(repo)
    assert report.ok, report.findings


def test_restore_from_backup_is_the_rollback_and_not_gated(repo):
    write(
        repo / "roles/nginx/tasks/main.yml",
        """
        - name: Roll out nginx.conf
          block:
            - name: Deploy nginx.conf
              ansible.builtin.template:
                src: nginx.conf.j2
                dest: /etc/nginx/nginx.conf
                backup: true
              register: nginx_conf_result
          rescue:
            - name: Restore the previous nginx.conf
              ansible.builtin.copy:
                src: "{{ nginx_conf_result.backup_file }}"
                dest: /etc/nginx/nginx.conf
                remote_src: true
              when: nginx_conf_result.backup_file is defined
            - name: Restore from a timestamped backup path
              ansible.builtin.copy:
                src: /etc/nginx/nginx.conf.backup.20260424_120000
                dest: /etc/nginx/nginx.conf
                remote_src: true
            - name: Not a restore (controller side source)
              ansible.builtin.copy:
                src: files/nginx.conf
                dest: /etc/nginx/nginx.conf
        """,
    )
    report = run_scan(repo)
    assert [f.task for f in report.findings] == ["Not a restore (controller side source)"]
    assert report.tasks_checked == 4


def test_jinja_prefix_is_resolved_from_role_defaults(repo):
    write(
        repo / "roles/v2board/defaults/main.yml",
        """
        v2board_base_dir: /etc
        v2board_config_dir: "{{ v2board_base_dir }}/v2board"
        """,
    )
    write(
        repo / "roles/v2board/tasks/configure.yml",
        """
        - name: Render config
          ansible.builtin.template:
            src: config.yaml.j2
            dest: "{{ v2board_config_dir }}/config.yaml"
        """,
    )
    report = run_scan(repo)
    assert len(report.findings) == 1
    assert report.findings[0].dest == "/etc/v2board/config.yaml"


def test_unresolvable_jinja_dest_is_skipped(repo):
    write(
        repo / "roles/x/tasks/main.yml",
        """
        - name: Unknown destination
          ansible.builtin.template:
            src: a.j2
            dest: "{{ somewhere_else }}/a.conf"
        """,
    )
    assert run_scan(repo).ok


def test_only_tasks_and_handlers_directories_of_roles_are_scanned(repo):
    write(
        repo / "roles/x/defaults/main.yml",
        """
        x_example:
          - name: Not a task
            template:
              dest: /etc/not-a-task.conf
        """,
    )
    write(
        repo / "roles/x/handlers/main.yml",
        """
        - name: Handler writing config
          ansible.builtin.copy:
            src: a
            dest: /etc/handler.conf
        """,
    )
    report = run_scan(repo)
    assert [f.task for f in report.findings] == ["Handler writing config"]


def test_vault_tags_do_not_break_parsing(repo):
    write(
        repo / "roles/x/tasks/main.yml",
        """
        - name: Secret aware
          ansible.builtin.template:
            src: a.j2
            dest: /etc/a.conf
            backup: true
          vars:
            secret: !vault |
              $ANSIBLE_VAULT;1.1;AES256
              6162
        """,
    )
    assert run_scan(repo).ok


# --- playbooks ----------------------------------------------------------------
def test_playbook_sections_are_scanned(repo):
    write(
        repo / "playbooks/maintenance/fix.yml",
        """
        ---
        - name: Fix things
          hosts: all
          become: true
          pre_tasks:
            - name: Pre task
              ansible.builtin.copy:
                content: "x"
                dest: /etc/apt/sources.list.d/docker.sources
          tasks:
            - name: Task
              ansible.builtin.template:
                src: a.j2
                dest: /etc/a.conf
                backup: true
          post_tasks:
            - name: Post task
              ansible.builtin.copy:
                src: b
                dest: /etc/b.conf
          handlers:
            - name: Handler
              ansible.builtin.copy:
                src: c
                dest: /etc/c.conf

        - name: Imported
          import_playbook: other.yml
        """,
    )
    write(
        repo / "playbooks/maintenance/security-patch/tasks.yml",
        """
        - name: Task file inside playbooks
          ansible.builtin.copy:
            src: d
            dest: /etc/d.conf
        """,
    )
    report = run_scan(repo)
    assert sorted(f.task for f in report.findings) == [
        "Handler",
        "Post task",
        "Pre task",
        "Task file inside playbooks",
    ]
    assert report.tasks_checked == 5


# --- allowlist ----------------------------------------------------------------
def test_allowlist_suppresses_findings_and_reports_unused_entries(repo):
    write(
        repo / "roles/x/tasks/main.yml",
        """
        - name: Documented exception
          ansible.builtin.copy:
            src: a
            dest: /etc/a.conf
            backup: false
        """,
    )
    allowlist_file = write(
        repo / "scripts/backup-coverage-allowlist.txt",
        """
        # reason: restored from a backup by design
        roles/x/tasks/main.yml:Documented exception
        roles/gone/tasks/*.yml:Does not exist anymore
        """,
    )
    entries = cbc.load_allowlist(allowlist_file)
    assert len(entries) == 2
    report = run_scan(repo, entries)
    assert report.ok
    assert [f.task for f in report.allowlisted] == ["Documented exception"]
    assert [e.task_pattern for e in report.unused_allowlist] == ["Does not exist anymore"]


def test_allowlist_rejects_malformed_lines(tmp_path):
    bad = write(tmp_path / "allow.txt", "roles/x/tasks/main.yml\n")
    with pytest.raises(ValueError):
        cbc.load_allowlist(bad)


def test_yaml_parse_error_is_a_finding_and_cannot_be_allowlisted(repo):
    write(repo / "roles/x/tasks/main.yml", "- name: broken\n  copy: [\n")
    entries = [cbc.AllowlistEntry("roles/x/tasks/main.yml", "*", 1)]
    report = run_scan(repo, entries)
    assert len(report.findings) == 1
    assert report.findings[0].kind == cbc.KIND_YAML


# --- CLI ----------------------------------------------------------------------
def test_cli_exit_codes_and_formats(repo, capsys):
    write(
        repo / "roles/x/tasks/main.yml",
        """
        - name: Missing
          ansible.builtin.template:
            src: a.j2
            dest: /etc/a.conf
        """,
    )
    rc = cbc.main(["--root", str(repo)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "roles/x/tasks/main.yml" in out
    assert "[missing-backup] Missing" in out
    assert "FAIL" in out

    rc = cbc.main(["--root", str(repo), "--format", "github"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "::error file=roles/x/tasks/main.yml,line=1,title=Missing backup::Missing:" in out

    write(repo / "roles/x/tasks/main.yml", "- name: Nothing\n  ansible.builtin.debug:\n    msg: hi\n")
    rc = cbc.main(["--root", str(repo)])
    assert rc == 0
    assert "OK:" in capsys.readouterr().out


def test_cli_explicit_dirs_and_allowlist(repo, capsys):
    write(
        repo / "custom-roles/x/tasks/main.yml",
        """
        - name: Exempted
          ansible.builtin.copy:
            src: a
            dest: /etc/a.conf
        """,
    )
    write(repo / "custom-playbooks/site.yml", "- hosts: all\n  tasks: []\n")
    allow = write(repo / "allow.txt", "custom-roles/x/tasks/main.yml:Exempted\n")
    rc = cbc.main(
        [
            "--root",
            str(repo),
            "--roles-dir",
            str(repo / "custom-roles"),
            "--playbooks-dir",
            str(repo / "custom-playbooks"),
            "--allowlist",
            str(allow),
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "allowlisted   : 1" in out


def test_cli_usage_error_when_no_directories_exist(tmp_path):
    assert cbc.main(["--root", str(tmp_path / "nope")]) == 2


def test_repository_allowlist_is_well_formed():
    """The real allowlist must always parse (it is loaded by CI)."""
    entries = cbc.load_allowlist(cbc.DEFAULT_ALLOWLIST)
    for entry in entries:
        assert entry.path_pattern and entry.task_pattern
