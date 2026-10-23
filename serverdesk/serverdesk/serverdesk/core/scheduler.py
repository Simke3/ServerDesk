"""cron and systemd timers."""
from __future__ import annotations

from .executor import Executor, Result


def get_crontab(ex: Executor, user: str = "") -> str:
    cmd = ["crontab", "-l"] + (["-u", user] if user else [])
    res = ex.run(cmd, timeout=10, sudo=bool(user))
    if res.ok:
        return res.out
    if "no crontab" in res.err.lower():
        return ""
    raise RuntimeError(res.err.strip() or "crontab failed")


def set_crontab(ex: Executor, content: str, user: str = "") -> Result:
    if content and not content.endswith("\n"):
        content += "\n"
    cmd = ["crontab"] + (["-u", user] if user else []) + ["-"]
    return ex.run_audited("cron.save", cmd, input=content, sudo=bool(user))


def timers(ex: Executor) -> list[dict]:
    res = ex.run("systemctl list-timers --all --no-pager --no-legend 2>/dev/null", timeout=20)
    rows = []
    for line in res.out.splitlines():
        if not line.strip():
            continue
        # Columns are variable width; split on the trailing unit names.
        parts = line.rsplit(None, 2)
        if len(parts) == 3:
            when, unit, activates = parts[0], parts[1], parts[2]
            rows.append({"schedule": when.strip(), "unit": unit, "activates": activates})
    return rows


def system_cron_files(ex: Executor) -> str:
    return ex.run("ls -1 /etc/cron.d /etc/cron.daily /etc/cron.hourly /etc/cron.weekly 2>/dev/null",
                  timeout=10).out
