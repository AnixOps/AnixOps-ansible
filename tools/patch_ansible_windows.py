#!/usr/bin/env python3
"""
Patch Ansible CLI to work on Windows
Fixes the os.get_blocking() issue that occurs on Windows with Python 3.12+
"""

import os
import sys
import shutil
from pathlib import Path


def find_ansible_cli_init():
    """Find the ansible CLI __init__.py file"""
    # Look for the file in the virtual environment
    venv_path = Path(__file__).parent.parent / "venv"
    
    # Try common locations
    possible_paths = [
        venv_path / "Lib" / "site-packages" / "ansible" / "cli" / "__init__.py",
        Path(sys.prefix) / "Lib" / "site-packages" / "ansible" / "cli" / "__init__.py",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None


def patch_ansible_cli(file_path):
    """Patch the check_blocking_io and initialize_locale functions to work on Windows"""
    
    # Create backup
    backup_path = file_path.with_suffix('.py.bak')
    if backup_path.exists():
        # Restore from backup for a clean patch
        shutil.copy2(backup_path, file_path)
        print(f"✓ Restored from backup: {backup_path}")
    else:
        shutil.copy2(file_path, backup_path)
        print(f"✓ Created backup: {backup_path}")
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already patched
    if 'PATCHED FOR WINDOWS' in content:
        print("✓ File is already patched")
        return True
    
    patched = False
    
    # Patch 1: Fix os.get_blocking() issue
    old_line1 = "        if not os.get_blocking(fd):"
    new_code1 = """        # PATCHED FOR WINDOWS - os.get_blocking() is not available on Windows
        try:
            is_blocking = os.get_blocking(fd)
        except (AttributeError, OSError):
            # Skip on Windows or if not supported
            continue
        
        if not is_blocking:"""
    
    if old_line1 in content:
        content = content.replace(old_line1, new_code1)
        print(f"✓ Patched os.get_blocking() issue")
        patched = True
    
    # Patch 2: Fix locale encoding check
    old_locale_code = """    try:
        locale.setlocale(locale.LC_ALL, '')
        dummy, encoding = locale.getlocale()
    except (locale.Error, ValueError) as e:"""
    
    new_locale_code = """    # PATCHED FOR WINDOWS - Force UTF-8 on Windows
    import platform
    try:
        if platform.system() == 'Windows':
            # On Windows, force UTF-8 encoding
            encoding = 'UTF-8'
        else:
            locale.setlocale(locale.LC_ALL, '')
            dummy, encoding = locale.getlocale()
    except (locale.Error, ValueError) as e:"""
    
    if old_locale_code in content:
        content = content.replace(old_locale_code, new_locale_code)
        print(f"✓ Patched locale encoding check")
        patched = True
    
    if patched:
        # Write the patched content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✓ Successfully patched: {file_path}")
        return True
    else:
        print("✗ Could not find the expected code patterns to patch")
        print("  The Ansible version may have changed")
        return False


def main():
    print("=" * 60)
    print("Ansible Windows Patch Utility")
    print("=" * 60)
    print()
    
    # Find the file
    cli_init_path = find_ansible_cli_init()
    
    if not cli_init_path:
        print("✗ Could not find ansible CLI __init__.py")
        print("  Please ensure Ansible is installed in the virtual environment")
        return 1
    
    print(f"Found Ansible CLI: {cli_init_path}")
    print()
    
    # Patch the file
    if patch_ansible_cli(cli_init_path):
        print()
        print("=" * 60)
        print("✓ Patch applied successfully!")
        print("=" * 60)
        print()
        print("You can now run Ansible commands on Windows.")
        print()
        print("To test: .\run.ps1 ping")
        print()
        return 0
    else:
        print()
        print("=" * 60)
        print("✗ Patch failed")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
