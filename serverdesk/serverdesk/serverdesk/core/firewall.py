"""Firewall status (ufw, firewalld, nftables) with basic ufw rule control."""
from __future__ import annotations

import re

from .executor import Executor, Result


def detect(ex: Executor) -> str:
    for tool in ("ufw", "firewall-cmd", "nft", "iptables"):
        if ex.has(tool):
            return tool
    return ""


def status(ex: Executor, tool: str) -> str:
    cmds = {
        "ufw": "ufw status numbered verbose",
        "firewall-cmd": "firewall-cmd --list-all-zones | head -n 200",
        "nft": "nft list ruleset",
        "iptables": "iptables -S",
    }
    if tool not in cmds:
        return "No supported firewall tool detected."
    res = ex.run(cmds[tool], timeout=20, sudo=True)
    return res.out if res.ok else (res.err or "Permission denied or tool inactive")


_RULE_RE = re.compile(r"^[0-9]{1,5}(/(tcp|udp))?$")
_FROM_RE = re.compile(r"^(any|[0-9a-fA-F:.]+(/[0-9]{1,3})?)$")


def ufw_rule(ex: Executor, action: str, port: str, source: str = "any") -> Result:
    if action not in ("allow", "deny", "reject", "limit") or not _RULE_RE.match(port) or not _FROM_RE.match(source):
        return Result(2, "", "Invalid rule")
    cmd = ["ufw", action] if source == "any" else ["ufw", action, "from", source, "to", "any", "port"]
    cmd += [port] if source == "any" else [port.split("/")[0]] + (["proto", port.split("/")[1]] if "/" in port else [])
    return ex.run_audited("firewall.ufw_" + action, cmd, sudo=True)


def ufw_delete(ex: Executor, number: int) -> Result:
    return ex.run_audited("firewall.ufw_delete", f"yes | ufw delete {int(number)}", sudo=True)


def ufw_enable(ex: Executor, enable: bool) -> Result:
    return ex.run_audited("firewall.ufw_enable" if enable else "firewall.ufw_disable",
                          "yes | ufw enable" if enable else "ufw disable", sudo=True)
