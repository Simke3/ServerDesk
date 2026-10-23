"""Application stylesheet (dark, restrained, enterprise look)."""

BG = "#0f1419"
PANEL = "#161c24"
PANEL_ALT = "#1b232d"
BORDER = "#26303c"
TEXT = "#d7dee8"
MUTED = "#7d8a9b"
ACCENT = "#3b82f6"
GOOD = "#22c55e"
WARN = "#f59e0b"
BAD = "#ef4444"


def level_color(pct: float, warn: float = 70, bad: float = 90) -> str:
    return BAD if pct >= bad else WARN if pct >= warn else GOOD


STYLESHEET = f"""
* {{ font-family: "Inter", "Noto Sans", "DejaVu Sans", sans-serif; font-size: 13px; color: {TEXT}; }}
QMainWindow, QWidget#root {{ background: {BG}; }}
QWidget {{ background: transparent; }}
QDialog, QMessageBox {{ background: {PANEL}; }}
QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px; }}
QLabel#title {{ font-size: 20px; font-weight: 600; }}
QLabel#subtitle, QLabel#muted {{ color: {MUTED}; }}
QLabel#cardTitle {{ color: {MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 1px; }}
QLabel#bigValue {{ font-size: 24px; font-weight: 600; }}

QListWidget#nav {{ background: {PANEL}; border: none; border-right: 1px solid {BORDER}; outline: 0; padding: 6px; }}
QListWidget#nav::item {{ padding: 9px 12px; border-radius: 6px; margin: 1px 0; color: {MUTED}; }}
QListWidget#nav::item:hover {{ background: {PANEL_ALT}; color: {TEXT}; }}
QListWidget#nav::item:selected {{ background: {ACCENT}; color: white; }}

QPushButton {{ background: {PANEL_ALT}; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 14px; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: {MUTED}; border-color: {BORDER}; }}
QPushButton#primary {{ background: {ACCENT}; border-color: {ACCENT}; color: white; }}
QPushButton#primary:hover {{ background: #2f6fe0; }}
QPushButton#danger {{ background: transparent; border-color: {BAD}; color: {BAD}; }}
QPushButton#danger:hover {{ background: {BAD}; color: white; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {PANEL}; border: 1px solid {BORDER}; border-radius: 6px; padding: 5px 8px;
    selection-background-color: {ACCENT}; }}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QSpinBox:focus {{ border-color: {ACCENT}; }}
QComboBox QAbstractItemView {{ background: {PANEL}; border: 1px solid {BORDER}; selection-background-color: {ACCENT}; }}
QPlainTextEdit#mono, QPlainTextEdit#log {{ font-family: "JetBrains Mono", "DejaVu Sans Mono", "Monospace"; font-size: 12px; background: #0b0f14; }}

QTableWidget {{ background: {PANEL}; alternate-background-color: {PANEL_ALT}; border: 1px solid {BORDER};
    border-radius: 6px; gridline-color: transparent; selection-background-color: #1e3a68; selection-color: white; }}
QTableWidget::item {{ padding: 3px 6px; border: none; }}
QHeaderView::section {{ background: {PANEL_ALT}; color: {MUTED}; padding: 6px 8px; border: none;
    border-bottom: 1px solid {BORDER}; font-weight: 600; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 6px; top: -1px; }}
QTabBar::tab {{ background: transparent; padding: 8px 16px; color: {MUTED}; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}

QProgressBar {{ background: {BORDER}; border: none; border-radius: 4px; height: 8px; text-align: center; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QStatusBar {{ background: {PANEL}; border-top: 1px solid {BORDER}; color: {MUTED}; }}
QToolTip {{ background: {PANEL_ALT}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {BORDER}; border-radius: 3px; background: {PANEL}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QSplitter::handle {{ background: {BORDER}; }}
"""
