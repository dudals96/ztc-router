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


RETENTION_DAYS = 14  # user decision 2026-09-24 (EVAL_PROTOCOL_ztc.md §0)


def prune(max_age_days: float = RETENTION_DAYS, now: float | None = None) -> dict:
    """Drop telemetry records older than max_age_days from every stream.

    Each stream is rewritten atomically (0600 temp file + rename). Symlinks are skipped.
    Lines without a numeric ts are kept (they are not ours to judge). Returns counts.
    """
    cutoff = (time.time() if now is None else now) - max_age_days * 86400
    result = {"streams": 0, "kept": 0, "dropped": 0, "skipped_symlinks": 0}
    for path in sorted(telemetry_dir().glob("*.jsonl")):
        if path.is_symlink():
            result["skipped_symlinks"] += 1
            continue
        kept, dropped = [], 0
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    ts = json.loads(line).get("ts")
                except (json.JSONDecodeError, AttributeError):
                    ts = None
                if isinstance(ts, (int, float)) and ts < cutoff:
                    dropped += 1
                else:
                    kept.append(line if line.endswith("\n") else line + "\n")
        result["streams"] += 1
        result["kept"] += len(kept)
        result["dropped"] += dropped
        if not dropped:
            continue
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(kept)
        os.replace(tmp, path)
    return result
