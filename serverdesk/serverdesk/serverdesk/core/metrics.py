"""System metrics collected from /proc over any Executor (local or SSH)."""
from __future__ import annotations

import time
from collections import deque

from .executor import Executor

_SCRIPT = r"""
echo '##stat'; grep '^cpu' /proc/stat
echo '##mem'; cat /proc/meminfo
echo '##load'; cat /proc/loadavg
echo '##up'; cat /proc/uptime
echo '##net'; cat /proc/net/dev
echo '##df'; df -PkT -x tmpfs -x devtmpfs -x squashfs -x overlay -x efivarfs 2>/dev/null
echo '##host'; hostname; (. /etc/os-release 2>/dev/null; echo "$PRETTY_NAME"); uname -r
echo '##temp'; cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | head -8
echo '##cpuinfo'; grep -m1 'model name' /proc/cpuinfo
"""


def _sections(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    cur = None
    for line in text.splitlines():
        if line.startswith("##"):
            cur = line[2:].strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return out


class MetricsCollector:
    HISTORY = 120

    def __init__(self, ex: Executor):
        self.ex = ex
        self._prev_cpu: list[tuple[int, int]] | None = None
        self._prev_net: tuple[float, int, int] | None = None
        self.history = {k: deque(maxlen=self.HISTORY) for k in ("cpu", "mem", "rx", "tx", "load")}

    def snapshot(self) -> dict:
        res = self.ex.run(_SCRIPT, timeout=15)
        if not res.ok and not res.out:
            raise RuntimeError(res.err.strip() or "Unable to collect metrics")
        s = _sections(res.out)
        snap: dict = {"ts": time.time()}

        # CPU ---------------------------------------------------------
        times = []
        for line in s.get("stat", []):
            p = line.split()
            if not p or not p[0].startswith("cpu"):
                continue
            vals = [int(x) for x in p[1:9]]
            idle = vals[3] + vals[4]
            times.append((sum(vals), idle))
        cpu_total, cores = 0.0, []
        if self._prev_cpu and len(self._prev_cpu) == len(times):
            pct = []
            for (t1, i1), (t0, i0) in zip(times, self._prev_cpu):
                dt = t1 - t0
                pct.append(max(0.0, min(100.0, 100.0 * (1 - (i1 - i0) / dt))) if dt > 0 else 0.0)
            cpu_total, cores = pct[0], pct[1:]
        self._prev_cpu = times
        snap["cpu"] = cpu_total
        snap["cores"] = cores
        snap["ncpu"] = max(1, len(times) - 1)

        # Memory ------------------------------------------------------
        mem = {}
        for line in s.get("mem", []):
            if ":" in line:
                k, v = line.split(":", 1)
                mem[k.strip()] = int(v.split()[0]) * 1024
        total = mem.get("MemTotal", 0)
        avail = mem.get("MemAvailable", mem.get("MemFree", 0))
        snap["mem_total"], snap["mem_used"] = total, max(0, total - avail)
        snap["mem_cached"] = mem.get("Cached", 0) + mem.get("Buffers", 0)
        snap["swap_total"] = mem.get("SwapTotal", 0)
        snap["swap_used"] = max(0, snap["swap_total"] - mem.get("SwapFree", 0))
        snap["mem_pct"] = 100.0 * snap["mem_used"] / total if total else 0.0
        snap["swap_pct"] = 100.0 * snap["swap_used"] / snap["swap_total"] if snap["swap_total"] else 0.0

        # Load / uptime -----------------------------------------------
        try:
            snap["load"] = tuple(float(x) for x in s["load"][0].split()[:3])
        except (KeyError, IndexError, ValueError):
            snap["load"] = (0.0, 0.0, 0.0)
        try:
            snap["uptime"] = float(s["up"][0].split()[0])
        except (KeyError, IndexError, ValueError):
            snap["uptime"] = 0.0

        # Network -----------------------------------------------------
        rx = tx = 0
        for line in s.get("net", [])[2:]:
            if ":" not in line:
                continue
            name, data = line.split(":", 1)
            if name.strip() == "lo":
                continue
            f = data.split()
            rx += int(f[0])
            tx += int(f[8])
        now = snap["ts"]
        rx_rate = tx_rate = 0.0
        if self._prev_net:
            t0, rx0, tx0 = self._prev_net
            dt = max(now - t0, 0.001)
            rx_rate, tx_rate = max(0, rx - rx0) / dt, max(0, tx - tx0) / dt
        self._prev_net = (now, rx, tx)
        snap["rx_rate"], snap["tx_rate"] = rx_rate, tx_rate
        snap["rx_total"], snap["tx_total"] = rx, tx

        # Disks -------------------------------------------------------
        disks = []
        for line in s.get("df", [])[1:]:
            p = line.split()
            if len(p) < 7:
                continue
            try:
                size, used, avail_k = int(p[2]) * 1024, int(p[3]) * 1024, int(p[4]) * 1024
            except ValueError:
                continue
            disks.append({"device": p[0], "fstype": p[1], "size": size, "used": used,
                          "avail": avail_k, "pct": 100.0 * used / size if size else 0.0,
                          "mount": " ".join(p[6:])})
        snap["disks"] = disks

        # Host info ---------------------------------------------------
        h = s.get("host", [])
        snap["hostname"] = h[0] if len(h) > 0 else "?"
        snap["os"] = h[1] if len(h) > 1 and h[1] else "Linux"
        snap["kernel"] = h[2] if len(h) > 2 else ""
        temps = []
        for t in s.get("temp", []):
            try:
                temps.append(int(t) / 1000.0)
            except ValueError:
                pass
        snap["temp"] = max(temps) if temps else None
        ci = s.get("cpuinfo", [])
        snap["cpu_model"] = ci[0].split(":", 1)[1].strip() if ci and ":" in ci[0] else ""

        # history -----------------------------------------------------
        self.history["cpu"].append(snap["cpu"])
        self.history["mem"].append(snap["mem_pct"])
        self.history["rx"].append(rx_rate)
        self.history["tx"].append(tx_rate)
        self.history["load"].append(snap["load"][0])
        return snap


def human_bytes(n: float, suffix: str = "B") -> str:
    n = float(n)
    for unit in ("", "K", "M", "G", "T", "P"):
        if abs(n) < 1024:
            return f"{n:.0f} {unit}{suffix}" if unit == "" else f"{n:.1f} {unit}{suffix}"
        n /= 1024
    return f"{n:.1f} E{suffix}"


def human_duration(seconds: float) -> str:
    s = int(seconds)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, _ = divmod(s, 60)
    if d:
        return f"{d}d {h}h {m}m"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"
