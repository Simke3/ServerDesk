from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QFormLayout, QLabel, QSpinBox

from ..widgets import Card, PageHeader, button
from .base import Page


class SettingsPage(Page):
    title = "Settings"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.root.addWidget(PageHeader("Settings", "Monitoring intervals, alert thresholds and safety options"))
        card = Card("Monitoring & alerts")
        form = QFormLayout()
        form.setHorizontalSpacing(24)
        self.refresh_s = QSpinBox()
        self.refresh_s.setRange(1, 60)
        self.refresh_s.setSuffix(" s")
        self.cpu = self._pct()
        self.mem = self._pct()
        self.disk = self._pct()
        self.load = QDoubleSpinBox()
        self.load.setRange(0.1, 50)
        self.load.setSingleStep(0.25)
        self.alerts = QCheckBox("Raise alerts and desktop notifications")
        self.confirm = QCheckBox("Ask for confirmation before stop / kill / delete / remove actions")
        self.log_lines = QSpinBox()
        self.log_lines.setRange(50, 20000)
        self.log_lines.setSingleStep(100)
        form.addRow("Refresh interval", self.refresh_s)
        form.addRow("CPU alert at", self.cpu)
        form.addRow("Memory alert at", self.mem)
        form.addRow("Disk alert at", self.disk)
        form.addRow("Load per core alert at", self.load)
        form.addRow("Default log lines", self.log_lines)
        form.addRow("", self.alerts)
        form.addRow("", self.confirm)
        card.lay.addLayout(form)
        self.root.addWidget(card)
        self.saved = QLabel("")
        self.saved.setObjectName("muted")
        self.root.addWidget(button("Save settings", "primary", slot=self.save))
        self.root.addWidget(self.saved)
        self.root.addStretch(1)

    @staticmethod
    def _pct() -> QSpinBox:
        s = QSpinBox()
        s.setRange(10, 100)
        s.setSuffix(" %")
        return s

    def refresh(self) -> None:
        c = self.ctx.cfg
        th = c.get("thresholds")
        self.refresh_s.setValue(int(c.get("refresh_seconds", 2)))
        self.cpu.setValue(int(th["cpu"]))
        self.mem.setValue(int(th["memory"]))
        self.disk.setValue(int(th["disk"]))
        self.load.setValue(float(th["load_per_core"]))
        self.alerts.setChecked(bool(c.get("alerts_enabled", True)))
        self.confirm.setChecked(bool(c.get("confirm_destructive", True)))
        self.log_lines.setValue(int(c.get("log_lines", 400)))
        self.saved.setText("")

    def save(self) -> None:
        c = self.ctx.cfg
        c.set("refresh_seconds", self.refresh_s.value())
        c.set("thresholds", {"cpu": self.cpu.value(), "memory": self.mem.value(), "disk": self.disk.value(),
                             "load_per_core": self.load.value()})
        c.set("alerts_enabled", self.alerts.isChecked())
        c.set("confirm_destructive", self.confirm.isChecked())
        c.set("log_lines", self.log_lines.value())
        self.ctx.apply_settings()
        self.saved.setText("Settings saved.")
