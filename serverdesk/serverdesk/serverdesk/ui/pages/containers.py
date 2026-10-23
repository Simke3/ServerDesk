from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QSplitter, QTabWidget, QVBoxLayout, QWidget

from ...core import docker
from .. import theme
from ..widgets import PageHeader, button, confirm, fill_table, fit_columns, hbox, info, make_table, run_async, selected_text, LogHighlighter
from .base import Page


class ContainersPage(Page):
    title = "Containers"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.root.addWidget(PageHeader("Containers", "Docker containers and images"))
        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.tabs = QTabWidget()
        self.root.addWidget(self.status)
        self.root.addWidget(self.tabs, 1)

        w = QWidget()
        v = QVBoxLayout(w)
        v.addLayout(hbox(
            None,
            button("Start", slot=lambda: self.act("start")),
            button("Stop", slot=lambda: self.act("stop")),
            button("Restart", "primary", slot=lambda: self.act("restart")),
            button("Pause", slot=lambda: self.act("pause")),
            button("Resume", slot=lambda: self.act("unpause")),
            button("Remove", "danger", slot=lambda: self.act("rm")),
            button("Refresh", slot=self.refresh)))
        self.table = make_table(["Name", "Image", "State", "Status", "CPU", "Memory", "Ports", "ID"], stretch=6)
        fit_columns(self.table, [190, 230, 90, 170, 70, 150, 0, 110])
        self.table.itemSelectionChanged.connect(self._sel)
        self.logs = QPlainTextEdit()
        self.logs.setObjectName("log")
        self.logs.setReadOnly(True)
        self._hl = LogHighlighter(self.logs.document())
        split = QSplitter(Qt.Vertical)
        split.addWidget(self.table)
        split.addWidget(self.logs)
        split.setSizes([400, 260])
        v.addWidget(split, 1)
        self.tabs.addTab(w, "Containers")

        w = QWidget()
        v = QVBoxLayout(w)
        v.addLayout(hbox(None, button("Prune unused data", "danger", slot=self.prune)))
        self.images = make_table(["Repository", "Tag", "Image ID", "Size", "Created"], stretch=0)
        fit_columns(self.images, [0, 140, 130, 100, 160])
        v.addWidget(self.images)
        self.tabs.addTab(w, "Images")
        self._deb = QTimer(self)
        self._deb.setSingleShot(True)
        self._deb.setInterval(300)
        self._deb.timeout.connect(self._load_logs)
        self.available = True

    def refresh(self) -> None:
        ex = self.ctx.ex

        def work():
            if not docker.available(ex):
                return None
            return docker.containers(ex), docker.stats(ex), docker.images(ex)

        run_async(work, self._got, self.fail)

    def _got(self, data) -> None:
        if data is None:
            self.status.setText("Docker is not installed, not running, or the current user cannot access it.")
            self.status.setStyleSheet(f"color: {theme.WARN};")
            fill_table(self.table, [])
            return
        self.status.setText("")
        containers, stats, images = data
        rows = []
        for c in containers:
            st = stats.get(c.get("Names", ""), {})
            state = c.get("State", "")
            col = theme.GOOD if state == "running" else theme.BAD if state in ("exited", "dead") else theme.WARN
            rows.append([c.get("Names", ""), c.get("Image", ""), (state, state, col), c.get("Status", ""),
                         st.get("CPUPerc", "-"), st.get("MemUsage", "-"), c.get("Ports", ""), c.get("ShortID", "")])
        fill_table(self.table, rows)
        fill_table(self.images, [[i.get("Repository", ""), i.get("Tag", ""), i.get("ID", ""), i.get("Size", ""),
                                  i.get("CreatedSince", "")] for i in images])

    def _sel(self) -> None:
        self._deb.start()

    def _load_logs(self) -> None:
        name = selected_text(self.table)
        if not name:
            return
        ex = self.ctx.ex
        run_async(lambda: docker.logs(ex, name), self.logs.setPlainText, self.fail)

    def act(self, action: str) -> None:
        name = selected_text(self.table)
        if not name:
            info(self, "Containers", "Select a container first.")
            return
        if action in ("rm", "stop", "restart") and not confirm(
                self, "Confirm", f"{'Remove' if action == 'rm' else action.capitalize()} container {name}?",
                True, self.ctx.cfg.get("confirm_destructive", True)):
            return
        ex = self.ctx.ex

        def done(res):
            if not res.ok:
                info(self, "Docker", res.err or res.out, error=True)
            self.refresh()

        run_async(lambda: docker.act(ex, name, action), done, self.fail)

    def prune(self) -> None:
        if not confirm(self, "Docker prune", "Remove stopped containers, dangling images and unused networks?",
                       True, True):
            return
        ex = self.ctx.ex
        run_async(lambda: docker.prune(ex), lambda r: (info(self, "Docker prune", r.out or r.err), self.refresh()), self.fail)
