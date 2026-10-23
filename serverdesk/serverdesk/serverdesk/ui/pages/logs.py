from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QCheckBox, QComboBox, QFileDialog, QLabel, QLineEdit, QPlainTextEdit, QSpinBox

from ...core import logs
from ..widgets import LogHighlighter, PageHeader, button, hbox, info, run_async
from .base import Page


class LogsPage(Page):
    title = "Logs"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.root.addWidget(PageHeader("Logs", "journald and common log files with live follow and highlighting"))
        self.source = QComboBox()
        self.source.addItem("systemd journal")
        self.source.currentIndexChanged.connect(self._source_changed)
        self.unit = QLineEdit()
        self.unit.setPlaceholderText("Unit (e.g. nginx.service)")
        self.unit.setFixedWidth(210)
        self.prio = QComboBox()
        self.prio.addItems(["all priorities"] + list(logs.PRIORITIES))
        self.lines = QSpinBox()
        self.lines.setRange(50, 20000)
        self.lines.setSingleStep(100)
        self.lines.setValue(int(ctx.cfg.get("log_lines", 400)))
        self.since = QComboBox()
        self.since.addItems(["any time", "-15 min", "-1 hour", "-6 hours", "-24 hours", "-7 days"])
        self.follow = QCheckBox("Follow")
        self.follow.toggled.connect(self._toggle_follow)
        self.root.addLayout(hbox(self.source, self.unit, self.prio, self.since, QLabel("Lines"), self.lines,
                                 self.follow, None, button("Refresh", "primary", slot=self.refresh),
                                 button("Save…", slot=self.save)))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search within results…")
        self.search.textChanged.connect(self._render)
        self.root.addWidget(self.search)
        self.view = QPlainTextEdit()
        self.view.setObjectName("log")
        self.view.setReadOnly(True)
        self.view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.view.setMaximumBlockCount(30000)
        self._hl = LogHighlighter(self.view.document())
        self.root.addWidget(self.view, 1)
        self._raw = ""
        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self.refresh)
        self._busy = False

    def on_host_changed(self) -> None:
        while self.source.count() > 1:
            self.source.removeItem(1)
        self._raw = ""
        self.view.clear()

    def on_show(self) -> None:
        ex = self.ctx.ex
        run_async(lambda: logs.available_files(ex), self._set_files)

    def on_hide(self) -> None:
        self._timer.stop()
        self.follow.setChecked(False)

    def _set_files(self, files) -> None:
        current = self.source.currentText()
        self.source.blockSignals(True)
        self.source.clear()
        self.source.addItem("systemd journal")
        self.source.addItems(files)
        idx = self.source.findText(current)
        self.source.setCurrentIndex(max(0, idx))
        self.source.blockSignals(False)
        self._source_changed()

    def _source_changed(self) -> None:
        is_journal = self.source.currentIndex() == 0
        for w in (self.unit, self.prio, self.since):
            w.setEnabled(is_journal)
        self.refresh()

    def _toggle_follow(self, on: bool) -> None:
        self._timer.start() if on else self._timer.stop()

    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        ex = self.ctx.ex
        n = self.lines.value()
        src = self.source.currentText()
        if self.source.currentIndex() == 0:
            unit = self.unit.text().strip()
            prio = self.prio.currentText() if self.prio.currentIndex() > 0 else ""
            since = self.since.currentText() if self.since.currentIndex() > 0 else ""
            fn = lambda: logs.journal(ex, n, unit, prio, since)
        else:
            fn = lambda: logs.tail_file(ex, src, n)
        run_async(fn, self._got, self._err)

    def _err(self, exc) -> None:
        self._busy = False
        self.fail(exc)

    def _got(self, text: str) -> None:
        self._busy = False
        self._raw = text
        self._render()

    def _render(self) -> None:
        text = logs.filter_text(self._raw, self.search.text())
        bar = self.view.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 4
        self.view.setPlainText(text)
        if at_bottom or self.follow.isChecked():
            bar.setValue(bar.maximum())

    def save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save log", "serverdesk-log.txt", "Text (*.txt)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(self.view.toPlainText())
            except OSError as e:
                info(self, "Save failed", str(e), error=True)
