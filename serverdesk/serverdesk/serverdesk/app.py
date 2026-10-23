"""Application bootstrap."""
from __future__ import annotations

import signal
import sys

from PySide6.QtWidgets import QApplication

from . import APP_NAME
from .ui import theme
from .ui.context import AppContext
from .ui.main_window import MainWindow
from .ui.widgets import init_threading


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("ServerDesk")
    app.setDesktopFileName("serverdesk")
    app.setStyleSheet(theme.STYLESHEET)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    init_threading()
    ctx = AppContext()
    win = MainWindow(ctx)
    win.show()
    ctx.start_monitor()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
