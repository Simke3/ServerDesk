from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QTableWidgetItem, QVBoxLayout, QWidget

from ...core import services
from ...core.metrics import human_bytes, human_duration
from .. import theme
from ..widgets import Card, Gauge, PageHeader, Sparkline, StatCard, fit_columns, make_table, run_async, usage_bar
from .base import Page


class DashboardPage(Page):
    title = "Dashboard"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.root.addWidget(PageHeader("Dashboard", "Live health overview of the selected server"))

        # gauges
        gauge_row = QHBoxLayout()
        gauge_row.setSpacing(12)
        self.g_cpu, self.g_mem = Gauge("CPU"), Gauge("Memory")
        self.g_swap, self.g_disk = Gauge("Swap"), Gauge("Root disk")
        for g in (self.g_cpu, self.g_mem, self.g_swap, self.g_disk):
            card = Card()
            card.lay.addWidget(g)
            gauge_row.addWidget(card)
        self.root.addLayout(gauge_row)

        # stat cards
        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.s_load = StatCard("Load average")
        self.s_up = StatCard("Uptime")
        self.s_net = StatCard("Network")
        self.s_failed = StatCard("Failed services")
        for s in (self.s_load, self.s_up, self.s_net, self.s_failed):
            stats.addWidget(s)
        self.root.addLayout(stats)

        # charts + info
        mid = QHBoxLayout()
        mid.setSpacing(12)
        charts = Card("History")
        self.sp_cpu = Sparkline("CPU")
        self.sp_mem = Sparkline("Memory")
        self.sp_net = Sparkline("Network  ↓ / ↑", fixed_max=None, formatter=lambda v: human_bytes(v, "B/s"))
        for sp in (self.sp_cpu, self.sp_mem, self.sp_net):
            charts.lay.addWidget(sp)
        mid.addWidget(charts, 3)

        right = QVBoxLayout()
        right.setSpacing(12)
        info = Card("System")
        self.info_lbl = QLabel("—")
        self.info_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        info.lay.addWidget(self.info_lbl)
        right.addWidget(info)
        alerts = Card("Active alerts")
        self.alert_tbl = make_table(["Level", "Alert", "Since"], stretch=1)
        self.alert_tbl.setSortingEnabled(False)
        self.alert_tbl.setMinimumHeight(120)
        fit_columns(self.alert_tbl, [80, 0, 80])
        alerts.lay.addWidget(self.alert_tbl)
        right.addWidget(alerts, 1)
        mid.addLayout(right, 2)
        self.root.addLayout(mid, 1)

        disks = Card("Filesystems")
        self.disk_tbl = make_table(["Mount", "Device", "Type", "Size", "Used", "Free", "Usage"], stretch=1)
        self.disk_tbl.setMaximumHeight(190)
        self.disk_tbl.setSortingEnabled(False)
        disks.lay.addWidget(self.disk_tbl)
        self.root.addWidget(disks)

        ctx.snapshot.connect(self.on_snapshot)
        ctx.monitor_error.connect(self.on_error)
        self._failed_tick = 0

    def on_host_changed(self) -> None:
        self.info_lbl.setText("Connecting…")

    def refresh(self) -> None:
        if self.ctx.last_snapshot:
            self.on_snapshot(self.ctx.last_snapshot)

    def on_error(self, msg: str) -> None:
        self.info_lbl.setText(f"<span style='color:{theme.BAD}'>Cannot reach server:</span><br>{msg}")

    def on_snapshot(self, s: dict) -> None:
        th = self.ctx.cfg.get("thresholds")
        self.g_cpu.set_value(s["cpu"], sub=f"{s['ncpu']} cores")
        self.g_mem.set_value(s["mem_pct"], sub=f"{human_bytes(s['mem_used'])} / {human_bytes(s['mem_total'])}")
        if s["swap_total"]:
            self.g_swap.set_value(s["swap_pct"], sub=f"{human_bytes(s['swap_used'])} / {human_bytes(s['swap_total'])}")
        else:
            self.g_swap.set_value(0, "off", "no swap")
        root = next((d for d in s["disks"] if d["mount"] == "/"), s["disks"][0] if s["disks"] else None)
        if root:
            self.g_disk.set_value(root["pct"], sub=f"{human_bytes(root['used'])} / {human_bytes(root['size'])}")

        l1, l5, l15 = s["load"]
        per_core = l1 / s["ncpu"]
        self.s_load.set(f"{l1:.2f}", f"5m {l5:.2f}  ·  15m {l15:.2f}",
                        theme.BAD if per_core >= th["load_per_core"] else None)
        self.s_up.set(human_duration(s["uptime"]), s["kernel"])
        self.s_net.set(f"↓ {human_bytes(s['rx_rate'], 'B/s')}", f"↑ {human_bytes(s['tx_rate'], 'B/s')}")

        h = s.get("history") or {}
        if h:
            self.sp_cpu.set_series((h["cpu"], theme.ACCENT))
            self.sp_mem.set_series((h["mem"], "#a855f7"))
            self.sp_net.set_series((h["rx"], theme.GOOD), (h["tx"], theme.WARN))

        temp = f"<br>Temperature: {s['temp']:.0f} °C" if s.get("temp") is not None else ""
        self.info_lbl.setText(
            f"<b>{s['hostname']}</b><br>{s['os']}<br>Kernel {s['kernel']}<br>{s['cpu_model']}{temp}")

        disks = sorted(s["disks"], key=lambda d: d["mount"])
        self.disk_tbl.setRowCount(len(disks))
        for r, d in enumerate(disks):
            vals = [d["mount"], d["device"], d["fstype"], human_bytes(d["size"]), human_bytes(d["used"]),
                    human_bytes(d["avail"])]
            for c, val in enumerate(vals):
                self.disk_tbl.setItem(r, c, QTableWidgetItem(val))
            self.disk_tbl.setCellWidget(r, 6, self._bar_cell(d["pct"]))

        alerts = list(self.ctx.engine().active.values())
        self.alert_tbl.setRowCount(len(alerts))
        for r, a in enumerate(alerts):
            lvl = QTableWidgetItem(a["level"].upper())
            lvl.setForeground(QColor(theme.BAD if a["level"] == "critical" else theme.WARN))
            self.alert_tbl.setItem(r, 0, lvl)
            self.alert_tbl.setItem(r, 1, QTableWidgetItem(a["message"]))
            self.alert_tbl.setItem(r, 2, QTableWidgetItem(a["since"].strftime("%H:%M:%S")))

        self._failed_tick = (self._failed_tick + 1) % 5
        if self._failed_tick == 1:
            ex = self.ctx.ex
            run_async(lambda: services.failed_count(ex), self._set_failed)

    def _set_failed(self, n: int) -> None:
        self.s_failed.set(str(n), "systemctl --failed", theme.BAD if n else theme.GOOD)

    @staticmethod
    def _bar_cell(pct: float) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(6, 0, 6, 0)
        lay.setSpacing(8)
        lay.addWidget(usage_bar(pct), 1)
        lbl = QLabel(f"{pct:.0f}%")
        lbl.setFixedWidth(38)
        lay.addWidget(lbl)
        return w
