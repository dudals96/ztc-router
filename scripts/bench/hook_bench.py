#!/usr/bin/env python3
"""Hook latency bench (docs/harness/EVAL_PROTOCOL_ztc.md §3).

Measures two layers separately:
  full : spawn scripts/hooks/router-client.sh, feed the payload, wait for exit (what the harness pays)
  rpc  : the client's internal RPC (router_client.rpc, same code path, in-process timing)
over cold (first call after a fresh daemon start) / warm, concurrency 1 / 3, and two payload
kinds (l0_regex hit, l0_ledger hit). Raw rows: $PI_ROUTER_HOME/telemetry/bench_<date>.jsonl.
Aggregate: learning/metrics/bench_<date>.json. The daemon under test runs with its own
home ($PI_ROUTER_HOME/bench-run) so bench traffic never mixes with shadow telemetry.
Earlier latency figures (18 ms, 34.2 ms, 38.5 ms) were code constants, not measurements.
"""

import argparse
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "engines" / "hybrid_router"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "hooks"))
from ztc import telemetry  # noqa: E402
from ztc.paths import BIND_HOST, METRICS_DIR, router_home, router_port  # noqa: E402
import router_client  # noqa: E402  (installs its signal handlers in this main thread)

CLIENT = REPO_ROOT / "scripts" / "hooks" / "router-client.sh"
DAEMON = REPO_ROOT / "scripts" / "hybrid-router-daemon.py"
BUDGET_MS = 30.0
PAYLOADS = {
    "l0_regex": "error TS2339: Property 'state' does not exist on type 'Session'",
    "l0_ledger": "fatal: heap out of memory while linking target bench",
}


def payload(kind: str) -> bytes:
    return json.dumps({
        "session_id": "bench", "hook_event_name": "PostToolUse", "tool_name": "Bash", "cwd": str(REPO_ROOT),
        "tool_input": {"command": "npm run build"},
        "tool_response": {"stdout": "", "stderr": PAYLOADS[kind], "interrupted": False},
    }).encode()


