"""Reusable widgets and threading helpers."""
from __future__ import annotations

import re
from collections import deque
from typing import Callable, Iterable

from PySide6.QtCore import QObject, QRectF, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
                               QProgressBar, QPushButton, QSizePolicy, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from . import theme

HISTORY_POINTS = 120

# --------------------------------------------------------------------------- threading


class _Dispatcher(QObject):
    """Lives in the GUI thread; delivers worker results through queued signals."""
    deliver = Signal(object, object)

    def __init__(self):
        super().__init__()
        self.deliver.connect(self._on_deliver)

    @Slot(object, object)
    def _on_deliver(self, callback, payload):
        try:
            callback(payload)
        except RuntimeError:
            pass  # target widget already destroyed


_dispatcher: _Dispatcher | None = None


def init_threading() -> None:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = _Dispatcher()
        QThreadPool.globalInstance().setMaxThreadCount(12)


class _Task(QRunnable):
    def __init__(self, fn, ok, err):
        super().__init__()
        self.fn, self.ok, self.err = fn, ok, err

    def run(self):
        try:
            result = self.fn()
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            if self.err:
                _dispatcher.deliver.emit(self.err, exc)
            return
        if self.ok:
            _dispatcher.deliver.emit(self.ok, result)


def run_async(fn: Callable, ok: Callable | None = None, err: Callable | None = None) -> None:
    """Run fn in the thread pool; ok(result) / err(exception) run in the GUI thread."""
    QThreadPool.globalInstance().start(_Task(fn, ok, err))


# --------------------------------------------------------------------------- tables


class SortItem(QTableWidgetItem):
    def __lt__(self, other):
        a, b = self.data(Qt.UserRole), other.data(Qt.UserRole)
        if a is not None and b is not None:
            try:
                return a < b
            except TypeError:
                pass
        return self.text().lower() < other.text().lower()


def make_table(headers: list[str], stretch: int | None = None, multi: bool = False) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.ExtendedSelection if multi else QAbstractItemView.SingleSelection)
    t.setAlternatingRowColors(True)
    t.setShowGrid(False)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(28)
    t.setSortingEnabled(True)
    t.setWordWrap(False)
    hh = t.horizontalHeader()
    hh.setHighlightSections(False)
    hh.setSectionResizeMode(QHeaderView.Interactive)
    hh.setStretchLastSection(stretch is None)
    if stretch is not None:
        hh.setSectionResizeMode(stretch, QHeaderView.Stretch)
    return t


def fit_columns(table: QTableWidget, widths: Iterable[int]) -> None:
    for i, w in enumerate(widths):
        if w:
            table.setColumnWidth(i, w)


def fill_table(table: QTableWidget, rows: list[list], key_col: int = 0) -> None:
    """Fill rows. A cell is a str or a tuple (text, sort_key[, color]). Keeps selection and scroll."""
    sel_key = None
    cur = table.currentRow()
    if cur >= 0 and table.item(cur, key_col):
        sel_key = table.item(cur, key_col).text()
    vbar = table.verticalScrollBar().value()
    sorting = table.isSortingEnabled()
    order_col = table.horizontalHeader().sortIndicatorSection()
    order = table.horizontalHeader().sortIndicatorOrder()
    table.setSortingEnabled(False)
    table.setUpdatesEnabled(False)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            text, key, color = cell, None, None
            if isinstance(cell, tuple):
                text, key = cell[0], cell[1]
                color = cell[2] if len(cell) > 2 else None
            item = SortItem(str(text))
            if key is not None:
                item.setData(Qt.UserRole, key)
            if color:
                item.setForeground(QColor(color))
            table.setItem(r, c, item)
    table.setSortingEnabled(sorting)
    if sorting:
        table.sortItems(order_col if order_col >= 0 else 0, order)
    table.setUpdatesEnabled(True)
    if sel_key is not None:
        for r in range(table.rowCount()):
            it = table.item(r, key_col)
            if it and it.text() == sel_key:
                table.selectRow(r)
                break
    table.verticalScrollBar().setValue(vbar)


def selected_text(table: QTableWidget, col: int = 0) -> str | None:
    r = table.currentRow()
    if r < 0:
        return None
    it = table.item(r, col)
    return it.text() if it else None


def filter_rows(table: QTableWidget, needle: str) -> None:
    needle = needle.lower().strip()
    for r in range(table.rowCount()):
        hit = not needle
        if not hit:
            for c in range(table.columnCount()):
                it = table.item(r, c)
                if it and needle in it.text().lower():
                    hit = True
                    break
        table.setRowHidden(r, not hit)


# --------------------------------------------------------------------------- dialogs


def confirm(parent, title: str, text: str, destructive: bool = True, enabled: bool = True) -> bool:
    if not enabled:
        return True
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning if destructive else QMessageBox.Question)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    box.setDefaultButton(QMessageBox.No)
    return box.exec() == QMessageBox.Yes


def info(parent, title: str, text: str, error: bool = False) -> None:
    (QMessageBox.critical if error else QMessageBox.information)(parent, title, text)


# --------------------------------------------------------------------------- layout helpers


def button(text: str, kind: str = "", tip: str = "", slot: Callable | None = None) -> QPushButton:
    b = QPushButton(text)
    if kind:
        b.setObjectName(kind)
    if tip:
        b.setToolTip(tip)
    if slot:
        b.clicked.connect(lambda _=False: slot())
    return b


def hbox(*widgets, spacing: int = 8, margins=(0, 0, 0, 0)) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for w in widgets:
        if w is None:
            lay.addStretch(1)
        else:
            lay.addWidget(w)
    return lay


