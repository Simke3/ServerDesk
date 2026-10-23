"""Local user / group inspection and basic account actions."""
from __future__ import annotations

import re

from .executor import Executor, Result

_USER_RE = re.compile(r"^[a-z_][a-z0-9_.\-]{0,31}\$?$")


def list_users(ex: Executor, include_system: bool = False) -> list[dict]:
    res = ex.run(["getent", "passwd"], timeout=15)
    locked_out = ex.run("passwd -S -a 2>/dev/null", timeout=15, sudo=True)
    state = {}
    for ln in locked_out.out.splitlines():
        p = ln.split()
        if len(p) >= 2:
            state[p[0]] = p[1]
    rows = []
    for ln in res.out.splitlines():
        p = ln.split(":")
        if len(p) < 7:
            continue
        uid = int(p[2]) if p[2].isdigit() else -1
        is_human = 1000 <= uid < 60000
        if not include_system and not is_human and uid != 0:
            continue
        rows.append({"user": p[0], "uid": uid, "gid": p[3], "name": p[4].split(",")[0], "home": p[5],
                     "shell": p[6], "locked": state.get(p[0], "") in ("L", "LK"),
                     "login": not p[6].endswith(("nologin", "false"))})
    return sorted(rows, key=lambda r: r["uid"])


def list_groups(ex: Executor) -> list[dict]:
    res = ex.run(["getent", "group"], timeout=15)
    rows = []
    for ln in res.out.splitlines():
        p = ln.split(":")
        if len(p) >= 4 and p[2].isdigit() and (int(p[2]) >= 1000 or p[0] in ("sudo", "wheel", "docker", "adm")):
            rows.append({"group": p[0], "gid": int(p[2]), "members": p[3].replace(",", ", ")})
    return rows


def logins(ex: Executor) -> str:
    return ex.run("last -n 40 -w 2>/dev/null || last -n 40", timeout=15).out


def sessions(ex: Executor) -> str:
    return ex.run("who -u 2>/dev/null", timeout=10).out


def failed_logins(ex: Executor) -> str:
    return ex.run("lastb -n 30 -w 2>/dev/null", timeout=15, sudo=True).text


def lock(ex: Executor, user: str, lock_it: bool) -> Result:
    if not _USER_RE.match(user) or user == "root":
        return Result(2, "", "Refusing: invalid user or root")
    return ex.run_audited("user.lock" if lock_it else "user.unlock",
                          ["usermod", "-L" if lock_it else "-U", user], sudo=True)


def add_to_group(ex: Executor, user: str, group: str) -> Result:
    if not _USER_RE.match(user) or not _USER_RE.match(group):
        return Result(2, "", "Invalid name")
    return ex.run_audited("user.group_add", ["usermod", "-aG", group, user], sudo=True)
