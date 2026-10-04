#!/usr/bin/env python3
"""Gold drafting tool (docs/harness/GOLD100_SCHEDULE_ztc.md §2.2, §4.2): extract / label / status.

- extract: Claude Code transcripts -> Bash failures ("Exit code N", N != 0) -> the hook client's
  own masking (router_client.build_body) and the daemon's re-mask -> gold.validate_row ->
  stratified, capped sample -> $PI_ROUTER_HOME/gold/candidates.jsonl. The split is decided here,
  before any labelling, from the session hash only. Only tune rows carry an L0 regex draft.
- label: one candidate at a time, keys 1-6 / s / q. Appends user-labelled rows to gold/v1.jsonl.
  Holdout rows are shown blind (no draft). Already-labelled candidates are skipped (resumable).
- status: counts only (per split / class / day). Never prints bodies.

Everything is written under $PI_ROUTER_HOME/gold/ (dir 0700, files 0600). Paths inside a git
work tree are refused. Stdlib only, no network, no LLM.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import random
import re
import signal
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parents[2] / "engines" / "hybrid_router"
sys.path.insert(0, str(ENGINE_DIR))
from ztc import gold, l0  # noqa: E402
from ztc.masking import mask_text  # noqa: E402
from ztc.paths import REPO_ROOT, ensure_outside_repo, router_home  # noqa: E402

KEYS = {"1": "syntax_compile", "2": "dependency_missing", "3": "lint_formatting",
        "4": "permission_auth", "5": "other", "6": "abstain"}
SPLIT_SALT = "ztc-gold-split/1"
TUNE_PERCENT = 70
SESSION_CAP = 4
SIGNATURE_CAP = 2
PROJECT_SHARE = 0.5
_TIMEOUT = re.compile(r"(?i)\bcommand timed out\b|\btimed out after \d")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]|\x1b\[[0-9;?]*[A-Za-z]")


def _load_client():
    """Import scripts/hooks/router_client.py for its masking path without keeping its signal handlers."""
    saved = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        spec = importlib.util.spec_from_file_location(
            "ztc_router_client", REPO_ROOT / "scripts" / "hooks" / "router_client.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        for s, h in saved.items():
            signal.signal(s, h)
    return mod


CLIENT = _load_client()


# ---------------------------------------------------------------- output location

def gold_dir() -> Path:
    """$PI_ROUTER_HOME/gold, refused inside this repository or any git work tree; created 0700."""
    path = Path(router_home()).expanduser() / "gold"
    if path.is_symlink():
        raise PermissionError("gold path must not be a symlink")
    resolved = ensure_outside_repo(path)
    for parent in (resolved, *resolved.parents):
        if (parent / ".git").exists():
            raise PermissionError(f"gold output must not be inside a git work tree: {parent}")
    missing = []
    probe = resolved
    while not probe.exists():
        missing.append(probe)
        probe = probe.parent
    for d in reversed(missing):
        d.mkdir(mode=0o700, exist_ok=True)
    if not resolved.is_dir():
        raise PermissionError("gold path must be a directory")
    os.chmod(resolved, 0o700)
    for d in missing:
        os.chmod(d, 0o700)
    return resolved


def _write_private(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _append_private(path: Path, line: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, (line + "\n").encode("utf-8"))
    finally:
        os.close(fd)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------- transcript scan

def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str))
    return ""


def _local_date(ts) -> str | None:
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().date().isoformat()
    except ValueError:
        return None


def scan_failures(root: Path):
    """Yield one dict per Bash tool_result with is_error=true. Nothing is printed."""
    for path in sorted(Path(root).expanduser().rglob("*.jsonl")):
        if not path.is_file():
            continue
        pending, session_cwd = {}, None
        sub_path = "subagents" in path.parts
        try:
            f = open(path, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(rec, dict):
                    continue
                if session_cwd is None and isinstance(rec.get("cwd"), str):
                    session_cwd = rec["cwd"]
                msg = rec.get("message")
                content = msg.get("content") if isinstance(msg, dict) else None
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_use" and block.get("name") == "Bash":
                        inp = block.get("input") if isinstance(block.get("input"), dict) else {}
                        pending[block.get("id")] = {
                            "command": inp.get("command") if isinstance(inp.get("command"), str) else "",
                            "cwd": rec.get("cwd") if isinstance(rec.get("cwd"), str) else session_cwd,
                        }
                    elif block.get("type") == "tool_result" and block.get("tool_use_id") in pending:
                        use = pending.pop(block["tool_use_id"])
                        if block.get("is_error") is not True:
                            continue
                        tur = rec.get("toolUseResult")
                        yield {
                            "session_id": str(rec.get("sessionId") or path.stem),
                            "tool_use_id": str(block["tool_use_id"]),
                            "command": use["command"],
                            "cwd": use["cwd"] or session_cwd,
                            "project_cwd": session_cwd or use["cwd"],
                            "date": _local_date(rec.get("timestamp")),
                            "subagent": rec.get("isSidechain") is True or sub_path,
                            "interrupted": isinstance(tur, dict) and tur.get("interrupted") is True,
                            "error": _text_of(block.get("content")),
                        }


def _project(cwd) -> str:
    name = re.split(r"[\\/]", cwd.rstrip("/\\"))[-1] if isinstance(cwd, str) and cwd.strip("/\\") else ""
    return name or "unknown"


def _bucket(program: str) -> str:
    return (re.split(r"[\\/]", program)[-1] or program or "-").lower()


def split_for(session_hash: str) -> str:
    """Deterministic, seed-independent: a session never changes split across re-extracts."""
    h = int(hashlib.sha256(f"{SPLIT_SALT}\x00{session_hash}".encode()).hexdigest()[:8], 16)
    return "tune" if h % 100 < TUNE_PERCENT else "holdout"


def build_candidate(f: dict, compiled, attr: dict) -> tuple[dict | None, str]:
    """Return (candidate, "") or (None, exclusion reason)."""
    error = f["error"]
    first, _, rest = error.partition("\n")
    m = CLIENT.EXIT_LINE.match(first)
    if not m:
        return None, "not_exit_code"  # harness/hook/permission denials and other non-execution errors
    if int(m.group(1)) == 0:
        return None, "exit_zero"
    if f["interrupted"] or _TIMEOUT.search(error):
        return None, "timeout"
    if not rest.strip():
        return None, "empty_body"
    payload = {"hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "cwd": f["cwd"],
               "session_id": f["session_id"], "tool_input": {"command": f["command"]}, "error": error}
    body = CLIENT.build_body(payload)  # the hook client's own masking path
    program = mask_text(body["program"], limit=60)  # the daemon re-masks the same way
    text = mask_text(body["text"])
    if not text.strip():
        return None, "empty_body"
    cand = {
        "id": "g-" + hashlib.sha256(f"{f['session_id']}\x00{f['tool_use_id']}".encode()).hexdigest()[:8],
        "schema": gold.SCHEMA,
        "group": {"session": body["session"], "signature": l0.signature(program, text, compiled),
                  "project": _project(f["project_cwd"])},
        "event": "PostToolUseFailure", "tool": "Bash", "program": program, "text": text,
        "exit_code": body["exit_code"], "split": split_for(body["session"]), "attribution": attr,
        "source": {"date": f["date"], "subagent": bool(f["subagent"])},
    }
    probe = {**cand, "label": "abstain", "label_source": "agent-draft", "created_at": "1970-01-01T00:00:00+00:00"}
    if gold.validate_row(probe):
        return None, "invalid_after_mask"
    return cand, ""


def stratum(c: dict) -> tuple:
    return (c["group"]["project"], _bucket(c["program"]), c["exit_code"], c["source"]["subagent"])


def sample(pool: list[dict], n: int, seed: int) -> list[dict]:
    """Proportional allocation over strata, then fill; caps: session, signature, project share."""
    rng = random.Random(seed)
    strata = defaultdict(list)
    for c in sorted(pool, key=lambda c: c["id"]):
        strata[stratum(c)].append(c)
    keys = sorted(strata, key=repr)
    for k in keys:
        rng.shuffle(strata[k])
    total = len(pool)
    quota = {}
    if total:
        raw = {k: n * len(strata[k]) / total for k in keys}
        quota = {k: int(v) for k, v in raw.items()}
        for k in sorted(keys, key=lambda k: (-(raw[k] - quota[k]), repr(k)))[: max(0, n - sum(quota.values()))]:
            quota[k] += 1
    project_cap = max(1, int(n * PROJECT_SHARE))
    chosen, ids = [], set()
    per_session, per_sig, per_project = Counter(), Counter(), Counter()

    def take(c) -> bool:
        g = c["group"]
        if (c["id"] in ids or per_session[g["session"]] >= SESSION_CAP or per_sig[g["signature"]] >= SIGNATURE_CAP
                or per_project[g["project"]] >= project_cap):
            return False
        chosen.append(c)
        ids.add(c["id"])
        per_session[g["session"]] += 1
        per_sig[g["signature"]] += 1
        per_project[g["project"]] += 1
        return True

    for k in keys:
        got = 0
        for c in strata[k]:
            if got >= quota.get(k, 0) or len(chosen) >= n:
                break
            got += take(c)
    rest = [c for k in keys for c in strata[k] if c["id"] not in ids]
    rng.shuffle(rest)
    for c in rest:
        if len(chosen) >= n:
            break
        take(c)
    rng.shuffle(chosen)
    return chosen


def extract(transcripts_root: Path, since: str, n: int, seed: int, force: bool = False, out=sys.stdout) -> dict:
    out_dir = gold_dir()
    target = out_dir / "candidates.jsonl"
    if target.exists() and not force:
        raise FileExistsError(f"{target} exists; pass --force to replace it (labelled rows in v1.jsonl are kept)")
    since_d = date.fromisoformat(since).isoformat()
    compiled = l0.compile_signatures(l0.load_rules())
    attr = l0.attribution()
    reasons, seen, pool = Counter(), set(), []
    failures = 0
    for f in scan_failures(transcripts_root):
        failures += 1
        key = (f["session_id"], f["tool_use_id"])
        if key in seen:
            reasons["duplicate"] += 1
            continue
        seen.add(key)
        if not f["date"] or f["date"] < since_d:
            reasons["before_since"] += 1
            continue
        cand, why = build_candidate(f, compiled, attr)
        if cand is None:
            reasons[why] += 1
            continue
        pool.append(cand)
    tune_sigs = {c["group"]["signature"] for c in pool if c["split"] == "tune"}
    kept = [c for c in pool if not (c["split"] == "holdout" and c["group"]["signature"] in tune_sigs)]
    reasons["holdout_signature_in_tune"] = len(pool) - len(kept)
    chosen = sample(kept, n, seed)
    for c in chosen:
        if c["split"] == "tune":
            c["draft_label"] = l0.classify_regex(c["text"], compiled)
    _write_private(target, "".join(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n" for c in chosen))
    projects = Counter(c["group"]["project"] for c in chosen)
    summary = {
        "since": since_d, "n": n, "seed": seed, "created_at": _now(),
        "bash_failures_seen": failures, "eligible": len(kept), "excluded": dict(sorted(reasons.items())),
        "selected": len(chosen),
        "by_split": {s: sum(1 for c in chosen if c["split"] == s) for s in ("tune", "holdout")},
        "sessions": len({c["group"]["session"] for c in chosen}),
        "projects": len(projects), "max_project_share": round(max(projects.values()) / len(chosen), 3) if chosen else None,
        "subagent": sum(1 for c in chosen if c["source"]["subagent"]),
    }
    _write_private(out_dir / "extract_meta.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2), file=out)
    return summary


# ---------------------------------------------------------------- labelling

def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe(text: str) -> str:
    return _CONTROL.sub("?", text)


def label(split: str | None = None, limit: int | None = None, inp=sys.stdin, out=sys.stdout) -> int:
    out_dir = gold_dir()
    cands = _read_jsonl(out_dir / "candidates.jsonl")
    if not cands:
        print("no candidates; run `extract` first", file=out)
        return 0
    v1 = out_dir / "v1.jsonl"
    done = {r.get("id") for r in _read_jsonl(v1)}
    queue = [c for c in cands if c["id"] not in done and (split is None or c["split"] == split)]
    if limit is not None:
        queue = queue[:limit]
    menu = "  ".join(f"{k} {v}" for k, v in KEYS.items()) + "  s skip  q quit"
    written = 0
    for i, c in enumerate(queue, 1):
        print(f"\n[{i}/{len(queue)}] split={c['split']}  program={_safe(c['program'])}  exit={c['exit_code']}", file=out)
        print("-" * 60, file=out)
        print(_safe(c["text"]), file=out)
        print("-" * 60, file=out)
        if c["split"] == "tune":  # holdout stays blind (H5)
            print(f"draft (L0 regex): {c.get('draft_label') or '-'}", file=out)
        print(menu, file=out)
        while True:
            print("> ", end="", file=out, flush=True)
            raw = inp.readline()
            if raw == "":
                print(f"\nend of input: saved {written}", file=out)
                return written
            key = raw.strip().lower()
            if key == "q":
                print(f"saved {written}", file=out)
                return written
            if key == "s":
                break
            if key in KEYS:
                row = {k: c[k] for k in ("id", "schema", "group", "event", "tool", "program", "text",
                                         "exit_code", "split", "attribution")}
                row.update(label=KEYS[key], label_source="user", created_at=_now())
                errs = gold.validate_row(row)
                if errs:
                    print(f"row rejected by validator ({len(errs)} errors); skipped", file=out)
                    break
                _append_private(v1, json.dumps(row, ensure_ascii=False, sort_keys=True))
                written += 1
                break
            print("keys: 1-6, s, q", file=out)
    print(f"\ndone: saved {written}", file=out)
    return written


# ---------------------------------------------------------------- status

def status(out=sys.stdout) -> dict:
    out_dir = gold_dir()
    cands = _read_jsonl(out_dir / "candidates.jsonl")
    v1 = out_dir / "v1.jsonl"
    rows = gold.load(v1) if v1.exists() else []
    done = {r.get("id") for r in rows}
    splits = ("tune", "holdout")
    report = {
        "candidates": {s: sum(1 for c in cands if c["split"] == s) for s in splits},
        "labelled": {s: sum(1 for r in rows if r.get("split") == s) for s in splits},
        "remaining": {s: sum(1 for c in cands if c["split"] == s and c["id"] not in done) for s in splits},
        "by_class": {s: dict(sorted(Counter(r.get("label") for r in rows if r.get("split") == s).items()))
                     for s in splits},
        "by_day": dict(sorted(Counter(str(r.get("created_at", ""))[:10] for r in rows).items())),
        "validate_errors": len(gold.validate(rows)),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2), file=out)
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)
    ex = sub.add_parser("extract", help="sample masked candidates from Claude Code transcripts")
    ex.add_argument("--since", required=True, help="YYYY-MM-DD (local date)")
    ex.add_argument("--n", type=int, default=120)
    ex.add_argument("--seed", type=int, required=True)
    ex.add_argument("--transcripts-root", type=Path, default=Path.home() / ".claude" / "projects")
    ex.add_argument("--force", action="store_true", help="replace an existing candidates.jsonl")
    lb = sub.add_parser("label", help="label candidates interactively (1-6, s, q)")
    lb.add_argument("--split", choices=("holdout", "tune"))
    lb.add_argument("--limit", type=int)
    sub.add_parser("status", help="counts only")
    args = ap.parse_args(argv)
    try:
        if args.command == "extract":
            extract(args.transcripts_root, args.since, args.n, args.seed, force=args.force)
        elif args.command == "label":
            label(args.split, args.limit)
        else:
            status()
    except (PermissionError, FileExistsError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
