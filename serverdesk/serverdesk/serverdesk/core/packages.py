"""Package manager awareness: pending updates for apt, dnf/yum and pacman."""
from __future__ import annotations

from .executor import Executor, Result


def detect(ex: Executor) -> str:
    for tool in ("apt", "dnf", "yum", "pacman", "zypper"):
        if ex.has(tool):
            return tool
    return ""


def pending_updates(ex: Executor, tool: str) -> list[str]:
    cmds = {
        "apt": "apt list --upgradable 2>/dev/null | tail -n +2",
        "dnf": "dnf -q check-update 2>/dev/null | grep -E '^[A-Za-z0-9]' | grep -v '^Obsoleting'",
        "yum": "yum -q check-update 2>/dev/null | grep -E '^[A-Za-z0-9]'",
        "pacman": "(checkupdates 2>/dev/null || pacman -Qu 2>/dev/null)",
        "zypper": "zypper -q lu 2>/dev/null | tail -n +4",
    }
    if tool not in cmds:
        return []
    res = ex.run(cmds[tool], timeout=120)
    return [ln for ln in res.out.splitlines() if ln.strip()]


def refresh_index(ex: Executor, tool: str) -> Result:
    cmds = {"apt": "apt-get update", "dnf": "dnf -q makecache", "yum": "yum -q makecache",
            "pacman": "pacman -Sy", "zypper": "zypper refresh"}
    return ex.run_audited("packages.refresh", cmds.get(tool, "true"), sudo=True, timeout=300)


def upgrade_all(ex: Executor, tool: str) -> Result:
    cmds = {"apt": "DEBIAN_FRONTEND=noninteractive apt-get -y upgrade", "dnf": "dnf -y upgrade",
            "yum": "yum -y update", "pacman": "pacman -Syu --noconfirm", "zypper": "zypper -n update"}
    return ex.run_audited("packages.upgrade_all", cmds.get(tool, "true"), sudo=True, timeout=1800)
