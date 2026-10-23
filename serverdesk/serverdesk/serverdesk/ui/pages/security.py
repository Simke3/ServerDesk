from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QInputDialog, QPlainTextEdit, QTabWidget, QVBoxLayout, QWidget

from ...core import users
from .. import theme
from ..widgets import PageHeader, button, confirm, fill_table, fit_columns, hbox, info, make_table, run_async, selected_text
from .base import Page


class SecurityPage(Page):
    title = "Users & Security"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.root.addWidget(PageHeader("Users & Security", "Accounts, groups, active sessions and login history"))
        self.tabs = QTabWidget()
        self.root.addWidget(self.tabs, 1)

        w = QWidget()
        v = QVBoxLayout(w)
        self.show_system = QCheckBox("Show system accounts")
        self.show_system.toggled.connect(lambda _: self.refresh())
        v.addLayout(hbox(self.show_system, None, button("Lock", slot=lambda: self.lock(True)),
                         button("Unlock", slot=lambda: self.lock(False)),
                         button("Add to group…", slot=self.add_group), button("Refresh", slot=self.refresh)))
        self.users = make_table(["User", "UID", "GID", "Name", "Home", "Shell", "Login", "Locked"], stretch=4)
        fit_columns(self.users, [150, 70, 70, 0, 200, 170, 70, 70])
        v.addWidget(self.users)
        self.tabs.addTab(w, "Users")

        self.groups = make_table(["Group", "GID", "Members"], stretch=2)
        fit_columns(self.groups, [160, 80, 0])
        self.tabs.addTab(self.groups, "Groups")

        self.sessions = self._text()
        self.tabs.addTab(self.sessions, "Sessions & logins")
        self.failed = self._text()
        self.tabs.addTab(self.failed, "Failed logins")

    @staticmethod
    def _text() -> QPlainTextEdit:
        t = QPlainTextEdit()
        t.setObjectName("log")
        t.setReadOnly(True)
        return t

    def refresh(self) -> None:
        ex = self.ctx.ex
        sys_acc = self.show_system.isChecked()
        run_async(lambda: users.list_users(ex, sys_acc), self._users, self.fail)
        run_async(lambda: users.list_groups(ex), self._groups, self.fail)
        run_async(lambda: "== Active sessions ==\n" + users.sessions(ex) + "\n== Recent logins ==\n" + users.logins(ex),
                  self.sessions.setPlainText, self.fail)
        run_async(lambda: users.failed_logins(ex) or "(none or insufficient privileges)",
                  self.failed.setPlainText, self.fail)

    def _users(self, rows) -> None:
        fill_table(self.users, [[u["user"], (str(u["uid"]), u["uid"]), u["gid"], u["name"], u["home"], u["shell"],
                                 "yes" if u["login"] else "no",
                                 ("LOCKED", 1, theme.BAD) if u["locked"] else ("no", 0)] for u in rows])

    def _groups(self, rows) -> None:
        fill_table(self.groups, [[g["group"], (str(g["gid"]), g["gid"]), g["members"]] for g in rows])

    def _done(self, res) -> None:
        if not res.ok:
            info(self, "Users", res.err or res.out, error=True)
        self.refresh()

    def lock(self, lock_it: bool) -> None:
        user = selected_text(self.users)
        if not user:
            info(self, "Users", "Select a user first.")
            return
        if not confirm(self, "Confirm", f"{'Lock' if lock_it else 'Unlock'} account {user} on {self.ctx.host}?", True,
                       self.ctx.cfg.get("confirm_destructive", True)):
            return
        ex = self.ctx.ex
        run_async(lambda: users.lock(ex, user, lock_it), self._done, self.fail)

    def add_group(self) -> None:
        user = selected_text(self.users)
        if not user:
            info(self, "Users", "Select a user first.")
            return
        group, ok = QInputDialog.getText(self, "Add to group", f"Group for {user}:")
        if ok and group.strip():
            ex = self.ctx.ex
            run_async(lambda: users.add_to_group(ex, user, group.strip()), self._done, self.fail)
