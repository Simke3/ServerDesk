"""Base class for navigable pages."""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..context import AppContext


class Page(QWidget):
    title = "Page"
    needs_refresh_on_host_change = True

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(22, 18, 22, 14)
        self.root.setSpacing(12)
        self._visible = False
        ctx.host_changed.connect(self._host_changed)

    def _host_changed(self, _name: str) -> None:
        self.on_host_changed()
        if self._visible:
            self.refresh()

    # Hooks ---------------------------------------------------------
    def on_host_changed(self) -> None: ...
    def on_show(self) -> None: ...
    def on_hide(self) -> None: ...
    def refresh(self) -> None: ...

    # Called by the main window ------------------------------------
    def activated(self) -> None:
        self._visible = True
        self.on_show()
        self.refresh()

    def deactivated(self) -> None:
        self._visible = False
        self.on_hide()

    def fail(self, exc) -> None:
        self.ctx.notify(str(exc), "error")
