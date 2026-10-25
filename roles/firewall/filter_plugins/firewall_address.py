"""Jinja2 filters of the firewall role | 防火墙角色的 Jinja2 过滤器."""

from __future__ import annotations

import ipaddress
import socket

from ansible.errors import AnsibleFilterError


def firewall_ufw_address(value):
    """Return a whitelist entry in the form ufw stores and prints it.

    Mirrors ufw's UFWRule.set_src() and util.normalize_address(): lower-case,
    drop a /32 (IPv4) or /128 (IPv6) host prefix, round-trip the address
    through inet_pton/inet_ntop (IPv6 compression) and, for IPv4 only, reduce
    a CIDR to its network address. IPv6 prefixes keep their host bits, as in
    ufw. "ufw show added" prints this form, so the prune step compares like
    with like: 1.2.3.4/32 -> 1.2.3.4, 10.0.0.5/24 -> 10.0.0.0/24,
    2001:DB8:0::1/128 -> 2001:db8::1, 2001:db8::1/64 stays 2001:db8::1/64.
    """
    text = str(value).strip().lower()
    address, slash, prefix = text.partition("/")
    is_v6 = ":" in address
    family = socket.AF_INET6 if is_v6 else socket.AF_INET
    if slash and prefix == ("128" if is_v6 else "32"):
        slash = prefix = ""
    try:
        address = socket.inet_ntop(family, socket.inet_pton(family, address))
        if slash and not is_v6:
            address = str(ipaddress.IPv4Network(f"{address}/{prefix}", strict=False).network_address)
    except (OSError, ValueError) as exc:
        raise AnsibleFilterError(
            f"firewall_ufw_address: {value!r} is not a valid IPv4/IPv6 address or CIDR ({exc})"
        ) from exc
    return address + slash + prefix


class FilterModule:
    """Register the firewall role filters."""

    def filters(self):
        return {"firewall_ufw_address": firewall_ufw_address}
