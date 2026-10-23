from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPlainTextEdit

from ...core import packages
from ..widgets import PageHeader, button, confirm, hbox, run_async
from .base import Page


class UpdatesPage(Page):
    title = "Updates"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.root.addWidget(PageHeader("Updates", "Pending package updates (apt, dnf, yum, pacman, zypper)"))
        self.label = QLabel("")
        self.label.setObjectName("muted")
        self.root.addLayout(hbox(self.label, None, button("Refresh package index", slot=self.refresh_index),
                                 button("Check updates", "primary", slot=self.check),
                                 button("Upgrade all", "danger", slot=self.upgrade)))
        self.out = QPlainTextEdit()
        self.out.setObjectName("log")
        self.out.setReadOnly(True)
        self.root.addWidget(self.out, 1)
        self.tool = ""

    def on_host_changed(self) -> None:
        self.tool = ""
        self.out.clear()

    def refresh(self) -> None:
        self.check()

    def _detect(self, then) -> None:
        if self.tool:
            then()
            return
        ex = self.ctx.ex

        def done(tool):
            self.tool = tool
            self.label.setText(f"Package manager: {tool or 'not detected'}")
            if tool:
                then()

        run_async(lambda: packages.detect(ex), done, self.fail)

    def check(self) -> None:
        def go():
            ex, tool = self.ctx.ex, self.tool
            self.out.setPlainText("Checking…")

            def done(rows):
                self.out.setPlainText("\n".join(rows) if rows else "System is up to date (per the local package index).")
                self.label.setText(f"Package manager: {tool}  ·  {len(rows)} pending updates")

            run_async(lambda: packages.pending_updates(ex, tool), done, self.fail)
        self._detect(go)

    def refresh_index(self) -> None:
        def go():
            ex, tool = self.ctx.ex, self.tool
            self.out.setPlainText("Refreshing package index…")
            run_async(lambda: packages.refresh_index(ex, tool),
                      lambda r: (self.out.setPlainText(r.out + r.err), self.check()), self.fail)
        self._detect(go)

    def upgrade(self) -> None:
        def go():
            if not confirm(self, "Upgrade all packages", f"Install all pending updates on {self.ctx.host}? "
                           "Services may restart.", True, True):
                return
            ex, tool = self.ctx.ex, self.tool
            self.out.setPlainText("Upgrading… this can take several minutes.")
            run_async(lambda: packages.upgrade_all(ex, tool),
                      lambda r: (self.out.setPlainText(r.out + r.err), self.check()), self.fail)
        self._detect(go)
