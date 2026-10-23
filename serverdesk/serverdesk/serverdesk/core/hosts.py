"""Saved server profiles and executor factory."""
from __future__ import annotations

from .config import Config
from .executor import Executor, LocalExecutor, SshExecutor

LOCAL_NAME = "localhost"


class HostStore:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._cache: dict[str, Executor] = {}

    def profiles(self) -> list[dict]:
        return list(self.cfg.get("hosts", []))

    def names(self) -> list[str]:
        return [LOCAL_NAME] + [h["name"] for h in self.profiles()]

    def upsert(self, profile: dict) -> None:
        hosts = [h for h in self.profiles() if h["name"] != profile["name"]]
        hosts.append(profile)
        self.cfg.set("hosts", sorted(hosts, key=lambda h: h["name"].lower()))
        self._cache.pop(profile["name"], None)

    def remove(self, name: str) -> None:
        self.cfg.set("hosts", [h for h in self.profiles() if h["name"] != name])
        ex = self._cache.pop(name, None)
        if isinstance(ex, SshExecutor):
            ex.close()

    def executor(self, name: str) -> Executor:
        if name == LOCAL_NAME:
            return self._cache.setdefault(name, LocalExecutor())
        if name in self._cache:
            return self._cache[name]
        for h in self.profiles():
            if h["name"] == name:
                ex = SshExecutor(h["name"], h["host"], h.get("user", ""), h.get("port", 22), h.get("key", ""))
                self._cache[name] = ex
                return ex
        return self._cache.setdefault(LOCAL_NAME, LocalExecutor())
