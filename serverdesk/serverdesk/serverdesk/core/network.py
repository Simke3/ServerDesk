"""Network interfaces, listening sockets, routes and diagnostics."""
from __future__ import annotations

import json
import re

from .executor import Executor

_HOST_RE = re.compile(r"^[A-Za-z0-9_.\-:]+$")


def interfaces(ex: Executor) -> list[dict]:
    res = ex.run(["ip", "-j", "addr"], timeout=10)
    if not res.ok:
        raise RuntimeError(res.err.strip() or "ip failed")
    rows = []
    for i in json.loads(res.out):
        addrs = [f"{a['local']}/{a['prefixlen']}" for a in i.get("addr_info", [])]
        rows.append({"name": i.get("ifname", ""), "state": i.get("operstate", ""),
                     "mac": i.get("address", ""), "mtu": i.get("mtu", ""), "addrs": ", ".join(addrs)})
    return rows


def routes(ex: Executor) -> list[str]:
    return [ln for ln in ex.run(["ip", "route"], timeout=10).out.splitlines() if ln.strip()]


def listening(ex: Executor) -> list[dict]:
    res = ex.run("ss -tulpnH 2>/dev/null || ss -tulnH", timeout=15, sudo=False)
    rows = []
    for line in res.out.splitlines():
        p = line.split(None, 6)
        if len(p) < 5:
            continue
        proc = ""
        if len(p) > 6:
            m = re.search(r'users:\(\("([^"]+)",pid=(\d+)', p[6])
            proc = f"{m.group(1)} ({m.group(2)})" if m else ""
        rows.append({"proto": p[0], "state": p[1], "local": p[4], "peer": p[5] if len(p) > 5 else "",
                     "process": proc})
    return rows


def connections_summary(ex: Executor) -> str:
    return ex.run("ss -s", timeout=10).out


def dns_servers(ex: Executor) -> list[str]:
    out = ex.run("grep -h '^nameserver' /etc/resolv.conf", timeout=8).out
    return [ln.split()[1] for ln in out.splitlines() if len(ln.split()) > 1]


def ping(ex: Executor, host: str, count: int = 4) -> str:
    if not _HOST_RE.match(host):
        return "Invalid host"
    return ex.run(["ping", "-c", str(int(count)), "-W", "2", host], timeout=30).text


def traceroute(ex: Executor, host: str) -> str:
    if not _HOST_RE.match(host):
        return "Invalid host"
    res = ex.run(f"(command -v traceroute >/dev/null && traceroute -m 15 -w 2 {host}) || tracepath -m 15 {host}",
                 timeout=60)
    return res.text


def dns_lookup(ex: Executor, host: str) -> str:
    if not _HOST_RE.match(host):
        return "Invalid host"
    return ex.run(f"getent ahosts {host}", timeout=15).text
