#!/usr/bin/env python3
"""Shadow K1/K2 aggregate (docs/harness/EVAL_PROTOCOL_ztc.md §0, PLAN K1·K2).

Reads $PI_ROUTER_HOME/telemetry/{hook_events,router_events}.jsonl and writes
learning/metrics/shadow_k1k2_<date>.json. Counts and latency quantiles only: no program
names, commands, paths or signatures leave the router home (EVAL_PROTOCOL §0 "원자료·명령문·경로 금지").

K1: internal RPC (`rpc_ms`) and client (`client_ms`, interpreter start excluded) latency on
`ok` calls, timeout rate over all calls. The harness-side full latency lives in transcripts,
not telemetry, so it is not measured here.
K2: L0 confirmed judgments (router `error_class` set) / failed Bash calls (router events of a
PostToolUseFailure, i.e. `source` miss or l0_ledger), split into first sighting vs ledger hit.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engines" / "hybrid_router"))
from ztc.paths import METRICS_DIR, router_home  # noqa: E402

SCHEMA = "ztc-shadow-k1k2/1"
FAILED_SOURCES = ("miss", "l0_ledger")


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _quantiles(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    v = sorted(values)

    def q(p: float) -> float:
        return round(v[min(len(v) - 1, int(p * len(v)))], 3)

    return {"n": len(v), "p50": q(0.50), "p95": q(0.95), "p99": q(0.99), "max": round(v[-1], 3)}


def _day(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def aggregate(home: Path, window_days: int) -> dict:
    hooks = _rows(home / "telemetry" / "hook_events.jsonl")
    router = _rows(home / "telemetry" / "router_events.jsonl")
    outcomes = Counter(h.get("outcome") for h in hooks)
    ok = [h for h in hooks if h.get("outcome") == "ok"]
    days = Counter(_day(h["ts"]) for h in hooks if isinstance(h.get("ts"), (int, float)))
    failed = [r for r in router if r.get("source") in FAILED_SOURCES]
    confirmed = [r for r in failed if r.get("error_class")]
    total = len(hooks)
    return {
        "schema": SCHEMA,
        "date": time.strftime("%Y%m%d"),
        "source": "shadow telemetry ($PI_ROUTER_HOME, counts only)",
        "collection": {
            "first": min(days) if days else None,
            "last": max(days) if days else None,
            "days_with_data": len(days),
            "by_day": dict(sorted(days.items())),
            "window_days_planned": window_days,
            "window_met": len(days) >= window_days,
        },
        "calls_total": total,
        "by_event": dict(Counter(h.get("event") for h in hooks)),
        "outcomes": dict(outcomes),
        "client_versions": dict(Counter(h.get("client_version") for h in hooks)),
        "k1": {
            "internal_rpc_ms_ok": _quantiles([h["rpc_ms"] for h in ok if isinstance(h.get("rpc_ms"), (int, float))]),
            "client_ms_ok_excl_interpreter_start": _quantiles(
                [h["client_ms"] for h in ok if isinstance(h.get("client_ms"), (int, float))]
            ),
            "timeout_rate": round(outcomes.get("timeout", 0) / total, 4) if total else None,
            "target": "internal RPC p99 <= 30 ms, timeout rate < 1%",
            "full_latency": "not in telemetry (transcript hook durationMs) — not measured here",
        },
        "k2": {
            "failed_calls": len(failed),
            "l0_confirmed": len(confirmed),
            "rate": round(len(confirmed) / len(failed), 4) if failed else None,
            "first_sighting": sum(1 for r in confirmed if r.get("source") == "miss"),
            "ledger_hit": sum(1 for r in confirmed if r.get("source") == "l0_ledger"),
            "error_classes": dict(Counter(r["error_class"] for r in confirmed)),
            "target": ">= 50% (classification, not resolution)",
        },
        "k3": "기준선 미확보 (gold 부재)",
        "k4": "N/A (shadow: no injection)",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--window-days", type=int, default=7)
    ap.add_argument("--out", type=Path, help="default learning/metrics/shadow_k1k2_<date>.json")
    ap.add_argument("--stdout", action="store_true", help="print instead of writing")
    args = ap.parse_args()
    result = aggregate(router_home(), args.window_days)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.stdout:
        sys.stdout.write(text)
        return 0
    out = args.out or METRICS_DIR / f"shadow_k1k2_{result['date']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
