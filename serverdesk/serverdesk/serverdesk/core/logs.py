"""journald and classic log file readers."""
from __future__ import annotations

import re
import shlex

from .executor import Executor
from .services import valid_unit

PRIORITIES = {"emerg": 0, "alert": 1, "crit": 2, "err": 3, "warning": 4, "notice": 5, "info": 6, "debug": 7}
COMMON_FILES = ["/var/log/syslog", "/var/log/messages", "/var/log/auth.log", "/var/log/secure",
                "/var/log/kern.log", "/var/log/dpkg.log", "/var/log/nginx/error.log",
                "/var/log/nginx/access.log", "/var/log/apache2/error.log", "/var/log/mysql/error.log",
                "/var/log/postgresql/postgresql.log"]
_PATH_RE = re.compile(r"^/[A-Za-z0-9_./\-]+$")


def journal(ex: Executor, lines: int = 400, unit: str = "", priority: str = "", since: str = "",
            boot: bool = False) -> str:
    cmd = ["journalctl", "--no-pager", "-o", "short-iso", "-n", str(int(lines))]
    if unit:
        if not valid_unit(unit):
            return "Invalid unit name"
        cmd += ["-u", unit]
    if priority in PRIORITIES:
        cmd += ["-p", priority]
    if since:
        cmd += ["--since", since]
    if boot:
        cmd += ["-b"]
    res = ex.run(cmd, timeout=40, sudo=False)
    return res.out if res.out else (res.err or "(no entries)")


def tail_file(ex: Executor, path: str, lines: int = 400) -> str:
    if not _PATH_RE.match(path) or ".." in path:
        return "Invalid path"
    res = ex.run(f"tail -n {int(lines)} {shlex.quote(path)}", timeout=20)
    if not res.ok and "ermission" in res.err:
        res = ex.run(f"tail -n {int(lines)} {shlex.quote(path)}", timeout=20, sudo=True)
    return res.out if res.ok else res.err


def available_files(ex: Executor) -> list[str]:
    test = " ".join(shlex.quote(f) for f in COMMON_FILES)
    res = ex.run(f"for f in {test}; do [ -e \"$f\" ] && echo \"$f\"; done", timeout=10)
    return [ln.strip() for ln in res.out.splitlines() if ln.strip()]


def filter_text(text: str, needle: str, case: bool = False) -> str:
    if not needle:
        return text
    n = needle if case else needle.lower()
    return "\n".join(ln for ln in text.splitlines() if n in (ln if case else ln.lower()))
