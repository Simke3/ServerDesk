from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QInputDialog, QLabel, QLineEdit

from ...core import processes
from ...core.metrics import human_bytes
from .. import theme
from ..widgets import PageHeader, button, confirm, fill_table, fit_columns, filter_rows, hbox, info, make_table, run_async
from .base import Page


class ProcessesPage(Page):
    title = "Processes"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.root.addWidget(PageHeader("Processes", "Running processes sorted by CPU; signal or renice with audit logging"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter by name, user, PID or command…")
        self.search.textChanged.connect(lambda t: filter_rows(self.table, t))
        self.count = QLabel("")
        self.count.setObjectName("muted")
        self.root.addLayout(hbox(
            self.search, self.count, None,
            button("Terminate", slot=lambda: self.signal("TERM")),
            button("Kill", "danger", slot=lambda: self.signal("KILL")),
            button("Pause", slot=lambda: self.signal("STOP")),
            button("Resume", slot=lambda: self.signal("CONT")),
            button("Renice…", slot=self.renice),
            button("Refresh", slot=self.refresh)))
        self.table = make_table(["PID", "User", "CPU %", "Mem %", "RSS", "Thr", "State", "Elapsed", "Name", "Command"],
                                stretch=9)
        fit_columns(self.table, [70, 110, 70, 70, 90, 50, 60, 100, 150, 0])
        self.table.sortItems(2, 1)
        self.root.addWidget(self.table, 1)
        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self.refresh)
        self._busy = False

    def on_show(self) -> None:
        self._timer.start()

    def on_hide(self) -> None:
        self._timer.stop()

    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        ex = self.ctx.ex
        run_async(lambda: processes.list_processes(ex), self._fill, self._err)

    def _err(self, exc) -> None:
        self._busy = False
        self.fail(exc)

    def _fill(self, rows: list[dict]) -> None:
        self._busy = False
        out = []
        for p in rows:
            cpu_col = theme.WARN if p["cpu"] >= 50 else None
            out.append([(str(p["pid"]), p["pid"]), p["user"], (f"{p['cpu']:.1f}", p["cpu"], cpu_col),
                        (f"{p['mem']:.1f}", p["mem"]), (human_bytes(p["rss"]), p["rss"]), (str(p["threads"]), p["threads"]),
                        p["state"], p["etime"], p["name"], p["cmd"]])
        fill_table(self.table, out)
        self.count.setText(f"{len(rows)} processes")
        filter_rows(self.table, self.search.text())

    def _selected(self):
        r = self.table.currentRow()
        if r < 0:
            info(self, "Processes", "Select a process first.")
            return None
        return int(self.table.item(r, 0).text()), self.table.item(r, 8).text()

    def signal(self, sig: str) -> None:
        sel = self._selected()
        if not sel:
            return
        pid, name = sel
        if sig in ("TERM", "KILL") and not confirm(
                self, "Confirm", f"Send SIG{sig} to {name} (PID {pid}) on {self.ctx.host}?", True,
                self.ctx.cfg.get("confirm_destructive", True)):
            return
        ex = self.ctx.ex
        run_async(lambda: processes.signal_process(ex, pid, sig), self._done, self.fail)

    def renice(self) -> None:
        sel = self._selected()
        if not sel:
            return
        pid, name = sel
        val, ok = QInputDialog.getInt(self, "Renice", f"New priority for {name} (-20 high … 19 low):", 0, -20, 19)
        if ok:
            ex = self.ctx.ex
            run_async(lambda: processes.renice(ex, pid, val), self._done, self.fail)

    def _done(self, res) -> None:
        if not res.ok:
            info(self, "Process action failed", res.err or res.out, error=True)
        self.refresh()
