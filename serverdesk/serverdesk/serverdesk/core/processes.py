"""Process listing and signalling through ps/kill."""
from __future__ import annotations

from .executor import Executor, Result

SIGNALS = {"TERM": "15", "KILL": "9", "HUP": "1", "STOP": "19", "CONT": "18"}


def list_processes(ex: Executor) -> list[dict]:
    res = ex.run("ps -eo pid=,ppid=,user:20=,pcpu=,pmem=,rss=,nlwp=,etime=,stat=,comm=,args= --sort=-pcpu",
                 timeout=20)
    if not res.ok:
        raise RuntimeError(res.err.strip() or "ps failed")
    rows = []
    for line in res.out.splitlines():
        p = line.split(None, 10)
        if len(p) < 10:
            continue
        try:
            rows.append({
                "pid": int(p[0]), "ppid": int(p[1]), "user": p[2],
                "cpu": float(p[3]), "mem": float(p[4]), "rss": int(p[5]) * 1024,
                "threads": int(p[6]), "etime": p[7], "state": p[8], "name": p[9],
                "cmd": p[10] if len(p) > 10 else p[9],
            })
        except ValueError:
            continue
    return rows


def signal_process(ex: Executor, pid: int, sig: str) -> Result:
    if sig not in SIGNALS or pid <= 1:
        return Result(2, "", "Refusing: invalid signal or protected PID")
    return ex.run_audited(f"process.{sig.lower()}", ["kill", f"-{SIGNALS[sig]}", str(int(pid))], sudo=True)


def renice(ex: Executor, pid: int, value: int) -> Result:
    value = max(-20, min(19, int(value)))
    return ex.run_audited("process.renice", ["renice", "-n", str(value), "-p", str(int(pid))], sudo=True)
