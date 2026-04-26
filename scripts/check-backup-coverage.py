#!/usr/bin/env python3
"""
Backup Coverage Checker | 备份覆盖率检查

Scans all Ansible roles for template/copy tasks that deploy configuration files
but are missing 'backup: yes'. Reports missing backup coverage.

Usage:
    python3 scripts/check-backup-coverage.py
    python3 scripts/check-backup-coverage.py --roles-dir roles/

Exit codes:
    0 - All configuration templates have backup coverage
    1 - Missing backup coverage found (non-blocking warning)
"""

import os
import re
import sys
import argparse
from pathlib import Path


# Patterns that identify configuration file deployment tasks
CONFIG_PATTERNS = re.compile(
    r'(template|copy):',
    re.IGNORECASE
)

# Patterns that identify non-config tasks (should NOT have backup)
NON_CONFIG_PATTERNS = re.compile(
    r'(systemd|service|Unit|Description|ExecStart|After|WantedBy|'
    r'\.service|\.socket|\.timer)',
    re.IGNORECASE
)

# Extensions that indicate a template file deploys a config
CONFIG_EXTENSIONS = re.compile(
    r'\.(yml|yaml|conf|cfg|ini|cnf|config|j2|json|xml|toml)$',
    re.IGNORECASE
)

# Content file extensions that don't need backup
CONTENT_EXTENSIONS = re.compile(
    r'\.(html|htm|css|js|png|jpg|gif|svg|ico|woff|woff2|ttf|eot)$',
    re.IGNORECASE
)

# Files/directories to skip
SKIP_DIRS = {'.git', '.tox', '__pycache__', 'venv', 'node_modules'}
SKIP_FILES = {'check-backup-coverage.py'}


def find_yaml_files(roles_dir):
    """Find all YAML task files in roles directory."""
    yaml_files = []
    roles_path = Path(roles_dir)
    if not roles_path.exists():
        print(f"Roles directory not found: {roles_dir}")
        return yaml_files

    for root, dirs, files in os.walk(roles_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(('.yml', '.yaml')) and f not in SKIP_FILES:
                yaml_files.append(Path(root) / f)
    return sorted(yaml_files)


def parse_tasks(filepath):
    """
    Simple YAML task parser for backup detection.
    Looks for template/copy blocks and checks for backup: yes nearby.
    """
    issues = []
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        print(f"  Warning: Cannot read {filepath}: {e}")
        return issues

    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for template or copy task
        if re.match(r'\s+(ansible\.builtin\.)?(template|copy):\s*$', line) or \
           re.match(r'\s+(ansible\.builtin\.)?(template|copy):\s*src=', line):
            task_start = i
            task_lines = [line]

            # Collect the task block (until next top-level key or task)
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                # Stop at next task (same or lesser indentation, ending with colon)
                if next_line.strip() == '':
                    j += 1
                    continue
                # Check if this is a new top-level task item
                stripped = next_line.lstrip()
                indent = len(next_line) - len(stripped)
                if indent <= 2 and stripped.endswith(':') and not stripped.startswith('#'):
                    break
                if stripped.startswith('- name:') and indent <= 4:
                    break
                task_lines.append(next_line)
                j += 1

            task_text = '\n'.join(task_lines)

            # Skip tasks that only create files if they don't exist (stat.exists guard)
            if re.search(r'when:.*not\s+\S+\.stat\.exists', task_text):
                i = j
                continue

            # Determine if this is a config file deployment
            is_config = False

            # Check for src template with config-like extensions
            src_match = re.search(r'src:\s*\S+\.j2', task_text)
            if src_match:
                is_config = True

            # Check dest for config file paths
            dest_match = re.search(r'dest:\s*(/\S+)', task_text)
            if dest_match:
                dest_path = dest_match.group(1)
                # Skip content files (HTML, images, etc.)
                if CONTENT_EXTENSIONS.search(dest_path):
                    i = j
                    continue
                if CONFIG_EXTENSIONS.search(dest_path):
                    is_config = True
                # Also catch systemd service files
                if '.service' in dest_path:
                    is_config = True

            if is_config:
                # Check for backup: yes
                has_backup = re.search(r'backup:\s*yes', task_text)
                # Also check for backup: no (explicit opt-out)
                has_backup_no = re.search(r'backup:\s*no', task_text)

                if not has_backup and not has_backup_no:
                    # Find the task name for better reporting
                    task_name = "unnamed"
                    for tl in task_lines:
                        name_match = re.search(r'- name:\s*(.+)', tl)
                        if name_match:
                            task_name = name_match.group(1).strip()
                            break

                    # Find dest path for reporting
                    dest_path = "unknown"
                    if dest_match:
                        dest_path = dest_match.group(1)

                    issues.append({
                        'file': str(filepath),
                        'line': task_start + 1,
                        'task': task_name,
                        'dest': dest_path,
                    })

            i = j
        else:
            i += 1

    return issues


def main():
    parser = argparse.ArgumentParser(
        description='Check Ansible roles for missing backup: yes in template/copy tasks'
    )
    parser.add_argument(
        '--roles-dir',
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'roles'),
        help='Path to Ansible roles directory (default: ../roles)'
    )
    args = parser.parse_args()

    roles_dir = args.roles_dir
    all_issues = []
    files_scanned = 0

    yaml_files = find_yaml_files(roles_dir)

    for yaml_file in yaml_files:
        files_scanned += 1
        issues = parse_tasks(yaml_file)
        all_issues.extend(issues)

    # Print report
    print("=" * 60)
    print("Backup Coverage Report | 备份覆盖率报告")
    print("=" * 60)
    print(f"Files scanned: {files_scanned}")
    print(f"Issues found:  {len(all_issues)}")
    print("=" * 60)

    if all_issues:
        print("\nMissing backup: yes | 缺少备份配置:")
        print("-" * 60)
        for issue in all_issues:
            rel_path = os.path.relpath(issue['file'])
            print(f"  {rel_path}:{issue['line']}")
            print(f"    Task: {issue['task']}")
            print(f"    Dest: {issue['dest']}")
            print()
        print("=" * 60)
        print("WARNING: Some configuration templates lack backup: yes")
        print("Deployments to these roles will overwrite configs without backup.")
        print("=" * 60)
        return 1
    else:
        print("\nAll configuration templates have backup coverage.")
        return 0


if __name__ == '__main__':
    sys.exit(main())
