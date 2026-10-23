from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow, QStackedWidget,
                               QSystemTrayIcon, QVBoxLayout, QWidget)

from .. import APP_NAME, __version__
from . import theme
from .context import AppContext
from .pages.audit import AuditPage
from .pages.base import Page
from .pages.containers import ContainersPage
from .pages.dashboard import DashboardPage
from .pages.logs import LogsPage
from .pages.network import NetworkPage
from .pages.processes import ProcessesPage
from .pages.scheduler import SchedulerPage
from .pages.security import SecurityPage
from .pages.servers import ServersPage
from .pages.services import ServicesPage
from .pages.settings import SettingsPage
from .pages.storage import StoragePage
from .pages.terminal import TerminalPage
from .pages.updates import UpdatesPage
from .widgets import button


def app_icon() -> QIcon:
    pm = QPixmap(128, 128)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(theme.ACCENT))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(8, 8, 112, 112, 24, 24)
    p.setBrush(QColor("white"))
    for y in (34, 56, 78):
        p.drawRoundedRect(30, y, 68, 14, 5, 5)
    p.end()
    return QIcon(pm)


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        w = ctx.cfg.get("window", {})
        self.resize(w.get("width", 1360), w.get("height", 860))

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # sidebar -------------------------------------------------------
        side = QWidget()
        side.setFixedWidth(220)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)
        brand = QLabel(f"  {APP_NAME}")
        brand.setStyleSheet(f"font-size: 17px; font-weight: 700; padding: 16px 12px 10px 12px; background: {theme.PANEL};")
        sl.addWidget(brand)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        sl.addWidget(self.nav, 1)
        ver = QLabel(f"v{__version__}")
        ver.setObjectName("muted")
        ver.setStyleSheet(f"padding: 8px 16px; background: {theme.PANEL};")
        sl.addWidget(ver)
        outer.addWidget(side)

        # content -------------------------------------------------------
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self._build_topbar())
        self.stack = QStackedWidget()
        rl.addWidget(self.stack, 1)
        outer.addWidget(right, 1)

        self.pages: list[Page] = []
        for cls in (DashboardPage, ServicesPage, ProcessesPage, LogsPage, StoragePage, NetworkPage, ContainersPage,
                    SecurityPage, SchedulerPage, UpdatesPage, TerminalPage, ServersPage, AuditPage, SettingsPage):
            self._add_page(cls(ctx))
        self.nav.currentRowChanged.connect(self._switch)
        self.nav.setCurrentRow(0)
        for i in range(min(9, len(self.pages))):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self, activated=lambda i=i: self.nav.setCurrentRow(i))
        QShortcut(QKeySequence("F5"), self, activated=self._refresh_current)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._refresh_current)

        # status / tray ---------------------------------------------------
        self.conn_label = QLabel("")
        self.alert_label = QLabel("")
        self.statusBar().addWidget(self.conn_label, 1)
        self.statusBar().addPermanentWidget(self.alert_label)
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(app_icon(), self)
            self.tray.setToolTip(APP_NAME)
            self.tray.show()

        ctx.message.connect(self._on_message)
        ctx.alert_raised.connect(self._on_alert)
        ctx.snapshot.connect(self._on_snapshot)
        ctx.monitor_error.connect(self._on_monitor_error)
        ctx.settings_changed.connect(self._reload_hosts)
        ctx.host_changed.connect(lambda n: self._set_host_combo(n))

    # -- construction helpers ------------------------------------------
    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(f"background: {theme.PANEL}; border-bottom: 1px solid {theme.BORDER};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(18, 8, 18, 8)
        self.page_title = QLabel("")
        self.page_title.setStyleSheet("font-weight: 600; font-size: 14px; border: none;")
        lay.addWidget(self.page_title)
        lay.addStretch(1)
        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color: {theme.MUTED}; border: none;")
        lay.addWidget(self.dot)
        lay.addWidget(QLabel("Server:"))
        self.host_combo = QComboBox()
        self.host_combo.setMinimumWidth(200)
        self.host_combo.addItems(self.ctx.hosts.names())
        self.host_combo.setCurrentText(self.ctx.host)
        self.host_combo.currentTextChanged.connect(self.ctx.set_host)
        lay.addWidget(self.host_combo)
        lay.addWidget(button("Refresh", slot=self._refresh_current))
        return bar

    def _add_page(self, page: Page) -> None:
        self.pages.append(page)
        self.stack.addWidget(page)
        self.nav.addItem(QListWidgetItem(page.title))

    # -- slots -------------------------------------------------------------
    def _switch(self, row: int) -> None:
        if row < 0:
            return
        current = self.stack.currentWidget()
        if isinstance(current, Page):
            current.deactivated()
        self.stack.setCurrentIndex(row)
        page = self.pages[row]
        self.page_title.setText(page.title)
        page.activated()

    def _refresh_current(self) -> None:
        w = self.stack.currentWidget()
        if isinstance(w, Page):
            w.refresh()

    def _set_host_combo(self, name: str) -> None:
        self.host_combo.blockSignals(True)
        self.host_combo.setCurrentText(name)
        self.host_combo.blockSignals(False)
        self.dot.setStyleSheet(f"color: {theme.MUTED}; border: none;")
        self.conn_label.setText(f"Connecting to {name}…")

    def _reload_hosts(self) -> None:
        self.host_combo.blockSignals(True)
        self.host_combo.clear()
        self.host_combo.addItems(self.ctx.hosts.names())
        self.host_combo.setCurrentText(self.ctx.host)
        self.host_combo.blockSignals(False)

    def _on_message(self, text: str, level: str) -> None:
        self.statusBar().showMessage(text, 8000)

    def _on_snapshot(self, s: dict) -> None:
        self.dot.setStyleSheet(f"color: {theme.GOOD}; border: none;")
        self.conn_label.setText(f"{s['hostname']} · {s['os']} · connected")
        n = len(self.ctx.engine().active)
        self.alert_label.setText(f"{n} active alert{'s' if n != 1 else ''}" if n else "No alerts")
        self.alert_label.setStyleSheet(f"color: {theme.BAD if n else theme.MUTED};")

    def _on_monitor_error(self, msg: str) -> None:
        self.dot.setStyleSheet(f"color: {theme.BAD}; border: none;")
        self.conn_label.setText(f"{self.ctx.host}: {msg.splitlines()[0] if msg else 'unreachable'}")

    def _on_alert(self, alert: dict) -> None:
        if self.tray:
            icon = QSystemTrayIcon.Critical if alert["level"] == "critical" else QSystemTrayIcon.Warning
            self.tray.showMessage(f"{APP_NAME}: {alert['host']}", alert["message"], icon, 8000)

    def closeEvent(self, ev) -> None:
        self.ctx.cfg.set("window", {"width": self.width(), "height": self.height()})
        super().closeEvent(ev)
