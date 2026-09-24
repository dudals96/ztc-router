#!/usr/bin/env python3
"""
hybrid-router-daemon.py
Local daemon for the configurable keyword-heuristic router.
Features:
  1. HTTP listener for router status, telemetry, and dispatch.
  2. Routing through keyword heuristics or a local keyword-match simulation.
"""

import os
import sys
import json
import time
import threading
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from pathlib import Path
from router_data_safety import resolve_router_home
from router_daemon_runtime import ShadowEventQueue

REPO_ROOT = Path(__file__).resolve().parent.parent
PI_ROUTER_HOME = resolve_router_home(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT / "engines" / "hybrid_router"))
from router_core import HybridDecisionRouter

ROUTER_HOST = "127.0.0.1"
MAX_BODY_BYTES = 64 * 1024
MAX_ACTIVE_REQUESTS = 4


def resolve_router_port() -> int:
    try:
        port = int(os.environ.get("PI_ROUTER_PORT", "9876"))
    except ValueError as exc:
        raise RuntimeError("PI_ROUTER_PORT must be an integer") from exc
    if not 1024 <= port <= 65535:
        raise RuntimeError("PI_ROUTER_PORT must be between 1024 and 65535")
    return port


ROUTER_PORT = resolve_router_port()
router_instance = None
SHADOW_QUEUE = ShadowEventQueue(PI_ROUTER_HOME / "interventions.jsonl", REPO_ROOT)


def load_telemetry_data(log_path):
    events = []
    if log_path.exists():
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if event.get("cycle") == "hybrid-router-intervention":
                        events.append({
                            key: event[key]
                            for key in ("timestamp", "intervention_type", "error_class", "latency_ms", "latency_kind")
                            if key in event
                        })
                except (json.JSONDecodeError, TypeError):
                    continue

    measured_latencies = [
        event["latency_ms"]
        for event in events
        if event.get("latency_kind") == "measured_wall_clock"
        and isinstance(event.get("latency_ms"), (int, float))
    ]
    return {
        "interventions_count": len(events),
        "savings_status": "unmeasured",
        "avg_latency_ms": round(sum(measured_latencies) / len(measured_latencies), 2) if measured_latencies else None,
        "latency_samples": len(measured_latencies),
        "recent_events": events[-10:]
    }


class RouterHTTPHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _read_payload(self) -> tuple[object | None, tuple[int, str] | None]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None or not raw_length.isdecimal():
            return None, (400, "invalid request")
        content_length = int(raw_length)
        if content_length > MAX_BODY_BYTES:
            return None, (413, "request too large")
        body = self.rfile.read(content_length)
        if len(body) != content_length:
            return None, (400, "invalid request")
        try:
            return json.loads(body.decode("utf-8")), None
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, (400, "invalid request")

    def do_GET(self):
        if self.path == "/health" or self.path == "/status":
            queue_status = SHADOW_QUEUE.status()
            ready = router_instance is not None and queue_status["ready"] and not queue_status["write_error_count"]
            status_payload = {
                "status": "ready" if ready else "degraded",
                "signal": "Keyword heuristic router ready",
                "daemon": "HYBRID-ROUTER",
                "port": self.server.server_port,
                "timestamp": time.time(),
                "router_ready": router_instance is not None,
                "shadow_queue": queue_status,
            }
            self._send_json(200 if ready else 503, status_payload)

        elif self.path == "/telemetry":
            log_path = PI_ROUTER_HOME / "interventions.jsonl"
            telemetry_data = load_telemetry_data(log_path)
            self._send_json(200, telemetry_data)

        elif self.path == "/dashboard" or self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            
            html_content = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>HYBRID-ROUTER 규칙 분류 telemetry</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root {
      --bg: #090d16;
      --card-bg: rgba(22, 30, 49, 0.7);
      --card-border: rgba(59, 130, 246, 0.2);
      --accent: #3b82f6;
      --accent-glow: rgba(59, 130, 246, 0.35);
      --green: #10b981;
      --green-glow: rgba(16, 185, 129, 0.3);
      --text: #f3f4f6;
      --text-muted: #9ca3af;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", sans-serif;
      background: radial-gradient(circle at 50% 0%, #172554 0%, var(--bg) 60%);
      color: var(--text);
      min-height: 100vh;
      padding: 30px 20px;
    }
    .container { max-width: 1100px; margin: 0 auto; }
    header {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 28px; padding-bottom: 20px;
      border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .badge {
      display: inline-flex; align-items: center; gap: 6px;
      background: rgba(16, 185, 129, 0.15); color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.3);
      padding: 6px 14px; border-radius: 9999px; font-size: 0.85rem; font-weight: 600;
    }
    .badge .dot { width: 8px; height: 8px; background: #34d399; border-radius: 50%; box-shadow: 0 0 8px #34d399; }
    h1 { font-size: 1.6rem; font-weight: 700; letter-spacing: -0.5px; }
    .subtitle { color: var(--text-muted); font-size: 0.95rem; margin-top: 4px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 16px; margin-bottom: 28px; }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      backdrop-filter: blur(12px);
      border-radius: 16px;
      padding: 22px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.3);
      transition: transform 0.2s, border-color 0.2s;
    }
    .card:hover { transform: translateY(-2px); border-color: rgba(59, 130, 246, 0.5); }
    .card-title { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); margin-bottom: 8px; }
    .card-val { font-size: 2rem; font-weight: 800; color: #fff; }
    .card-val.green { color: #34d399; text-shadow: 0 0 16px var(--green-glow); }
    .card-val.blue { color: #60a5fa; text-shadow: 0 0 16px var(--accent-glow); }
    .card-desc { font-size: 0.8rem; color: var(--text-muted); margin-top: 6px; }
    .comparison-section {
      background: var(--card-bg); border: 1px solid var(--card-border);
      border-radius: 16px; padding: 24px; margin-bottom: 28px;
    }
    .comp-bar { margin: 16px 0 10px; }
    .bar-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
    .bar-label { font-size: 0.9rem; font-weight: 600; width: 180px; }
    .bar-track { flex: 1; height: 12px; background: rgba(255,255,255,0.06); border-radius: 6px; overflow: hidden; margin: 0 16px; }
    .bar-fill { height: 100%; border-radius: 6px; transition: width 0.5s; }
    .fill-red { background: linear-gradient(90deg, #f87171, #ef4444); }
    .fill-green { background: linear-gradient(90deg, #34d399, #10b981); }
    .bar-time { font-size: 0.9rem; font-weight: 700; width: 80px; text-align: right; }
    table { width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 0.85rem; }
    th { text-align: left; padding: 12px 10px; border-bottom: 1px solid rgba(255,255,255,0.1); color: var(--text-muted); font-weight: 600; }
    td { padding: 12px 10px; border-bottom: 1px solid rgba(255,255,255,0.04); }
    tr:hover td { background: rgba(255,255,255,0.02); }
    .pill { display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 600; }
    .pill-green { background: rgba(16, 185, 129, 0.15); color: #34d399; }
    .pill-blue { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <h1>⚡ HYBRID-ROUTER telemetry</h1>
        <div class="subtitle">키워드 휴리스틱 경로 관측; 절감·해결 성과는 미측정</div>
      </div>
      <div class="badge">
        <span class="dot"></span>
        <span>DAEMON READY : PORT __ROUTER_PORT__</span>
      </div>
    </header>

    <div class="grid">
      <div class="card">
        <div class="card-title">토큰·비용 절감</div>
        <div class="card-val green" id="stat-savings">미측정</div>
        <div class="card-desc">비교 기준선 없음</div>
      </div>
      <div class="card">
        <div class="card-title">판정 경로 시간 평균</div>
        <div class="card-val blue" id="stat-lat">-</div>
        <div class="card-desc">측정된 wall-clock 표본만 표시</div>
      </div>
      <div class="card">
        <div class="card-title">해결 성과</div>
        <div class="card-val green" id="stat-resolution">미측정</div>
        <div class="card-desc">분류 결과만으로 해결을 판정하지 않음</div>
      </div>
      <div class="card">
        <div class="card-title">규칙 분류 이벤트</div>
        <div class="card-val" id="stat-count">-</div>
        <div class="card-desc">이벤트 수는 해결 횟수가 아님</div>
      </div>
    </div>

    <div class="comparison-section">
      <h3>현재 판정 방식</h3>
      <p>로컬 키워드 휴리스틱과 로컬 키워드 일치 시뮬레이션을 사용합니다. 모델 추론, 토큰·비용 절감, 실제 해결 여부는 이 telemetry로 입증되지 않습니다.</p>
    </div>

    <div class="comparison-section">
      <h3>🛡️ 실시간 강제 개입 및 차단 내역 (Live Feed)</h3>
      <table>
        <thead>
          <tr>
            <th>시각</th>
            <th>구분</th>
            <th>절감</th>
            <th>판정 경로 시간</th>
            <th>이벤트 유형</th>
          </tr>
        </thead>
        <tbody id="events-table">
          <tr><td colspan="5" style="text-align:center; color: var(--text-muted);">데이터를 불러오는 중...</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <script>
    async function refreshData() {
      try {
        const res = await fetch('/telemetry');
        const data = await res.json();
        document.getElementById('stat-savings').innerText = '미측정';
        document.getElementById('stat-lat').innerText = Number.isFinite(data.avg_latency_ms) ? data.avg_latency_ms.toFixed(2) + ' ms' : '미측정';
        document.getElementById('stat-resolution').innerText = '미측정';
        document.getElementById('stat-count').innerText = data.interventions_count + ' 회';

        const tbody = document.getElementById('events-table');
        if (data.recent_events && data.recent_events.length > 0) {
          tbody.innerHTML = data.recent_events.reverse().map(ev => {
            const time = (ev.timestamp || '').split('T')[1]?.substring(0, 8) || '-';
            const isSkill = ev.intervention_type === 'directive';
            const pillClass = isSkill ? 'pill-blue' : 'pill-green';
            const typeLabel = ev.intervention_type || '분류 이벤트';
            return `<tr>
              <td>${time}</td>
              <td><span class="pill ${pillClass}">${typeLabel}</span></td>
              <td>미측정</td>
              <td>${ev.latency_kind === 'measured_wall_clock' && Number.isFinite(ev.latency_ms) ? Number(ev.latency_ms).toFixed(2) + ' ms' : '미측정'}</td>
              <td>규칙 기반 분류; 해결 성과 미측정</td>
            </tr>`;
          }).join('');
        }
      } catch (e) {
        console.error("Telemetry fetch failed:", e);
      }
    }
    refreshData();
    setInterval(refreshData, 3000);
  </script>
</body>
</html>""".replace("__ROUTER_PORT__", str(ROUTER_PORT))
            self.wfile.write(html_content.encode("utf-8"))

        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        payload, error = self._read_payload()
        if error:
            self._send_json(error[0], {"error": error[1]})
            return

        if self.path == "/shadow":
            try:
                accepted, result = SHADOW_QUEUE.enqueue(payload)
            except ValueError:
                self._send_json(400, {"error": "invalid request"})
                return
            status_code = 202 if accepted else (409 if result == "cancelled" else 503)
            self._send_json(status_code, {"accepted": accepted, "status": result})
        elif self.path == "/cancel":
            if not isinstance(payload, dict) or set(payload) != {"requestId"}:
                self._send_json(400, {"error": "invalid request"})
                return
            cancelled = SHADOW_QUEUE.cancel(payload.get("requestId"))
            self._send_json(202 if cancelled else 400, {"cancelled": cancelled})
        elif self.path == "/route" or self.path == "/dispatch":
            if not isinstance(payload, dict) or set(payload) - {"task_type", "content", "categories", "tokens_count", "latency_strict", "instructions"}:
                self._send_json(400, {"error": "invalid request"})
                return
            content = payload.get("content", {})
            categories = payload.get("categories", [])
            task_type = payload.get("task_type", "general")
            if (
                not isinstance(task_type, str)
                or len(task_type) > 128
                or not isinstance(content, dict)
                or len(content) > 32
                or any(not isinstance(key, str) or len(key) > 128 for key in content)
                or any(not isinstance(value, (str, int, float, bool, type(None))) for value in content.values())
                or len(json.dumps(content).encode("utf-8")) > MAX_BODY_BYTES // 2
                or not isinstance(categories, list)
                or len(categories) > 100
                or any(not isinstance(item, str) or len(item) > 128 for item in categories)
                or any(
                    isinstance(payload.get(key), bool)
                    or not isinstance(payload.get(key), int)
                    or not 0 <= payload[key] <= 600000
                    for key in ("tokens_count", "latency_strict")
                    if key in payload
                )
                or ("instructions" in payload and (not isinstance(payload["instructions"], str) or len(payload["instructions"]) > 1024))
                or router_instance is None
            ):
                self._send_json(400, {"error": "invalid request"})
                return
            try:
                result = router_instance.dispatch(payload)
                self._send_json(200, result)
            except Exception:
                self._send_json(500, {"error": "dispatch failed"})
        else:
            self._send_json(404, {"error": "not found"})

    def log_message(self, format, *args):
        # Quiet standard HTTP logs
        return


def start_daemon():
    global router_instance
    router_instance = HybridDecisionRouter()
    server = BoundedThreadingHTTPServer((ROUTER_HOST, ROUTER_PORT), RouterHTTPHandler)
    signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        SHADOW_QUEUE.start()
        if not SHADOW_QUEUE.status()["ready"]:
            raise RuntimeError("shadow event queue did not become ready")
        print(f"Keyword heuristic router listening on http://{ROUTER_HOST}:{ROUTER_PORT}")
        server.serve_forever(poll_interval=0.05)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        stopped = SHADOW_QUEUE.stop()
        if not stopped:
            print("Shadow event queue did not stop cleanly", file=sys.stderr)


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    request_queue_size = 8
    daemon_threads = True

    def __init__(self, server_address, handler_class):
        self.request_slots = threading.BoundedSemaphore(MAX_ACTIVE_REQUESTS)
        super().__init__(server_address, handler_class)

    def process_request(self, request, client_address):
        if not self.request_slots.acquire(blocking=False):
            try:
                request.settimeout(0.1)
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.request_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.request_slots.release()


def _handle_sigterm(_signum, _frame):
    raise KeyboardInterrupt


if __name__ == "__main__":
    start_daemon()
