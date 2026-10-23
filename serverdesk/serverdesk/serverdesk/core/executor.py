"""Command executors: run commands on the local machine or on a remote host over SSH.

Every core module talks to an Executor so that the same page can administer
localhost or any saved remote server.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from .config import CACHE_DIR
from . import audit


@dataclass
class Result:
    code: int
    out: str
    err: str

    @property
    def ok(self) -> bool:
        return self.code == 0

    @property
    def text(self) -> str:
        return (self.out or "") + (("\n" + self.err) if self.err and not self.ok else "")


class Executor(ABC):
    name: str = "localhost"
    is_remote: bool = False

    @abstractmethod
    def run(self, cmd, timeout: float = 20, sudo: bool = False, input: str | None = None) -> Result:
        ...

    def run_audited(self, action: str, cmd, **kw) -> Result:
        res = self.run(cmd, **kw)
        detail = cmd if isinstance(cmd, str) else shlex.join(cmd)
        audit.record(self.name, action, detail + ("" if res.ok else f" -> {res.err.strip()[:200]}"), res.ok)
        return res

    def has(self, binary: str) -> bool:
        return self.run(["sh", "-c", f"command -v {shlex.quote(binary)}"], timeout=8).ok


class LocalExecutor(Executor):
    name = "localhost"

    def _sudo_prefix(self) -> list[str]:
        if os.geteuid() == 0:
            return []
        if (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and shutil.which("pkexec"):
            return ["pkexec"]
        return ["sudo", "-n"]

    def run(self, cmd, timeout: float = 20, sudo: bool = False, input: str | None = None) -> Result:
        argv = ["bash", "-lc", cmd] if isinstance(cmd, str) else list(cmd)
        if sudo:
            argv = self._sudo_prefix() + argv
        env = dict(os.environ, LC_ALL="C.UTF-8", LANG="C.UTF-8")
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                               input=input, env=env, errors="replace")
            return Result(p.returncode, p.stdout, p.stderr)
        except subprocess.TimeoutExpired:
            return Result(124, "", f"Timed out after {timeout:.0f}s")
        except FileNotFoundError as e:
            return Result(127, "", str(e))
        except OSError as e:
            return Result(126, "", str(e))


class SshExecutor(Executor):
    is_remote = True

    def __init__(self, name: str, host: str, user: str = "", port: int = 22, key: str = ""):
        self.name = name
        self.host = host
        self.user = user
        self.port = int(port or 22)
        self.key = key
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def target(self) -> str:
        return f"{self.user}@{self.host}" if self.user else self.host

    def _base(self) -> list[str]:
        argv = [
            "ssh", "-p", str(self.port),
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=8",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ServerAliveInterval=10",
            "-o", "ControlMaster=auto",
            "-o", f"ControlPath={CACHE_DIR}/cm-%C",
            "-o", "ControlPersist=120",
        ]
        if self.key:
            argv += ["-i", str(Path(self.key).expanduser())]
        return argv + [self.target]

    def run(self, cmd, timeout: float = 20, sudo: bool = False, input: str | None = None) -> Result:
        remote = cmd if isinstance(cmd, str) else shlex.join(cmd)
        if sudo and self.user != "root":
            remote = f"sudo -n sh -c {shlex.quote(remote)}"
        argv = self._base() + [remote]
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                               input=input, errors="replace")
            return Result(p.returncode, p.stdout, p.stderr)
        except subprocess.TimeoutExpired:
            return Result(124, "", f"Timed out after {timeout:.0f}s")
        except FileNotFoundError:
            return Result(127, "", "ssh client is not installed (install openssh-client)")
        except OSError as e:
            return Result(126, "", str(e))

    def interactive_argv(self) -> list[str]:
        return self._base()

    def close(self) -> None:
        subprocess.run(["ssh", "-O", "exit", "-o", f"ControlPath={CACHE_DIR}/cm-%C", self.target],
                       capture_output=True)
