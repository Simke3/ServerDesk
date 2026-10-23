"""Persistent JSON configuration stored under XDG directories."""
from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path

APP_DIR = "serverdesk"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_DIR
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_DIR
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / APP_DIR

DEFAULTS = {
    "refresh_seconds": 2,
    "slow_refresh_seconds": 10,
    "thresholds": {"cpu": 90, "memory": 90, "disk": 90, "load_per_core": 2.0},
    "alerts_enabled": True,
    "confirm_destructive": True,
    "hosts": [],               # list of {name, host, user, port, key}
    "last_host": "localhost",
    "window": {"width": 1360, "height": 860},
    "log_lines": 400,
}


class Config:
    def __init__(self, path: Path | None = None):
        self.path = path or CONFIG_DIR / "config.json"
        self._lock = threading.RLock()
        self.data = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self) -> None:
        with self._lock:
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return
            self._merge(self.data, loaded)

    @staticmethod
    def _merge(base: dict, new: dict) -> None:
        for k, v in new.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                Config._merge(base[k], v)
            else:
                base[k] = v

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)

    def get(self, key: str, default=None):
        with self._lock:
            return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        with self._lock:
            self.data[key] = value
            self.save()
