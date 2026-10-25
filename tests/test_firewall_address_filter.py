#!/usr/bin/env python3
"""Unit tests for roles/firewall/filter_plugins/firewall_address.py (ufw address canonicalisation)."""

import importlib.util
import sys
from pathlib import Path

import pytest
from ansible.errors import AnsibleFilterError

sys.dont_write_bytecode = True
_PATH = Path(__file__).resolve().parent.parent / "roles" / "firewall" / "filter_plugins" / "firewall_address.py"
_SPEC = importlib.util.spec_from_file_location("firewall_address", _PATH)
firewall_address = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(firewall_address)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.2.3.4/32", "1.2.3.4"),
        ("10.0.0.5/24", "10.0.0.0/24"),
        ("203.0.113.10", "203.0.113.10"),
        (" 198.51.100.9 ", "198.51.100.9"),
        ("2001:DB8:0:0::1/128", "2001:db8::1"),
        ("2001:db8::5/64", "2001:db8::5/64"),
        ("::ffff:1.2.3.4", "::ffff:1.2.3.4"),
    ],
)
def test_firewall_ufw_address_matches_ufw_storage_form(raw, expected):
    assert firewall_address.firewall_ufw_address(raw) == expected


@pytest.mark.parametrize("raw", ["010.0.0.1", "not-an-ip", "1.2.3.4/33"])
def test_firewall_ufw_address_rejects_invalid_entries(raw):
    with pytest.raises(AnsibleFilterError):
        firewall_address.firewall_ufw_address(raw)


def test_filter_is_registered():
    assert "firewall_ufw_address" in firewall_address.FilterModule().filters()
