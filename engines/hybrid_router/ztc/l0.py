"""L0: regex classification + normalised signature ledger (SQLite, WAL).

- v0: error_signatures.patterns from config/anti_pattern_rules.json, now actually used.
- v1: normalise error text (paths, line numbers, hashes, numbers) into a signature and
  look it up in the ledger. Ledger rows are candidate/verified with provenance, expiry
  and revocation. There is no automatic promotion to verified (plan v0.3 §5 T1-4).
"""

import hashlib
import json
import re
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

from .paths import CONFIG_DIR, REPO_ROOT

RULES_PATH = CONFIG_DIR / "anti_pattern_rules.json"
CANDIDATE, VERIFIED = "candidate", "verified"
DEFAULT_TTL_SEC = 7 * 24 * 3600
MAX_SIGNATURE_LINES = 3

_PATH = re.compile(r"(?:[A-Za-z]:)?(?:[\w.~<>-]*[\\/])+[\w.<>-]+")
_LINE_COL = re.compile(r"(?<=[\w>)\]]):\d+(?::\d+)?")
_LINE_WORD = re.compile(r"(?i)\bline \d+")
_HEX = re.compile(r"\b(?:0x)?[0-9a-f]{7,}\b", re.I)
_NUM = re.compile(r"\b\d+\b")
_TS_CODE = re.compile(r"\bTS\d{4}\b")
# Status-like numbers carry meaning (HTTP 404 vs 500, exit 1 vs 137); keep them.
_KEEP_NUM = re.compile(
    r"(?i)\b((?:HTTP(?:/\d(?:\.\d)?)?|status|code|errno|signal|exit(?:\s+(?:code|status))?)\s*[:=]?\s*)(\d{1,3})\b"
)
_KEPT = re.compile(r"ZQ(\d{1,3})ZQ")
_WS = re.compile(r"\s+")


def load_rules(path: Path = RULES_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def policy_version(path: Path = RULES_PATH) -> str:
    """Content hash of the rule file. A rule change invalidates older ledger rows."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def compile_signatures(rules: dict) -> list[tuple[str, list[re.Pattern]]]:
    sigs = rules.get("rules", {}).get("error_loop_short_circuit", {}).get("error_signatures", {})
    return [(cls, [re.compile(p) for p in spec.get("patterns", [])]) for cls, spec in sigs.items()]


def classify_regex(text: str, compiled) -> str | None:
    """First class whose pattern matches, in rule-file order."""
    for cls, patterns in compiled:
        if any(p.search(text) for p in patterns):
            return cls
    return None


def normalize_line(line: str) -> str:
    """Replace volatile parts; keep identifiers so distinct errors stay distinct."""
    keep_codes = _TS_CODE.findall(line)
    line = _KEEP_NUM.sub(lambda m: f"{m.group(1)}ZQ{m.group(2)}ZQ", line)
    line = _PATH.sub("<PATH>", line)
    line = _LINE_COL.sub(":<N>", line)
    line = _LINE_WORD.sub("line <N>", line)
    line = _HEX.sub("<HEX>", line)
    line = _NUM.sub("<N>", line)
    line = _KEPT.sub(r"\1", line)
    for code in keep_codes:  # TS error codes carry meaning; restore them
        line = line.replace("TS<N>", code, 1)
    return _WS.sub(" ", line).strip()


def signature_lines(text: str, compiled) -> list[str]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    hits = [ln for ln in lines if any(p.search(ln) for _, pats in compiled for p in pats)]
    chosen = hits[:MAX_SIGNATURE_LINES] or lines[-1:]
    return [normalize_line(ln) for ln in chosen]


def signature(program: str, text: str, compiled) -> str:
    norm = "\n".join(signature_lines(text, compiled))
    return hashlib.sha256(f"{program}\x00{norm}".encode()).hexdigest()[:16]


def attribution() -> dict:
    """HEAD + sha256 of the files whose code produces the verdicts (A12)."""
    try:
        head = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=2
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        head = ""
    digest = hashlib.sha256()
    for rel in ("engines/hybrid_router/ztc/l0.py", "config/anti_pattern_rules.json"):
        p = REPO_ROOT / rel
        digest.update(rel.encode() + b"\x00" + (p.read_bytes() if p.exists() else b""))
    return {"head": head or "unknown", "worktree_sha256": digest.hexdigest()}


_SCHEMA = """
CREATE TABLE IF NOT EXISTS signatures (
    signature TEXT PRIMARY KEY,
    error_class TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('candidate', 'verified')),
    source_layer TEXT NOT NULL,
    source_model TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    client_version TEXT NOT NULL,
    head TEXT NOT NULL,
    worktree_sha256 TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    revoked_at REAL,
    hits INTEGER NOT NULL DEFAULT 0,
    last_seen_at REAL
)
"""


class Ledger:
    """Signature ledger. Thread-safe via a lock around one connection."""

    def __init__(self, path: Path, policy: str):
        self.path = Path(path)
        self.policy = policy
        self._lock = threading.Lock()
        existed = self.path.exists()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False, isolation_level=None)
        if not existed:
            self.path.chmod(0o600)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute(_SCHEMA)

    def ping(self) -> bool:
        with self._lock:
            return self._conn.execute("SELECT 1").fetchone() == (1,)

    def lookup(self, sig: str, now: float | None = None) -> dict | None:
        """Live row for this signature under the current policy, else None. Counts the hit."""
        now = now or time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT signature, error_class, state, source_layer, policy_version, expires_at, revoked_at"
                " FROM signatures WHERE signature = ?",
                (sig,),
            ).fetchone()
            if not row or row[6] is not None or row[5] <= now or row[4] != self.policy:
                return None
            self._conn.execute("UPDATE signatures SET hits = hits + 1, last_seen_at = ? WHERE signature = ?", (now, sig))
        return {"signature": row[0], "error_class": row[1], "state": row[2], "source_layer": row[3]}

    def put_candidate(self, sig: str, error_class: str, source_layer: str, source_model: str,
                      client_version: str, attr: dict, ttl: float = DEFAULT_TTL_SEC) -> None:
        """Insert a candidate. Never overwrites a verified row; never promotes."""
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO signatures (signature, error_class, state, source_layer, source_model,"
                " policy_version, client_version, head, worktree_sha256, created_at, expires_at)"
                " VALUES (?, ?, 'candidate', ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(signature) DO UPDATE SET error_class = excluded.error_class,"
                " source_layer = excluded.source_layer, source_model = excluded.source_model,"
                " policy_version = excluded.policy_version, client_version = excluded.client_version,"
                " head = excluded.head, worktree_sha256 = excluded.worktree_sha256,"
                " created_at = excluded.created_at, expires_at = excluded.expires_at, revoked_at = NULL"
                " WHERE signatures.state = 'candidate'",
                (sig, error_class, source_layer, source_model, self.policy, client_version,
                 attr["head"], attr["worktree_sha256"], now, now + ttl),
            )

    def revoke(self, sig: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE signatures SET revoked_at = ? WHERE signature = ?", (time.time(), sig))

    def counts(self) -> dict:
        with self._lock:
            rows = self._conn.execute("SELECT state, COUNT(*) FROM signatures GROUP BY state").fetchall()
        return {state: n for state, n in rows}

    def close(self) -> None:
        with self._lock:
            self._conn.close()