class Daemon:
    def __init__(self, env: dict):
        self.env = env
        self.proc = None

    def start(self) -> float:
        t0 = time.perf_counter()
        self.proc = subprocess.Popen([sys.executable, str(DAEMON)], env=self.env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        port = int(self.env["PI_ROUTER_PORT"])
        while time.perf_counter() - t0 < 10:
            try:
                with urlopen(f"http://{BIND_HOST}:{port}/health", timeout=0.5) as r:
                    if r.status == 200:
                        return (time.perf_counter() - t0) * 1000
            except OSError:
                time.sleep(0.01)
        raise RuntimeError("daemon did not become healthy")

    def stop(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait(5)
            self.proc = None


def full_call(kind: str, env: dict) -> dict:
    t0 = time.perf_counter()
    proc = subprocess.run([str(CLIENT)], input=payload(kind), capture_output=True, env=env)
    return {"ms": (time.perf_counter() - t0) * 1000, "neutral": proc.stdout == b"{}" and proc.returncode == 0}


def rpc_call(kind: str) -> dict:
    body = router_client.build_body(json.loads(payload(kind)))
    outcome, ms = router_client.rpc(body, time.perf_counter() + BUDGET_MS / 1000, "bench")
    return {"ms": ms, "neutral": True, "outcome": outcome}


def run_batch(fn, kind, env, n, conc):
    rows, lock = [], threading.Lock()

    def worker(count):
        for _ in range(count):
            r = fn(kind, env) if fn is full_call else fn(kind)
            with lock:
                rows.append(r)

    per = [n // conc + (1 if i < n % conc else 0) for i in range(conc)]
    threads = [threading.Thread(target=worker, args=(c,)) for c in per]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return rows


def stats(rows):
    ms = [r["ms"] for r in rows]
    return {
        "n": len(ms),
        "p50": telemetry.percentile(ms, 50), "p95": telemetry.percentile(ms, 95),
        "p99": telemetry.percentile(ms, 99), "max": max(ms) if ms else None,
        "over_budget_rate": round(sum(1 for r in rows if r["ms"] > BUDGET_MS) / len(rows), 4) if rows else None,
        "timeout_rate": round(sum(1 for r in rows if r.get("outcome") == "timeout") / len(rows), 4) if rows else None,
        "neutral_rate": round(sum(1 for r in rows if r["neutral"]) / len(rows), 4) if rows else None,
    }


def seed_ledger(env):
    """One miss, then wait for the async judge so the ledger kind is a real ledger hit."""
    full_call("l0_ledger", env)
    time.sleep(0.3)


def env_info():
    files = sorted(p for p in (REPO_ROOT / "engines" / "hybrid_router" / "ztc").glob("*.py"))
    files += [DAEMON, CLIENT, REPO_ROOT / "scripts" / "hooks" / "router_client.py"]
    digest = hashlib.sha256(b"".join(p.read_bytes() for p in files)).hexdigest()
    head = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(REPO_ROOT), "status", "--porcelain"], capture_output=True, text=True).stdout
    return {"node": socket.gethostname(), "os": platform.platform(), "python": platform.python_version(),
            "head": head, "worktree_dirty": bool(dirty.strip()), "code_sha256": digest}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--warm-n", type=int, default=200)
    ap.add_argument("--cold-n", type=int, default=30)
    args = ap.parse_args()

    date = datetime.now().strftime("%Y%m%d")
    run_home = router_home() / "bench-run"
    env = {**os.environ, "PI_ROUTER_HOME": str(run_home), "PI_ROUTER_PORT": str(router_port())}
    os.environ.update({"PI_ROUTER_HOME": str(run_home)})  # rpc_call reads the same port/home
    raw_rows, results = [], {}
    daemon = Daemon(env)

    # cold: first full call and first rpc call after each fresh daemon start
    cold = {"full": [], "rpc": [], "startup_ms": []}
    for i in range(args.cold_n):
        cold["startup_ms"].append(daemon.start())
        layer = "full" if i % 2 == 0 else "rpc"
        r = full_call("l0_regex", env) if layer == "full" else rpc_call("l0_regex")
        cold[layer].append(r)
        raw_rows.append({"state": "cold", "conc": 1, "layer": layer, "kind": "l0_regex", **r})
        daemon.stop()
    results["cold"] = {"full": stats(cold["full"]), "rpc": stats(cold["rpc"]),
                       "daemon_startup_ms": stats([{"ms": m, "neutral": True} for m in cold["startup_ms"]])}

    # warm
    daemon.start()
    try:
        seed_ledger(env)
        for _ in range(20):  # warm-up, not recorded
            full_call("l0_regex", env)
        results["warm"] = {}
        for conc in (1, 3):
            for kind in PAYLOADS:
                for layer, fn in (("full", full_call), ("rpc", rpc_call)):
                    rows = run_batch(fn, kind, env, args.warm_n, conc)
                    raw_rows += [{"state": "warm", "conc": conc, "layer": layer, "kind": kind, **r} for r in rows]
                    results["warm"][f"conc{conc}/{kind}/{layer}"] = stats(rows)
        with urlopen(f"http://{BIND_HOST}:{router_port()}/telemetry", timeout=2) as r:
            daemon_snapshot = json.loads(r.read())
    finally:
        daemon.stop()

    os.environ["PI_ROUTER_HOME"] = str(run_home.parent)
    for row in raw_rows:
        telemetry.append(f"bench_{date}", row)
    out = {
        "schema": "ztc-bench/1", "date": date, "env": env_info(), "budget_ms": BUDGET_MS,
        "protocol": "docs/harness/EVAL_PROTOCOL_ztc.md §3", "warm_n": args.warm_n, "cold_n": args.cold_n,
        "results": results,
        "daemon_handle_ms": daemon_snapshot.get("handle_ms"),
        "daemon_counters": daemon_snapshot.get("counters"),
        "scope": "single node, single run; compare runs only under the same conditions (sequential, no other bench running)",
        "prior_values_note": "이전 값(18 ms·34.2 ms·38.5 ms 등)은 코드 상수로 만든 시뮬 값이며 측정이 아니다",
        "raw": f"$PI_ROUTER_HOME/telemetry/bench_{date}.jsonl",
    }
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    path = METRICS_DIR / f"bench_{date}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(path)


if __name__ == "__main__":
    main()