class Card(QFrame):
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(14, 12, 14, 12)
        self.lay.setSpacing(8)
        if title:
            t = QLabel(title.upper())
            t.setObjectName("cardTitle")
            self.lay.addWidget(t)


class StatCard(Card):
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.value = QLabel("—")
        self.value.setObjectName("bigValue")
        self.sub = QLabel("")
        self.sub.setObjectName("muted")
        self.lay.addWidget(self.value)
        self.lay.addWidget(self.sub)

    def set(self, value: str, sub: str = "", color: str | None = None) -> None:
        self.value.setText(value)
        self.sub.setText(sub)
        self.value.setStyleSheet(f"color: {color};" if color else "")


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 4)
        lay.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("title")
        lay.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("subtitle")
            lay.addWidget(s)


def usage_bar(pct: float) -> QProgressBar:
    bar = QProgressBar()
    bar.setRange(0, 1000)
    bar.setValue(int(max(0, min(100, pct)) * 10))
    bar.setTextVisible(False)
    bar.setFixedHeight(8)
    bar.setStyleSheet(f"QProgressBar::chunk {{ background: {theme.level_color(pct)}; border-radius: 4px; }}")
    return bar


# --------------------------------------------------------------------------- custom painting


class Gauge(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title, self.value, self.text, self.sub = title, 0.0, "—", ""
        self.setMinimumSize(150, 150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_value(self, pct: float, text: str | None = None, sub: str = "") -> None:
        self.value = max(0.0, min(100.0, pct))
        self.text = text if text is not None else f"{pct:.0f}%"
        self.sub = sub
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        side = min(w, h - 26) - 16
        rect = QRectF((w - side) / 2, 8, side, side)
        pen = QPen(QColor(theme.BORDER), 10, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, 225 * 16, -270 * 16)
        pen.setColor(QColor(theme.level_color(self.value)))
        p.setPen(pen)
        p.drawArc(rect, 225 * 16, int(-270 * 16 * self.value / 100))
        p.setPen(QColor(theme.TEXT))
        f = QFont(self.font())
        f.setPointSize(16)
        f.setBold(True)
        p.setFont(f)
        p.drawText(rect, Qt.AlignCenter, self.text)
        f.setPointSize(9)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(0, h - 24, w, 14), Qt.AlignCenter, self.title.upper())
        if self.sub:
            p.drawText(QRectF(rect.left(), rect.center().y() + 14, rect.width(), 14), Qt.AlignCenter, self.sub)


class Sparkline(QWidget):
    """Line chart over a rolling history. Supports one or two series."""

    def __init__(self, title: str, fixed_max: float | None = 100.0, formatter=None, parent=None):
        super().__init__(parent)
        self.title, self.fixed_max = title, fixed_max
        self.fmt = formatter or (lambda v: f"{v:.0f}%")
        self.series: list[tuple[deque, str]] = []
        self.setMinimumHeight(110)

    def set_series(self, *series: tuple[deque, str]) -> None:
        self.series = list(series)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        top, bottom = 22, 6
        plot = QRectF(4, top, w - 8, h - top - bottom)
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(4, 0, w - 8, 18), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        if self.series and self.series[0][0]:
            cur = " / ".join(self.fmt(s[0][-1]) for s in self.series if s[0])
            p.setPen(QColor(theme.TEXT))
            p.drawText(QRectF(4, 0, w - 8, 18), Qt.AlignRight | Qt.AlignVCenter, cur)
        p.setPen(QPen(QColor(theme.BORDER), 1))
        for frac in (0.0, 0.5, 1.0):
            y = plot.top() + plot.height() * frac
            p.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))
        if not self.series:
            return
        vmax = self.fixed_max or max([max(s[0]) for s in self.series if s[0]] + [1.0]) * 1.15
        n = max(len(s[0]) for s in self.series)
        if n < 2:
            return
        step = plot.width() / (HISTORY_POINTS - 1)
        for data, color in self.series:
            if len(data) < 2:
                continue
            path = QPainterPath()
            pts = []
            for i, v in enumerate(data):
                x = plot.right() - (len(data) - 1 - i) * step
                y = plot.bottom() - plot.height() * min(v / vmax, 1.0)
                pts.append((x, y))
            path.moveTo(*pts[0])
            for x, y in pts[1:]:
                path.lineTo(x, y)
            fill = QPainterPath(path)
            fill.lineTo(pts[-1][0], plot.bottom())
            fill.lineTo(pts[0][0], plot.bottom())
            fill.closeSubpath()
            grad = QLinearGradient(0, plot.top(), 0, plot.bottom())
            c = QColor(color)
            c.setAlpha(70)
            grad.setColorAt(0, c)
            c.setAlpha(0)
            grad.setColorAt(1, c)
            p.fillPath(fill, grad)
            p.setPen(QPen(QColor(color), 1.6))
            p.drawPath(path)


class LogHighlighter(QSyntaxHighlighter):
    RULES = [
        (re.compile(r"\b(emerg|alert|crit|critical|fatal|panic|error|err|failed|failure|denied|refused|segfault)\b", re.I), theme.BAD),
        (re.compile(r"\b(warn|warning|timeout|timed out|retry|deprecated)\b", re.I), theme.WARN),
        (re.compile(r"\b(started|success|succeeded|ok|accepted|listening|ready)\b", re.I), theme.GOOD),
        (re.compile(r"^\d{4}-\d{2}-\d{2}T[\d:.+\-]+"), theme.MUTED),
    ]

    def highlightBlock(self, text: str) -> None:
        for rx, color in self.RULES:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            for m in rx.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)
