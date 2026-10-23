from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QLabel, QLineEdit, QSpinBox)

from ...core.hosts import LOCAL_NAME
from ..widgets import PageHeader, button, confirm, fill_table, fit_columns, hbox, info, make_table, run_async, selected_text
from .base import Page


class HostDialog(QDialog):
    def __init__(self, parent, profile: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Server profile")
        self.setMinimumWidth(460)
        p = profile or {}
        form = QFormLayout(self)
        self.name = QLineEdit(p.get("name", ""))
        self.host = QLineEdit(p.get("host", ""))
        self.user = QLineEdit(p.get("user", ""))
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(int(p.get("port", 22)))
        self.key = QLineEdit(p.get("key", ""))
        self.key.setPlaceholderText("~/.ssh/id_ed25519 (optional, agent is used otherwise)")
        browse = button("Browse…", slot=self._browse)
        form.addRow("Display name", self.name)
        form.addRow("Host / IP", self.host)
        form.addRow("SSH user", self.user)
        form.addRow("Port", self.port)
        form.addRow("Private key", hbox(self.key, browse))
        note = QLabel("Authentication uses SSH keys only (no passwords are stored).\n"
                      "Administrative actions use `sudo -n`, so the user needs passwordless sudo for those commands.")
        note.setObjectName("muted")
        form.addRow(note)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Private key", "~/.ssh")
        if path:
            self.key.setText(path)

    def _ok(self) -> None:
        if not self.name.text().strip() or not self.host.text().strip() or self.name.text().strip() == LOCAL_NAME:
            info(self, "Server", "A unique display name and a host are required.", error=True)
            return
        self.accept()

    def profile(self) -> dict:
        return {"name": self.name.text().strip(), "host": self.host.text().strip(), "user": self.user.text().strip(),
                "port": self.port.value(), "key": self.key.text().strip()}


class ServersPage(Page):
    title = "Servers"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.root.addWidget(PageHeader("Servers", "Manage remote servers over SSH; localhost is always available"))
        self.root.addLayout(hbox(
            button("Add server", "primary", slot=self.add), button("Edit", slot=self.edit),
            button("Remove", "danger", slot=self.remove), None,
            button("Test connection", slot=self.test), button("Connect", "primary", slot=self.connect_)))
        self.table = make_table(["Name", "Host", "User", "Port", "Key", "Active"], stretch=1)
        fit_columns(self.table, [200, 0, 140, 70, 260, 80])
        self.table.itemDoubleClicked.connect(lambda *_: self.connect_())
        self.root.addWidget(self.table, 1)
        ctx.host_changed.connect(lambda _n: self.refresh())

    def refresh(self) -> None:
        rows = [[LOCAL_NAME, "this machine", "", "", "", ("●" if self.ctx.host == LOCAL_NAME else "", 0)]]
        for h in self.ctx.hosts.profiles():
            rows.append([h["name"], h["host"], h.get("user", ""), str(h.get("port", 22)), h.get("key", ""),
                         ("●" if self.ctx.host == h["name"] else "", 0)])
        fill_table(self.table, rows)

    def _profile(self, name: str | None) -> dict | None:
        return next((h for h in self.ctx.hosts.profiles() if h["name"] == name), None)

    def add(self) -> None:
        dlg = HostDialog(self)
        if dlg.exec():
            self.ctx.hosts.upsert(dlg.profile())
            self.ctx.settings_changed.emit()
            self.refresh()

    def edit(self) -> None:
        prof = self._profile(selected_text(self.table))
        if not prof:
            info(self, "Servers", "Select a saved server (localhost cannot be edited).")
            return
        dlg = HostDialog(self, prof)
        if dlg.exec():
            new = dlg.profile()
            if new["name"] != prof["name"]:
                self.ctx.hosts.remove(prof["name"])
            self.ctx.hosts.upsert(new)
            self.ctx.settings_changed.emit()
            self.refresh()

    def remove(self) -> None:
        name = selected_text(self.table)
        if not self._profile(name):
            return
        if confirm(self, "Remove server", f"Remove '{name}' from the list?", True, True):
            if self.ctx.host == name:
                self.ctx.set_host(LOCAL_NAME)
            self.ctx.hosts.remove(name)
            self.ctx.settings_changed.emit()
            self.refresh()

    def test(self) -> None:
        name = selected_text(self.table)
        if not name:
            return
        ex = self.ctx.hosts.executor(name)

        def work():
            r = ex.run("echo connected as $(id -un) on $(hostname); sudo -n true 2>/dev/null && echo 'passwordless sudo: yes' "
                       "|| echo 'passwordless sudo: no'", timeout=15)
            return r

        def done(r):
            info(self, f"Test: {name}", r.out.strip() if r.ok else (r.err.strip() or "Connection failed"), error=not r.ok)

        run_async(work, done, self.fail)

    def connect_(self) -> None:
        name = selected_text(self.table)
        if name:
            self.ctx.set_host(name)
