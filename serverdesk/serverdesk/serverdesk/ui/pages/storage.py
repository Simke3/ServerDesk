from __future__ import annotations

from PySide6.QtWidgets import QLabel, QLineEdit, QTabWidget, QTableWidgetItem, QVBoxLayout, QWidget

from ...core import disks
from ...core.metrics import human_bytes
from ..widgets import PageHeader, button, fill_table, fit_columns, hbox, info, make_table, run_async, usage_bar
from .base import Page


class StoragePage(Page):
    title = "Storage"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.root.addWidget(PageHeader("Storage", "Filesystems, block devices, inodes and directory usage"))
        self.tabs = QTabWidget()
        self.root.addWidget(self.tabs, 1)

        self.fs = make_table(["Mount", "Device", "Type", "Size", "Used", "Free", "Usage"], stretch=0)
        fit_columns(self.fs, [0, 260, 80, 100, 100, 100, 160])
        self.tabs.addTab(self.fs, "Filesystems")
        self.dev = make_table(["Name", "Size", "Type", "FS", "Mount", "Model", "Media", "UUID"], stretch=7)
        fit_columns(self.dev, [180, 100, 80, 80, 200, 180, 90, 0])
        self.dev.setSortingEnabled(False)
        self.tabs.addTab(self.dev, "Block devices")
        self.ino = make_table(["Mount", "Device", "Inodes", "Used", "Free", "Use %"], stretch=0)
        self.tabs.addTab(self.ino, "Inodes")

        usage = QWidget()
        v = QVBoxLayout(usage)
        self.path = QLineEdit("/var")
        self.path.returnPressed.connect(self.analyze)
        self.lbl = QLabel("")
        self.lbl.setObjectName("muted")
        v.addLayout(hbox(QLabel("Path"), self.path, button("Analyze", "primary", slot=self.analyze), self.lbl))
        self.du = make_table(["Size", "Path"], stretch=1)
        fit_columns(self.du, [120, 0])
        v.addWidget(self.du)
        self.tabs.addTab(usage, "Directory usage")

    def refresh(self) -> None:
        ex = self.ctx.ex
        run_async(lambda: disks.filesystems(ex), self._fs, self.fail)
        run_async(lambda: disks.block_devices(ex), self._dev, self.fail)
        run_async(lambda: disks.inode_usage(ex), self._ino, self.fail)

    def _fs(self, rows) -> None:
        self.fs.setSortingEnabled(False)
        self.fs.setRowCount(len(rows))
        for r, d in enumerate(rows):
            for c, val in enumerate([d["mount"], d["device"], d["fstype"], human_bytes(d["size"]),
                                     human_bytes(d["used"]), human_bytes(d["avail"])]):
                self.fs.setItem(r, c, QTableWidgetItem(val))
            self.fs.setCellWidget(r, 6, usage_bar(d["pct"]))
            self.fs.item(r, 0).setToolTip(f"{d['pct']:.1f}% used")

    def _dev(self, rows) -> None:
        fill_table(self.dev, [[r["name"], human_bytes(r["size"]), r["type"], r["fstype"], r["mount"], r["model"],
                               r["rota"], r["uuid"]] for r in rows])

    def _ino(self, rows) -> None:
        fill_table(self.ino, [[r["mount"], r["device"], f"{r['inodes']:,}", f"{r['used']:,}", f"{r['free']:,}",
                               (r["pct"], int(r["pct"].rstrip("%")) if r["pct"].rstrip("%").isdigit() else 0)]
                              for r in rows])

    def analyze(self) -> None:
        path = self.path.text().strip() or "/"
        ex = self.ctx.ex
        self.lbl.setText("Analyzing… (large trees can take a while)")

        def done(rows):
            self.lbl.setText(f"{len(rows)} entries")
            fill_table(self.du, [[(human_bytes(s), s), p] for s, p in rows], key_col=1)

        def err(exc):
            self.lbl.setText("")
            info(self, "Directory usage", str(exc), error=True)

        run_async(lambda: disks.directory_usage(ex, path), done, err)
