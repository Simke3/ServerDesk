"""Block devices, mounts and directory usage."""
from __future__ import annotations

import json
import re
import shlex

from .executor import Executor

_PATH_RE = re.compile(r"^/[A-Za-z0-9_./\- ]*$")


def block_devices(ex: Executor) -> list[dict]:
    res = ex.run(["lsblk", "-J", "-b", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL,ROTA,RO,UUID"], timeout=15)
    if not res.ok:
        raise RuntimeError(res.err.strip() or "lsblk failed")
    data = json.loads(res.out)
    rows: list[dict] = []

    def walk(nodes, depth=0):
        for n in nodes:
            rows.append({
                "name": ("  " * depth) + ("└ " if depth else "") + n.get("name", ""),
                "size": int(n.get("size") or 0), "type": n.get("type") or "",
                "fstype": n.get("fstype") or "", "mount": n.get("mountpoint") or "",
                "model": (n.get("model") or "").strip(),
                "rota": "HDD" if str(n.get("rota")).lower() in ("1", "true") else "SSD/NVMe",
                "ro": str(n.get("ro")).lower() in ("1", "true"),
                "uuid": n.get("uuid") or "",
            })
            walk(n.get("children") or [], depth + 1)

    walk(data.get("blockdevices", []))
    return rows


def directory_usage(ex: Executor, path: str, limit: int = 40) -> list[tuple[int, str]]:
    if not _PATH_RE.match(path) or ".." in path:
        raise ValueError("Invalid path")
    res = ex.run(f"du -xk --max-depth=1 {shlex.quote(path)} 2>/dev/null | sort -rn | head -n {int(limit)}",
                 timeout=120, sudo=False)
    rows = []
    for line in res.out.splitlines():
        p = line.split(None, 1)
        if len(p) == 2 and p[0].isdigit():
            rows.append((int(p[0]) * 1024, p[1]))
    return rows


def inode_usage(ex: Executor) -> list[dict]:
    res = ex.run("df -Pi -x tmpfs -x devtmpfs -x squashfs -x overlay 2>/dev/null", timeout=15)
    rows = []
    for line in res.out.splitlines()[1:]:
        p = line.split()
        if len(p) >= 6 and p[1].isdigit():
            rows.append({"device": p[0], "inodes": int(p[1]), "used": int(p[2]),
                         "free": int(p[3]), "pct": p[4], "mount": " ".join(p[5:])})
    return rows


def filesystems(ex: Executor) -> list[dict]:
    res = ex.run("df -PkT -x tmpfs -x devtmpfs -x squashfs -x overlay -x efivarfs 2>/dev/null", timeout=15)
    rows = []
    for line in res.out.splitlines()[1:]:
        p = line.split()
        if len(p) < 7:
            continue
        try:
            size, used, avail = int(p[2]) * 1024, int(p[3]) * 1024, int(p[4]) * 1024
        except ValueError:
            continue
        rows.append({"device": p[0], "fstype": p[1], "size": size, "used": used, "avail": avail,
                     "pct": 100.0 * used / size if size else 0.0, "mount": " ".join(p[6:])})
    return rows
