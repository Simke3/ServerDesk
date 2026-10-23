from __future__ import annotations

from PySide6.QtWidgets import QLabel, QLineEdit, QPlainTextEdit, QTabWidget, QVBoxLayout, QWidget

from ...core import scheduler
from ..widgets import PageHeader, button, confirm, fill_table, fit_columns, hbox, info, make_table, run_async
from .base import Page

CRON_HELP = "# m h dom mon dow  command\n"


class SchedulerPage(Page):
    title = "Scheduler"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.root.addWidget(PageHeader("Scheduler", "cron jobs and systemd timers"))
        self.tabs = QTabWidget()
        self.root.addWidget(self.tabs, 1)

        w = QWidget()
        v = QVBoxLayout(w)
        self.cron_user = QLineEdit()
        self.cron_user.setPlaceholderText("crontab owner (empty = current/login user)")
        self.cron_user.setFixedWidth(320)
        v.addLayout(hbox(QLabel("Crontab of"), self.cron_user, None, button("Reload", slot=self.load_cron),
                         button("Save crontab", "primary", slot=self.save_cron)))
        self.editor = QPlainTextEdit()
        self.editor.setObjectName("mono")
        v.addWidget(self.editor, 1)
        self.sys_files = QPlainTextEdit()
        self.sys_files.setObjectName("log")
        self.sys_files.setReadOnly(True)
        self.sys_files.setMaximumHeight(120)
        v.addWidget(QLabel("System cron directories"))
        v.addWidget(self.sys_files)
        self.tabs.addTab(w, "Crontab")

        self.timers = make_table(["Schedule", "Timer", "Activates"], stretch=0)
        fit_columns(self.timers, [0, 260, 260])
        self.tabs.addTab(self.timers, "systemd timers")

    def refresh(self) -> None:
        self.load_cron()
        ex = self.ctx.ex
        run_async(lambda: scheduler.timers(ex), lambda rows: fill_table(
            self.timers, [[r["schedule"], r["unit"], r["activates"]] for r in rows], key_col=1), self.fail)
        run_async(lambda: scheduler.system_cron_files(ex), self.sys_files.setPlainText, self.fail)

    def load_cron(self) -> None:
        ex = self.ctx.ex
        user = self.cron_user.text().strip()
        run_async(lambda: scheduler.get_crontab(ex, user), lambda t: self.editor.setPlainText(t or CRON_HELP), self.fail)

    def save_cron(self) -> None:
        if not confirm(self, "Save crontab", f"Replace the crontab on {self.ctx.host}?", False,
                       self.ctx.cfg.get("confirm_destructive", True)):
            return
        ex = self.ctx.ex
        user = self.cron_user.text().strip()
        text = self.editor.toPlainText()

        def done(res):
            if res.ok:
                self.ctx.notify("Crontab saved", "info")
            else:
                info(self, "Crontab", res.err or res.out, error=True)

        run_async(lambda: scheduler.set_crontab(ex, text, user), done, self.fail)
