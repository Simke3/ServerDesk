from __future__ import annotations

from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QLineEdit, QPlainTextEdit

from ...core import audit
from ...core.executor import SshExecutor
from ..widgets import LogHighlighter, PageHeader, button, hbox
from .base import Page


class TerminalPage(Page):
    title = "Terminal"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.root.addWidget(PageHeader("Terminal", "Command shell on the selected server (line based, no full-screen programs)"))
        self.out = QPlainTextEdit()
        self.out.setObjectName("log")
        self.out.setReadOnly(True)
        self.out.setMaximumBlockCount(20000)
        self._hl = LogHighlighter(self.out.document())
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a command and press Enter  (↑/↓ history)")
        self.input.returnPressed.connect(self.send)
        self.input.installEventFilter(self)
        self.root.addWidget(self.out, 1)
        self.root.addLayout(hbox(self.input, button("Clear", slot=self.out.clear),
                                 button("Restart shell", slot=self.start_shell)))
        self.history: list[str] = []
        self.hpos = 0
        self.proc: QProcess | None = None

    def on_host_changed(self) -> None:
        # Drop the old shell; a new one starts when the page is shown again.
        if self.proc is not None:
            self.proc.kill()
            self.proc.deleteLater()
            self.proc = None
        self.out.clear()

    def on_show(self) -> None:
        if self.proc is None or self.proc.state() == QProcess.NotRunning:
            self.start_shell()
        self.input.setFocus()

    def start_shell(self) -> None:
        if self.proc is not None:
            self.proc.kill()
            self.proc.deleteLater()
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyRead.connect(self._read)
        self.proc.finished.connect(lambda code, _s: self._append(f"\n[shell exited with code {code}]\n"))
        ex = self.ctx.ex
        if isinstance(ex, SshExecutor):
            argv = ex.interactive_argv() + ["TERM=dumb bash --noprofile --norc -s"]
            self.proc.start(argv[0], argv[1:])
        else:
            self.proc.start("bash", ["--noprofile", "--norc", "-s"])
        self.out.clear()
        self._append(f"Connected shell: {self.ctx.host}\n")

    def _read(self) -> None:
        data = bytes(self.proc.readAll()).decode("utf-8", "replace")
        self._append(data)

    def _append(self, text: str) -> None:
        self.out.moveCursor(QTextCursor.End)
        self.out.insertPlainText(text)
        self.out.moveCursor(QTextCursor.End)

    def send(self) -> None:
        cmd = self.input.text()
        if not cmd.strip() or self.proc is None:
            return
        self.history.append(cmd)
        self.hpos = len(self.history)
        self.input.clear()
        self._append(f"$ {cmd}\n")
        self.proc.write((cmd + "\n").encode())
        audit.record(self.ctx.host, "terminal.command", cmd)

    def eventFilter(self, obj, ev):
        if obj is self.input and isinstance(ev, QKeyEvent) and ev.type() == ev.Type.KeyPress:
            if ev.key() == Qt.Key_Up and self.history:
                self.hpos = max(0, self.hpos - 1)
                self.input.setText(self.history[self.hpos])
                return True
            if ev.key() == Qt.Key_Down and self.history:
                self.hpos = min(len(self.history), self.hpos + 1)
                self.input.setText(self.history[self.hpos] if self.hpos < len(self.history) else "")
                return True
        return super().eventFilter(obj, ev)
