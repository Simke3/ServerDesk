"""Docker container management (also works with podman via the docker CLI alias)."""
from __future__ import annotations

import json
import re

from .executor import Executor, Result

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-/:@]*$")
ACTIONS = {"start", "stop", "restart", "pause", "unpause", "kill", "rm"}


def available(ex: Executor) -> bool:
    return ex.run("command -v docker >/dev/null && docker info >/dev/null 2>&1", timeout=15).ok


def _json_lines(text: str) -> list[dict]:
    rows = []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith("{"):
            try:
                rows.append(json.loads(ln))
            except ValueError:
                pass
    return rows


def containers(ex: Executor) -> list[dict]:
    res = ex.run(["docker", "ps", "-a", "--no-trunc", "--format", "{{json .}}"], timeout=25)
    if not res.ok:
        raise RuntimeError(res.err.strip() or "docker ps failed")
    rows = _json_lines(res.out)
    for r in rows:
        r["ShortID"] = r.get("ID", "")[:12]
    return rows


def images(ex: Executor) -> list[dict]:
    res = ex.run(["docker", "images", "--format", "{{json .}}"], timeout=25)
    return _json_lines(res.out)


def stats(ex: Executor) -> dict[str, dict]:
    res = ex.run(["docker", "stats", "--no-stream", "--format", "{{json .}}"], timeout=30)
    return {r.get("Name", ""): r for r in _json_lines(res.out)}


def act(ex: Executor, ident: str, action: str) -> Result:
    if action not in ACTIONS or not _ID_RE.match(ident):
        return Result(2, "", "Invalid request")
    cmd = ["docker", "rm", "-f", ident] if action == "rm" else ["docker", action, ident]
    return ex.run_audited(f"docker.{action}", cmd, timeout=90)


def logs(ex: Executor, ident: str, lines: int = 300) -> str:
    if not _ID_RE.match(ident):
        return "Invalid container"
    res = ex.run(["docker", "logs", "--tail", str(int(lines)), "--timestamps", ident], timeout=30)
    return (res.out + res.err) or "(empty)"


def inspect(ex: Executor, ident: str) -> str:
    if not _ID_RE.match(ident):
        return "Invalid container"
    return ex.run(["docker", "inspect", ident], timeout=20).text


def prune(ex: Executor) -> Result:
    return ex.run_audited("docker.prune", ["docker", "system", "prune", "-f"], timeout=180)
