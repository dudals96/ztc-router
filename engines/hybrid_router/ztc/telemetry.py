"""Append-only JSONL telemetry under PI_ROUTER_HOME/telemetry (0600 files).

Never written to learning/interventions.jsonl (that log is for user interventions).
"""

import json
import os
import time

from .paths import telemetry_dir


MAX_RECORD_BYTES = 8 * 1024
MAX_FILE_BYTES = 5 * 1024 * 1024


def append(stream: str, record: dict) -> bool:
    """Append one record to <stream>.jsonl; False if dropped by a size bound.

    Bounds and link safety grafted from track B: records over 8 KiB and writes that
    would grow the file past 5 MiB are dropped, symlinks are refused and the file is
    opened with O_NOFOLLOW. Raises OSError on other failures; callers decide.
    """
    path = telemetry_dir() / f"{stream}.jsonl"
    record = {"ts": round(time.time(), 3), **record}
    line = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(line) > MAX_RECORD_BYTES:
        return False
    if path.is_symlink():
        raise PermissionError(f"telemetry stream must not be a symlink: {path.name}")
    if path.exists() and path.stat().st_size + len(line) > MAX_FILE_BYTES:
        return False
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)
    return True


def read(stream: str) -> list[dict]:
    path = telemetry_dir() / f"{stream}.jsonl"
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile; None for an empty list."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, min(len(ordered), round(q / 100 * len(ordered) + 0.5)))
    return ordered[rank - 1]
