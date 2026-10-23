"""Threshold based alert engine with de-duplication."""
from __future__ import annotations

from datetime import datetime


class AlertEngine:
    def __init__(self):
        self.active: dict[str, dict] = {}
        self.log: list[dict] = []

    def evaluate(self, snap: dict, th: dict) -> list[dict]:
        """Return newly raised alerts; clears conditions that recovered."""
        conditions: dict[str, tuple[bool, str, str]] = {}
        conditions["cpu"] = (snap["cpu"] >= th["cpu"], "warning",
                             f"CPU usage {snap['cpu']:.0f}% (limit {th['cpu']}%)")
        conditions["memory"] = (snap["mem_pct"] >= th["memory"], "warning",
                                f"Memory usage {snap['mem_pct']:.0f}% (limit {th['memory']}%)")
        per_core = snap["load"][0] / max(1, snap["ncpu"])
        conditions["load"] = (per_core >= th["load_per_core"], "warning",
                              f"Load average {snap['load'][0]:.2f} on {snap['ncpu']} cores")
        for d in snap["disks"]:
            conditions[f"disk:{d['mount']}"] = (
                d["pct"] >= th["disk"], "critical",
                f"Disk {d['mount']} is {d['pct']:.0f}% full (limit {th['disk']}%)")
        if snap.get("temp") is not None:
            conditions["temp"] = (snap["temp"] >= 85, "critical", f"Temperature {snap['temp']:.0f} °C")

        raised = []
        for key, (bad, level, msg) in conditions.items():
            if bad and key not in self.active:
                alert = {"key": key, "level": level, "message": msg, "since": datetime.now(), "host": snap.get("hostname", "")}
                self.active[key] = alert
                self.log.append(alert)
                raised.append(alert)
            elif not bad and key in self.active:
                del self.active[key]
        # drop alerts for mounts that vanished
        for key in list(self.active):
            if key not in conditions:
                del self.active[key]
        self.log = self.log[-200:]
        return raised
