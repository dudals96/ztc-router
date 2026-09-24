#!/usr/bin/env python3
"""
hybrid-router-daemon.py
Local ZTC router daemon (Phase 1, shadow).

- Binds 127.0.0.1 only (not configurable). Port: PI_ROUTER_PORT (default 9876).
- ThreadingHTTPServer, request body limit 64 KB (413), per-request id (X-Request-Id).
- POST /v1/observe  : shadow hook observations. Synchronous answer is L0 only
                      (regex, then signature ledger). Misses go to the bounded judge queue,
                      whose Phase 1 judge is the local keyword heuristic (candidate rows only).
- POST /dispatch    : router_core dispatch (policy-driven), kept for the CLI.
- GET  /health      : 200 only if the ledger answers and the judge worker is alive, else 503.
- GET  /telemetry   : counters and measured latency percentiles. No commands, cwd or paths.
- GET  /dashboard   : the same numbers as HTML.
Raw data lives under PI_ROUTER_HOME. Nothing here is returned to an agent.
"""

import json
import re
import signal
import sys
import threading
import time
import uuid
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "engines" / "hybrid_router"))
from router_core import HybridDecisionRouter
from ztc import l0, telemetry
from ztc.judge_queue import JudgeQueue
from ztc.masking import mask_text
from ztc.paths import BIND_HOST, ledger_path, router_home, router_port

MAX_BODY_BYTES = 64 * 1024
HANDLER_SOCKET_TIMEOUT_SEC = 2.0
LATENCY_WINDOW = 2000
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")
KNOWN_ERROR_CLASSES = {"syntax_compile", "dependency_missing", "lint_formatting", "permission_auth",
                       "timeout_deadlock", "out_of_memory", "network_partition"}


