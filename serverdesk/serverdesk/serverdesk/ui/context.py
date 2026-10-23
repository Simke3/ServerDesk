"""Shared application state: current host, configuration and background monitor."""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from ..core.alerts import AlertEngine
from ..core.config import Config
from ..core.executor import Executor
from ..core.hosts import HostStore, LOCAL_NAME
from ..core.metrics import MetricsCollector
from .widgets import run_async


class AppContext(QObject):
    host_changed = Signal(str)
    message = Signal(str, str)       # text, level (info|warn|error)
    snapshot = Signal(dict)
    monitor_error = Signal(str)
    alert_raised = Signal(dict)
    settings_changed = Signal()

    def __init__(self):
        super().__init__()
        self.cfg = Config()
        self.hosts = HostStore(self.cfg)
        name = self.cfg.get("last_host", LOCAL_NAME)
        self.host = name if name in self.hosts.names() else LOCAL_NAME
        self._collectors: dict[str, MetricsCollector] = {}
        self._engines: dict[str, AlertEngine] = {}
        self.last_snapshot: dict | None = None
        self._busy = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # -- host handling ------------------------------------------------
    @property
    def ex(self) -> Executor:
        return self.hosts.executor(self.host)

    def set_host(self, name: str) -> None:
        if name == self.host:
            return
        self.host = name
        self.cfg.set("last_host", name)
        self.last_snapshot = None
        self.host_changed.emit(name)
        self._tick()

    def engine(self) -> AlertEngine:
        return self._engines.setdefault(self.host, AlertEngine())

    def notify(self, text: str, level: str = "info") -> None:
        self.message.emit(text, level)

    # -- monitor ------------------------------------------------------
    def start_monitor(self) -> None:
        self.apply_settings()
        self._tick()

    def apply_settings(self) -> None:
        self._timer.start(max(1, int(self.cfg.get("refresh_seconds", 2))) * 1000)
        self.settings_changed.emit()

    def _tick(self) -> None:
        if self._busy:
            return
        self._busy = True
        host, ex = self.host, self.ex
        collector = self._collectors.setdefault(host, MetricsCollector(ex))
        collector.ex = ex

        def work():
            return host, collector.snapshot(), collector

        run_async(work, self._on_snapshot, self._on_error)

    def _on_snapshot(self, payload) -> None:
        self._busy = False
        host, snap, collector = payload
        if host != self.host:
            return
        snap["history"] = collector.history
        self.last_snapshot = snap
        if self.cfg.get("alerts_enabled", True):
            for a in self.engine().evaluate(snap, self.cfg.get("thresholds")):
                self.alert_raised.emit(a)
        self.snapshot.emit(snap)

    def _on_error(self, exc) -> None:
        self._busy = False
        self.monitor_error.emit(str(exc))

    def collector_history(self):
        c = self._collectors.get(self.host)
        return c.history if c else None
