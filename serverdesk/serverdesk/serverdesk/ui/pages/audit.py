from __future__ import annotations

from ...core import audit
from .. import theme
from ..widgets import PageHeader, button, fill_table, fit_columns, hbox, make_table, run_async
from .base import Page


class AuditPage(Page):
    title = "Audit log"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.root.addWidget(PageHeader("Audit log", f"Every administrative action is recorded in {audit.AUDIT_FILE}"))
        self.root.addLayout(hbox(None, button("Refresh", slot=self.refresh)))
        self.table = make_table(["Time", "Operator", "Server", "Result", "Action", "Details"], stretch=5)
        fit_columns(self.table, [170, 120, 150, 70, 170, 0])
        self.table.setSortingEnabled(False)
        self.root.addWidget(self.table, 1)

    def refresh(self) -> None:
        def done(rows):
            fill_table(self.table, [[r[0], r[1], r[2], (r[3], r[3], theme.GOOD if r[3] == "OK" else theme.BAD), r[4], r[5]]
                                    for r in rows], key_col=0)
        run_async(lambda: audit.read(1000), done, self.fail)
