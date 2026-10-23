"""Append-only audit trail of every administrative action performed from the app."""
from __future__ import annotations

import getpass
import threading
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR

_lock = threading.Lock()
AUDIT_FILE: Path = DATA_DIR / "audit.log"


def record(host: str, action: str, detail: str = "", ok: bool = True) -> None:
    line = "{ts}\t{user}\t{host}\t{status}\t{action}\t{detail}\n".format(
        ts=datetime.now().isoformat(timespec="seconds"),
        user=getpass.getuser(),
        host=host,
        status="OK" if ok else "FAIL",
        action=action,
        detail=detail.replace("\n", " ")[:500],
    )
    with _lock:
        try:
            AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with AUDIT_FILE.open("a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError:
            pass


def read(limit: int = 500) -> list[list[str]]:
    try:
        lines = AUDIT_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows = [ln.split("\t", 5) for ln in lines[-limit:]]
    return [r + [""] * (6 - len(r)) for r in reversed(rows)]
