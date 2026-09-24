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
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

from pathlib import Path
from router_data_safety import resolve_router_home

REPO_ROOT = Path(__file__).resolve().parent.parent
PI_ROUTER_HOME = resolve_router_home(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT / "engines" / "hybrid_router"))
from router_core import HybridDecisionRouter

TAILNET_NODES = {
    "SYSTEM-1 (MacBook Pro)": "100.74.61.51",
    "SYSTEM-2 (desktop-1q6j3e6)": "100.101.16.70",
    "SYSTEM-3 (nv-gigabyte)": "100.75.98.124",
    "SYSTEM-4 (richardkim-i7)": "100.90.58.94"
}

ROUTER_PORT = 9876
router_instance = None


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


def run_echo_ping_verification():
    print("\n========================================================")
    print("  TAILNET DISTRIBUTED ECHO PING VERIFICATION (4 NODES)")
    print("========================================================")
    all_ok = True
    for node_name, ip in TAILNET_NODES.items():
        t0 = time.perf_counter()
        if ip == "100.74.61.51":
            # Local loopback on System 1
            print(f"[*] {node_name} [{ip}]: REACHABLE (Local Loopback, < 0.1ms)")
            continue
            
        try:
            res = subprocess.run(
                ["ping", "-c", "1", "-W", "1500", ip],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3
            )
            rtt = round((time.perf_counter() - t0) * 1000, 2)
            if res.returncode == 0:
                print(f"[✓] {node_name} [{ip}]: ECHO PING SUCCESS (RTT: {rtt}ms)")
            else:
                print(f"[!] {node_name} [{ip}]: PING TIMEOUT / UNREACHABLE")
                all_ok = False
        except Exception as e:
            print(f"[!] {node_name} [{ip}]: PING FAILED ({e})")
            all_ok = False
            
    print("========================================================\n")
    return all_ok


class RouterHTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health" or self.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            status_payload = {
                "status": "ready",
                "signal": "Keyword heuristic router ready",
                "daemon": "HYBRID-ROUTER",
                "port": ROUTER_PORT,
                "timestamp": time.time()
            }
            self.wfile.write(json.dumps(status_payload).encode("utf-8"))

        elif self.path == "/telemetry":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            
            log_path = PI_ROUTER_HOME / "interventions.jsonl"
            telemetry_data = load_telemetry_data(log_path)
            self.wfile.write(json.dumps(telemetry_data).encode("utf-8"))

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
        <span>DAEMON READY : PORT 9876</span>
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
</html>"""
            self.wfile.write(html_content.encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/route" or self.path == "/dispatch":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                task = json.loads(body.decode("utf-8"))
                result = router_instance.dispatch(task)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Quiet standard HTTP logs
        return


def start_daemon():
    global router_instance
    print("[INIT] Initializing Hybrid Decision Router Core...")
    router_instance = HybridDecisionRouter()
    
    # 1. Run Pre-Flight Echo Ping
    run_echo_ping_verification()
    
    # 2. Warm up local routing paths
    warmup_task = {"task_type": "build_error_branching", "content": {"log": "init warmup"}}
    warmup_res = router_instance.dispatch(warmup_task)
    print(f"[WARMUP] Local Engine Warmup Completed. Latency: {warmup_res['total_pipeline_latency_ms']}ms")

    # 3. Emit the required readiness signal
    print("\n" + "="*70)
    print(">>> [SIGNAL] Keyword heuristic router ready <<<")
    print("======================================================================")
    print(f"[*] Background Listener active on http://127.0.0.1:{ROUTER_PORT}")
    print(f"[*] Serving Anti-Gravity Sidebar Extension & CLI Clients")
    print("[*] Mode: local keyword heuristics and keyword-match simulation")
    print("======================================================================\n")

    # 4. Start HTTP Server (bind 0.0.0.0 to allow Tailnet peers access)
    server = HTTPServer(("0.0.0.0", ROUTER_PORT), RouterHTTPHandler)
    server.serve_forever()


if __name__ == "__main__":
    start_daemon()
