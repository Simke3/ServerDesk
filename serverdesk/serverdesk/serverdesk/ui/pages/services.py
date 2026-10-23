from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QComboBox, QLineEdit, QPlainTextEdit, QSplitter

from ...core import services
from .. import theme
from ..widgets import (PageHeader, button, confirm, fill_table, fit_columns, hbox, info, make_table,
                       run_async, selected_text)
from .base import Page


class ServicesPage(Page):
    title = "Services"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.root.addWidget(PageHeader("Services", "systemd units: inspect, start, stop, restart and enable at boot"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter services…")
        self.search.textChanged.connect(self._apply_filter)
        self.mode = QComboBox()
        self.mode.addItems(["All", "Running", "Failed", "Inactive", "Enabled at boot"])
        self.mode.currentIndexChanged.connect(self._apply_filter)
        self.btns = {
            "start": button("Start", slot=lambda: self.act("start")),
            "stop": button("Stop", "danger", slot=lambda: self.act("stop")),
            "restart": button("Restart", "primary", slot=lambda: self.act("restart")),
            "reload": button("Reload", slot=lambda: self.act("reload")),
            "enable": button("Enable", slot=lambda: self.act("enable")),
            "disable": button("Disable", slot=lambda: self.act("disable")),
        }
        bar = hbox(self.search, self.mode, None, *self.btns.values(), button("Refresh", slot=self.refresh))
        self.root.addLayout(bar)

        self.table = make_table(["Unit", "Active", "Sub", "Boot", "Description"], stretch=4)
        fit_columns(self.table, [280, 90, 90, 90, 0])
        self.table.itemSelectionChanged.connect(self._sel_changed)
        self.detail = QPlainTextEdit()
        self.detail.setObjectName("log")
        self.detail.setReadOnly(True)
        split = QSplitter(Qt.Vertical)
        split.addWidget(self.table)
        split.addWidget(self.detail)
        split.setSizes([480, 220])
        self.root.addWidget(split, 1)
        self._rows: list[dict] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._load_status)

    def refresh(self) -> None:
        ex = self.ctx.ex
        run_async(lambda: services.list_services(ex), self._fill, self.fail)

    def _fill(self, rows: list[dict]) -> None:
        self._rows = rows
        self._apply_filter()

    def _apply_filter(self) -> None:
        mode = self.mode.currentText()
        needle = self.search.text().lower().strip()
        out = []
        for r in self._rows:
            if mode == "Running" and r["sub"] != "running":
                continue
            if mode == "Failed" and r["active"] != "failed":
                continue
            if mode == "Inactive" and r["active"] != "inactive":
                continue
            if mode == "Enabled at boot" and r["enabled"] != "enabled":
                continue
            if needle and needle not in r["unit"].lower() and needle not in r["description"].lower():
                continue
            colour = theme.BAD if r["active"] == "failed" else theme.GOOD if r["sub"] == "running" else None
            out.append([r["unit"], (r["active"], r["active"], colour), (r["sub"], r["sub"], colour),
                        r["enabled"], r["description"]])
        fill_table(self.table, out)

    def _sel_changed(self) -> None:
        self._timer.start()

    def _load_status(self) -> None:
        unit = selected_text(self.table)
        if not unit:
            return
        ex = self.ctx.ex
        run_async(lambda: services.status(ex, unit), self.detail.setPlainText, self.fail)

    def act(self, action: str) -> None:
        unit = selected_text(self.table)
        if not unit:
            info(self, "Services", "Select a service first.")
            return
        destructive = action in ("stop", "disable")
        if not confirm(self, "Confirm", f"{action.capitalize()} {unit} on {self.ctx.host}?",
                       destructive, self.ctx.cfg.get("confirm_destructive", True) and (destructive or action == "restart")):
            return
        ex = self.ctx.ex

        def done(res):
            if res.ok:
                self.ctx.notify(f"{unit}: {action} succeeded", "info")
            else:
                info(self, "Service action failed", res.err or res.out, error=True)
            self.refresh()
            self._load_status()

        run_async(lambda: services.act(ex, unit, action), done, self.fail)