class RouterState:
    def __init__(self):
        self.started_at = time.time()
        self.rules = l0.load_rules()
        self.policy = l0.policy_version()
        self.signatures = l0.compile_signatures(self.rules)
        self.attr = l0.attribution()
        self.ledger = l0.Ledger(ledger_path(), self.policy)
        self.router = HybridDecisionRouter()
        self.queue = JudgeQueue(self._judge)
        self._lock = threading.Lock()
        self.counters = {"observe": 0, "l0_regex": 0, "l0_ledger": 0, "miss": 0, "pre": 0,
                         "rejected_413": 0, "rejected_400": 0, "errors": 0}
        self.handle_ms = deque(maxlen=LATENCY_WINDOW)

    def _judge(self, sig: str, payload: dict) -> None:
        """Async judge (Phase 1): local heuristic -> candidate row. No promotion."""
        res = self.router.local.predict({"log": payload["text"]})
        decision = res.get("decision", "")
        error_class = decision if decision in KNOWN_ERROR_CLASSES else "unclassified"
        self.ledger.put_candidate(sig, error_class, "heuristic", res.get("engine", "keyword-heuristic"),
                                  str(payload.get("client_version") or "unknown")[:32], self.attr)

    def bump(self, key: str, ms: float | None = None) -> None:
        with self._lock:
            self.counters[key] = self.counters.get(key, 0) + 1
            if ms is not None:
                self.handle_ms.append(ms)

    def observe(self, body: dict, request_id: str) -> dict:
        t0 = time.perf_counter()
        event = str(body.get("event", ""))[:32]
        program = mask_text(body.get("program", ""), limit=60)
        text = mask_text(body.get("text", ""))  # re-mask: the daemon does not trust the client
        verdict, queued = None, None
        post = event in ("PostToolUse", "PostToolUseFailure")
        if post and text:
            sig = l0.signature(program, text, self.signatures)
            cls = l0.classify_regex(text, self.signatures)
            if cls:
                verdict = {"error_class": cls, "source": "l0_regex", "signature": sig, "state": None}
            else:
                row = self.ledger.lookup(sig)
                if row:
                    verdict = {"error_class": row["error_class"], "source": "l0_ledger", "signature": sig, "state": row["state"]}
                else:
                    queued = self.queue.submit(sig, {"text": text, "client_version": body.get("client_version")})
        source = verdict["source"] if verdict else ("miss" if post and text else ("no_text" if post else "pre"))
        ms = (time.perf_counter() - t0) * 1000
        self.bump("observe")
        self.bump(source, ms)
        try:
            telemetry.append("router_events", {
                "kind": "observe", "request_id": request_id, "event": event, "program": program,
                "exit_code": body.get("exit_code"), "source": source,
                "error_class": verdict["error_class"] if verdict else None,
                "signature": verdict["signature"] if verdict else None, "queued": queued,
                "handle_ms": round(ms, 4),
            })
        except OSError:
            self.bump("errors")
        return {"request_id": request_id, "verdict": verdict, "queued": queued}

    def healthy(self) -> tuple[bool, dict]:
        try:
            ledger_ok = self.ledger.ping()
        except Exception:
            ledger_ok = False
        worker_ok = self.queue.alive()
        return ledger_ok and worker_ok, {"ledger": ledger_ok, "judge_worker": worker_ok, "queue_depth": self.queue.depth()}

    def snapshot(self) -> dict:
        with self._lock:
            lat = list(self.handle_ms)
            counters = dict(self.counters)
        return {
            "uptime_sec": round(time.time() - self.started_at, 1),
            "policy_version": self.policy,
            "counters": counters,
            "handle_ms": {f"p{q}": telemetry.percentile(lat, q) for q in (50, 95, 99)},
            "handle_ms_window": len(lat),
            "queue": {**self.queue.stats, "depth": self.queue.depth(), "capacity": self.queue.capacity},
            "ledger": self.ledger.counts(),
            "note": "measured values only; earlier dashboard figures (18 ms, 800x, 99.8%) were constants, not measurements",
        }

    def close(self) -> None:
        self.queue.shutdown()
        self.ledger.close()


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"><title>ZTC Router (shadow)</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>body{font-family:-apple-system,sans-serif;margin:24px;background:#fff;color:#111}
@media (prefers-color-scheme: dark){body{background:#111;color:#eee}}
pre{white-space:pre-wrap;font-size:13px}</style></head>
<body><h1>ZTC Router — shadow mode</h1>
<p>실측값만 표시한다. 에이전트에 주입되는 것은 없다. 이전 대시보드의 18 ms·800배·99.8% 는 코드 상수였다.</p>
<pre id="t">loading…</pre>
<script>async function r(){try{const x=await fetch('/telemetry');document.getElementById('t').textContent=
JSON.stringify(await x.json(),null,2)}catch(e){document.getElementById('t').textContent='unreachable'}}
r();setInterval(r,3000);</script></body></html>"""


def make_handler(state: RouterState):
    class RouterHTTPHandler(BaseHTTPRequestHandler):
        timeout = HANDLER_SOCKET_TIMEOUT_SEC
        server_version = "ztc-router/1"
        sys_version = ""

        def _request_id(self) -> str:
            rid = self.headers.get("X-Request-Id", "")
            return rid if REQUEST_ID_RE.match(rid) else uuid.uuid4().hex[:16]

        def _send(self, code: int, payload, request_id: str, content_type: str = "application/json") -> None:
            data = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Request-Id", request_id)
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)
            self.close_connection = True

        def _read_json(self, rid: str):
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self._send(411, {"error": "length_required"}, rid)
                return None
            if length > MAX_BODY_BYTES:
                state.bump("rejected_413")
                self._send(413, {"error": "payload_too_large", "limit": MAX_BODY_BYTES}, rid)
                return None
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                state.bump("rejected_400")
                self._send(400, {"error": "invalid_json"}, rid)
                return None

        def do_GET(self):
            rid = self._request_id()
            if self.path in ("/health", "/status"):
                ok, detail = state.healthy()
                self._send(200 if ok else 503, {"status": "ready" if ok else "degraded", **detail}, rid)
            elif self.path == "/telemetry":
                self._send(200, state.snapshot(), rid)
            elif self.path in ("/dashboard", "/"):
                self._send(200, DASHBOARD_HTML.encode("utf-8"), rid, "text/html; charset=utf-8")
            else:
                self._send(404, {"error": "not_found"}, rid)

        def do_POST(self):
            rid = self._request_id()
            if self.path not in ("/v1/observe", "/dispatch", "/route"):
                self._send(404, {"error": "not_found"}, rid)
                return
            body = self._read_json(rid)
            if body is None:
                return
            if not isinstance(body, dict):
                state.bump("rejected_400")
                self._send(400, {"error": "invalid_json"}, rid)
                return
            try:
                result = state.observe(body, rid) if self.path == "/v1/observe" else state.router.dispatch(body)
            except Exception as exc:
                state.bump("errors")
                self._send(500, {"error": type(exc).__name__}, rid)
                return
            self._send(200, result, rid)

        def log_message(self, format, *args):
            return

    return RouterHTTPHandler


def make_server(port: int | None = None) -> tuple[ThreadingHTTPServer, RouterState]:
    state = RouterState()
    server = ThreadingHTTPServer((BIND_HOST, router_port() if port is None else port), make_handler(state))
    server.daemon_threads = True
    return server, state


def main() -> None:
    server, state = make_server()
    host, port = server.server_address[:2]

    def stop(signum, frame):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(f"[ztc-router] listening on http://{host}:{port} (home {router_home()}, policy {state.policy})", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        state.close()
        print("[ztc-router] stopped", flush=True)


if __name__ == "__main__":
    main()
