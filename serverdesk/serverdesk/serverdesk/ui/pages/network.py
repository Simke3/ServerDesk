from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QLabel, QLineEdit, QPlainTextEdit, QTabWidget, QVBoxLayout, QWidget)

from ...core import firewall, network
from .. import theme
from ..widgets import (PageHeader, button, confirm, fill_table, fit_columns, filter_rows, hbox, info, make_table,
                       run_async)
from .base import Page


class NetworkPage(Page):
    title = "Network"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.root.addWidget(PageHeader("Network", "Interfaces, listening ports, diagnostics and firewall"))
        self.tabs = QTabWidget()
        self.root.addWidget(self.tabs, 1)

        # interfaces ---------------------------------------------------
        w = QWidget()
        v = QVBoxLayout(w)
        self.ifaces = make_table(["Interface", "State", "MAC", "MTU", "Addresses"], stretch=4)
        fit_columns(self.ifaces, [140, 90, 150, 70, 0])
        v.addWidget(self.ifaces, 2)
        self.routes = QPlainTextEdit()
        self.routes.setObjectName("log")
        self.routes.setReadOnly(True)
        v.addWidget(QLabel("Routes / DNS / socket summary"))
        v.addWidget(self.routes, 1)
        self.tabs.addTab(w, "Interfaces")

        # listening ----------------------------------------------------
        w = QWidget()
        v = QVBoxLayout(w)
        self.port_search = QLineEdit()
        self.port_search.setPlaceholderText("Filter ports / processes…")
        self.port_search.textChanged.connect(lambda t: filter_rows(self.ports, t))
        v.addLayout(hbox(self.port_search, button("Refresh", slot=self.refresh)))
        self.ports = make_table(["Proto", "State", "Local address", "Peer", "Process"], stretch=4)
        fit_columns(self.ports, [70, 90, 260, 220, 0])
        v.addWidget(self.ports)
        self.tabs.addTab(w, "Listening ports")

        # diagnostics --------------------------------------------------
        w = QWidget()
        v = QVBoxLayout(w)
        self.target = QLineEdit("1.1.1.1")
        v.addLayout(hbox(QLabel("Host"), self.target, button("Ping", "primary", slot=lambda: self.diag("ping")),
                         button("Traceroute", slot=lambda: self.diag("trace")),
                         button("DNS lookup", slot=lambda: self.diag("dns"))))
        self.diag_out = QPlainTextEdit()
        self.diag_out.setObjectName("log")
        self.diag_out.setReadOnly(True)
        v.addWidget(self.diag_out)
        self.tabs.addTab(w, "Diagnostics")

        # firewall -----------------------------------------------------
        w = QWidget()
        v = QVBoxLayout(w)
        self.fw_tool = ""
        self.fw_label = QLabel("")
        self.fw_label.setObjectName("muted")
        self.fw_action = QComboBox()
        self.fw_action.addItems(["allow", "deny", "reject", "limit"])
        self.fw_port = QLineEdit()
        self.fw_port.setPlaceholderText("port or port/proto, e.g. 443/tcp")
        self.fw_src = QLineEdit()
        self.fw_src.setPlaceholderText("from (optional): IP or CIDR")
        self.fw_num = QLineEdit()
        self.fw_num.setPlaceholderText("rule #")
        self.fw_num.setFixedWidth(70)
        self.fw_rule_btns = [
            button("Add rule", "primary", slot=self.add_rule),
            button("Delete rule", "danger", slot=self.del_rule),
            button("Enable", slot=lambda: self.fw_toggle(True)),
            button("Disable", "danger", slot=lambda: self.fw_toggle(False)),
        ]
        v.addLayout(hbox(self.fw_label, None, button("Refresh", slot=self.load_firewall)))
        v.addLayout(hbox(self.fw_action, self.fw_port, self.fw_src, self.fw_rule_btns[0], None, self.fw_num,
                         self.fw_rule_btns[1], self.fw_rule_btns[2], self.fw_rule_btns[3]))
        self.fw_out = QPlainTextEdit()
        self.fw_out.setObjectName("log")
        self.fw_out.setReadOnly(True)
        v.addWidget(self.fw_out)
        self.tabs.addTab(w, "Firewall")
        self.tabs.currentChanged.connect(lambda i: self.load_firewall() if i == 3 else None)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        ex = self.ctx.ex
        run_async(lambda: network.interfaces(ex), self._ifaces, self.fail)
        run_async(lambda: network.listening(ex), self._ports, self.fail)

        def routes():
            return "\n".join(["# routes", *network.routes(ex), "", "# dns", *network.dns_servers(ex), "",
                              "# sockets", network.connections_summary(ex)])
        run_async(routes, self.routes.setPlainText, self.fail)

    def _ifaces(self, rows) -> None:
        out = []
        for r in rows:
            col = theme.GOOD if r["state"] == "UP" else theme.MUTED
            out.append([r["name"], (r["state"], r["state"], col), r["mac"], str(r["mtu"]), r["addrs"]])
        fill_table(self.ifaces, out)

    def _ports(self, rows) -> None:
        fill_table(self.ports, [[r["proto"], r["state"], r["local"], r["peer"], r["process"]] for r in rows], key_col=2)
        filter_rows(self.ports, self.port_search.text())

    def diag(self, kind: str) -> None:
        host = self.target.text().strip()
        ex = self.ctx.ex
        fn = {"ping": network.ping, "trace": network.traceroute, "dns": network.dns_lookup}[kind]
        self.diag_out.setPlainText(f"Running {kind} on {self.ctx.host}…")
        run_async(lambda: fn(ex, host), self.diag_out.setPlainText, self.fail)

    # firewall -----------------------------------------------------------
    def load_firewall(self) -> None:
        ex = self.ctx.ex

        def work():
            tool = firewall.detect(ex)
            return tool, firewall.status(ex, tool) if tool else "No firewall tool found."

        def done(res):
            self.fw_tool, text = res
            self.fw_label.setText(f"Detected: {self.fw_tool or 'none'}")
            self.fw_out.setPlainText(text)
            for b in self.fw_rule_btns:
                b.setEnabled(self.fw_tool == "ufw")

        run_async(work, done, self.fail)

    def _fw_done(self, res) -> None:
        if not res.ok:
            info(self, "Firewall", res.err or res.out, error=True)
        self.load_firewall()

    def add_rule(self) -> None:
        port, src, action = self.fw_port.text().strip(), self.fw_src.text().strip() or "any", self.fw_action.currentText()
        if not confirm(self, "Firewall", f"{action} {port} from {src} on {self.ctx.host}?", True,
                       self.ctx.cfg.get("confirm_destructive", True)):
            return
        ex = self.ctx.ex
        run_async(lambda: firewall.ufw_rule(ex, action, port, src), self._fw_done, self.fail)

    def del_rule(self) -> None:
        txt = self.fw_num.text().strip()
        if not txt.isdigit():
            info(self, "Firewall", "Enter the rule number shown in the list.")
            return
        if not confirm(self, "Firewall", f"Delete rule #{txt} on {self.ctx.host}?", True,
                       self.ctx.cfg.get("confirm_destructive", True)):
            return
        ex = self.ctx.ex
        run_async(lambda: firewall.ufw_delete(ex, int(txt)), self._fw_done, self.fail)

    def fw_toggle(self, enable: bool) -> None:
        if not confirm(self, "Firewall", f"{'Enable' if enable else 'DISABLE'} the firewall on {self.ctx.host}?",
                       True, True):
            return
        ex = self.ctx.ex
        run_async(lambda: firewall.ufw_enable(ex, enable), self._fw_done, self.fail)
