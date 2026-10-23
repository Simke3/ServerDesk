"""systemd service management."""
from __future__ import annotations

import re

from .executor import Executor, Result

_UNIT_RE = re.compile(r"^[A-Za-z0-9:_.@\\-]+$")
ACTIONS = {"start", "stop", "restart", "reload", "enable", "disable", "mask", "unmask"}


def valid_unit(name: str) -> bool:
    return bool(_UNIT_RE.match(name)) and len(name) < 256


def list_services(ex: Executor) -> list[dict]:
    res = ex.run(["systemctl", "list-units", "--type=service", "--all", "--no-legend",
                  "--no-pager", "--plain"], timeout=25)
    if not res.ok:
        raise RuntimeError(res.err.strip() or "systemctl failed")
    files = ex.run(["systemctl", "list-unit-files", "--type=service", "--no-legend",
                    "--no-pager", "--plain"], timeout=25)
    enabled: dict[str, str] = {}
    for line in files.out.splitlines():
        p = line.split()
        if len(p) >= 2:
            enabled[p[0]] = p[1]
    rows = []
    for line in res.out.splitlines():
        p = line.split(None, 4)
        if len(p) < 4:
            continue
        unit = p[0].lstrip("●* ").strip()
        rows.append({"unit": unit, "load": p[1], "active": p[2], "sub": p[3],
                     "description": p[4] if len(p) > 4 else "",
                     "enabled": enabled.get(unit, "-")})
    return rows


def status(ex: Executor, unit: str) -> str:
    if not valid_unit(unit):
        return "Invalid unit name"
    res = ex.run(["systemctl", "status", unit, "--no-pager", "-l", "-n", "30"], timeout=15)
    return res.out or res.err


def act(ex: Executor, unit: str, action: str) -> Result:
    if action not in ACTIONS:
        return Result(2, "", f"Unsupported action: {action}")
    if not valid_unit(unit):
        return Result(2, "", "Invalid unit name")
    return ex.run_audited(f"service.{action}", ["systemctl", action, unit], sudo=True, timeout=60)


def failed_count(ex: Executor) -> int:
    res = ex.run(["systemctl", "--failed", "--no-legend", "--no-pager", "--plain"], timeout=15)
    return len([ln for ln in res.out.splitlines() if ln.strip()])
