"""Gold set schema validator and aggregator (docs/harness/EVAL_PROTOCOL_ztc.md §1-2).

The validator rejects rows whose text still carries a secret or an absolute path,
checks session-level split integrity and signature leakage across splits.
The aggregator writes counts, per-class holdout sufficiency, a holdout seal (sha256),
and the L0 regex shadow fit rate on user-labelled holdout rows with a Wilson 95% CI.
It never claims non-inferiority; discordant pairs vs the heuristic are reported as counts.
"""

import hashlib
import json
import math
import re
from pathlib import Path

from . import l0
from .masking import contains_unmasked_secret, mask_text

SCHEMA = "ztc-gold/1"
LABELS = {"syntax_compile", "dependency_missing", "lint_formatting", "permission_auth", "other", "abstain"}
EVENTS = {"PreToolUse", "PostToolUse", "PostToolUseFailure"}
MIN_PER_CLASS = 20
PROXY_MAX_WRONG = 0.10  # 2.1 entry proxy (GOLD100_SCHEDULE_ztc.md H4, EVAL §2.3)
_ID = re.compile(r"^g-[0-9a-f]{8}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ABS = re.compile(r"(?<![\w.~>])/(?:Users|home|private|var|etc|opt|tmp)/|\b[A-Za-z]:\\")


def validate_row(row: dict) -> list[str]:
    errs = []
    need = {"id": str, "schema": str, "group": dict, "event": str, "tool": str, "program": str, "text": str,
            "label": str, "label_source": str, "split": str, "created_at": str, "attribution": dict}
    for key, typ in need.items():
        if not isinstance(row.get(key), typ):
            errs.append(f"{key}: missing or not {typ.__name__}")
    if "exit_code" not in row or not (row["exit_code"] is None or isinstance(row["exit_code"], int)):
        errs.append("exit_code: must be int or null")
    if errs:
        return errs
    if row["schema"] != SCHEMA:
        errs.append("schema")
    if not _ID.match(row["id"]):
        errs.append("id format")
    if row["event"] not in EVENTS:
        errs.append("event")
    if row["label"] not in LABELS:
        errs.append("label")
    if row["label_source"] not in ("user", "agent-draft"):
        errs.append("label_source")
    if row["split"] not in ("tune", "holdout"):
        errs.append("split")
    g = row["group"]
    if not all(isinstance(g.get(k), str) and g.get(k) for k in ("session", "signature", "project")):
        errs.append("group.session/signature/project")
    a = row["attribution"]
    if not isinstance(a.get("head"), str) or not _HEX64.match(str(a.get("worktree_sha256", ""))):
        errs.append("attribution.head/worktree_sha256")
    for field in ("text", "program"):
        value = row[field]
        if len(value) > 500:
            errs.append(f"{field}: over 500 chars")
        if contains_unmasked_secret(value):
            errs.append(f"{field}: unmasked secret")
        if _ABS.search(value) or mask_text(value) != value:
            errs.append(f"{field}: not masked (absolute path or maskable content)")
    return errs


def load(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if line.strip():
                rows.append({"_line": n, **json.loads(line)})
    return rows


def validate(rows: list[dict]) -> list[str]:
    errors = []
    for r in rows:
        errors += [f"line {r.get('_line')}: {e}" for e in validate_row(r)]
    session_split, sig_split = {}, {}
    for r in rows:
        g, split = r.get("group") or {}, r.get("split")
        if session_split.setdefault(g.get("session"), split) != split:
            errors.append(f"line {r.get('_line')}: session {g.get('session')} spans both splits")
        sig_split.setdefault(g.get("signature"), set()).add(split)
    errors += [f"signature {s} leaks across splits" for s, sp in sig_split.items() if len(sp) > 1]
    return errors


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return round(centre - half, 4), round(centre + half, 4)


def aggregate(rows: list[dict], heuristic=None) -> dict:
    clean = [{k: v for k, v in r.items() if k != "_line"} for r in rows]
    holdout = [r for r in clean if r["split"] == "holdout"]
    evalset = [r for r in holdout if r["label_source"] == "user" and r["label"] != "abstain"]
    seal = hashlib.sha256("\n".join(sorted(json.dumps(r, sort_keys=True) for r in holdout)).encode()).hexdigest()
    by_class = {}
    for r in evalset:
        by_class[r["label"]] = by_class.get(r["label"], 0) + 1
    sigs = l0.compile_signatures(l0.load_rules())
    hits = abstain = b = c = 0
    judged: dict[str, list[int]] = {}
    for r in evalset:
        pred = l0.classify_regex(r["text"], sigs)
        if pred is None:
            abstain += 1
        else:
            tally = judged.setdefault(pred, [0, 0])
            tally[0] += 1
            tally[1] += pred != r["label"]
        l0_ok = pred == r["label"]
        hits += l0_ok
        if heuristic is not None:
            h_ok = heuristic(r["text"]) == r["label"]
            b += l0_ok and not h_ok
            c += h_ok and not l0_ok
    n = len(evalset)
    return {
        "schema": SCHEMA,
        "rows": len(clean),
        "by_split": {s: sum(1 for r in clean if r["split"] == s) for s in ("tune", "holdout")},
        "by_label_source": {s: sum(1 for r in clean if r["label_source"] == s) for s in ("user", "agent-draft")},
        "holdout_seal_sha256": seal if holdout else None,
        "holdout_eval_n": n,
        "holdout_by_class": {cls: {"n": k, "sufficient": k >= MIN_PER_CLASS} for cls, k in sorted(by_class.items())},
        "k3_shadow_fit_rate": {
            "value": round(hits / n, 4) if n else None,
            "wilson95": wilson(hits, n),
            "l0_abstained": abstain,
            "status": "measured" if n else "기준선 미확보 (gold 부재)",
        },
        "l21_entry_proxy": {
            cls: {"n": k, "wrong": w, "wrong_rate": round(w / k, 4), "wilson95": wilson(w, k),
                  "eligible": k >= MIN_PER_CLASS and w / k <= PROXY_MAX_WRONG}
            for cls, (k, w) in sorted(judged.items())
        },
        "paired_vs_heuristic": {"l0_only_correct_b": b, "heuristic_only_correct_c": c,
                                "note": "counts only; non-inferiority requires the pre-registered power check"}
        if heuristic is not None and n else None,
    }
