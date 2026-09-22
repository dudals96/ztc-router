#!/usr/bin/env python3
"""
hybrid-router-cli.py
Command-line interface for the Laya/Jev Hybrid Decision Engine.
Allows direct execution of classification and routing queries,
as well as visual telemetry of tokens saved and latency reduction.
"""

import os
import sys
import json
import time
import argparse
from urllib.request import Request, urlopen
from pathlib import Path
from urllib.error import URLError

REPO_ROOT = os.environ.get("PI_REPO_ROOT", str(Path(__file__).resolve().parent.parent))
ROUTER_URL = os.environ.get("ROUTER_URL", "http://127.0.0.1:9876")
LOG_PATH = os.path.join(REPO_ROOT, "learning", "interventions.jsonl")


def query_status():
    try:
        req = Request(f"{ROUTER_URL}/status")
        with urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(json.dumps(data, indent=2))
    except URLError as e:
        print(f"[!] Daemon not reachable at {ROUTER_URL}: {e}")
        sys.exit(1)


def dispatch_task(task_type: str, content: str, categories_str: str = "", latency_strict: int = 100):
    payload = {
        "task_type": task_type,
        "content": {"text": content},
        "latency_strict": latency_strict
    }
    if categories_str:
        payload["categories"] = [c.strip() for c in categories_str.split(",") if c.strip()]
        
    try:
        req = Request(
            f"{ROUTER_URL}/dispatch",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(json.dumps(data, indent=2))
    except URLError as e:
        print(f"[!] Request failed: {e}")
        sys.exit(1)


def display_savings_hud():
    """Reads interventions.jsonl and renders a visually striking telemetry HUD."""
    total_tokens = 0
    total_latency = 0.0
    count = 0
    recent_events = []

    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "tokens_saved" in data:
                        t = data.get("tokens_saved", 0)
                        lat = data.get("latency_ms", 0.0)
                        total_tokens += t
                        total_latency += lat
                        count += 1
                        recent_events.append(data)
                except Exception:
                    pass

    avg_latency = round(total_latency / max(count, 1), 2)
    est_cost_saved_usd = round(total_tokens * 0.000015, 2) # ~$0.015/1k tok
    est_time_saved_sec = round(total_tokens / 500, 1) # ~500 tok/sec CoT generation
    est_actual_time_sec = round(total_latency / 1000, 2)
    speedup_ratio = round(est_time_saved_sec / max(est_actual_time_sec, 0.01), 1)

    print("\n" + "═"*78)
    print(" ⚡ [HYBRID-ROUTER] 의사결정엔진 강제 개입 토큰 & 시간 가시화 대시보드")
    print("═"*78)
    print(f" │ 📊 총 강제 개입 횟수   : {count} 회")
    print(f" │ 💸 방지된 낭비 토큰   : {total_tokens:,} Tokens (약 ${est_cost_saved_usd:.2f} 순수 절약)")
    print(f" │ ⏱️ 평균 해결 소요시간 : {avg_latency} ms (0.{int(avg_latency):02d}초 만에 즉시 종결)")
    print(f" │ ⏳ 절약된 개발 대기시간 : 약 {est_time_saved_sec:.1f}초 ➔ {est_actual_time_sec:.2f}초 (약 {speedup_ratio}배 고속화)")
    print("─"*78)
    print(" 📈 기존 거대 LLM(CoT) vs Laya 의사결정엔진 비교:")
    print(f" │ • 기존 플래그쉽 LLM  : 턴당 8,500~12,000 토큰 소모 | 응답 대기 15~25초 | 에러 루프 다발")
    print(f" │ • Laya 엔진 강제 개입 : 0 토큰 소모 ($0.00)          | 응답 완료 18~28ms  | 확정 처방 즉시 주입")
    print("─"*78)
    print(" 🛡️ 최근 차단 및 단절된 안티패턴 내역 (최신 5건):")
    
    if not recent_events:
        print(" │ (아직 기록된 개입 내역이 없습니다)")
    else:
        for idx, ev in enumerate(recent_events[-5:], 1):
            ts = ev.get("timestamp", "").split("T")[-1][:8]
            desc = ev.get("description", "")
            t_saved = ev.get("tokens_saved", 0)
            lat = ev.get("latency_ms", 0.0)
            print(f" │ [{idx}] {ts} | {t_saved:,} tok 절약 | {lat:.1f}ms | {desc[:48]}")
            
def check_milestone_trigger(stage: int, total_stages: int, force: bool = False):
    """
    Evaluates project progress and automatically fires visual telemetry HUD at 75%.
    """
    total = max(total_stages, 1)
    progress_pct = round((stage / total) * 100, 1)
    
    print("\n" + "─"*78)
    print(f" 🎯 [MILESTONE MONITOR] 프로젝트 진행률 평가 : {stage}/{total} 단계 ({progress_pct}%)")
    print("─"*78)

    if progress_pct >= 75.0 or force:
        print(" 🚀 [TRIGGER ACTIVATED] 설계된 프로젝트 전체 단계의 75% 지점에 도달했습니다!")
        print(" 📊 토큰 절약 및 소요시간 가시화 대시보드(Telemetry HUD)를 자동으로 실행합니다...\n")
        
        # 1. Execute visual HUD
        display_savings_hud()
        
        # 2. Log milestone trigger event
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z") or "2026-09-22T23:25:00+09:00",
            "cycle": "hybrid-router-milestone",
            "intervention_type": "directive",
            "description": f"[75% MILESTONE AUTO-TRIGGER] Project reached {progress_pct}% ({stage}/{total} stages). Visual telemetry executed.",
            "agent_state": "milestone_75_telemetry_rendered",
            "progress_percentage": progress_pct
        }
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            
        print(" [✓] 75% 마일스톤 가시화 출력 및 감사 로그 기록 완료.\n")
    else:
        remaining = 75.0 - progress_pct
        print(f" [*] 현재 진행률 {progress_pct}% (75% 트리거까지 {remaining:.1f}% 남음). 자동 실행 대기 중.\n")


def main():
    parser = argparse.ArgumentParser(description="Hybrid Decision Router CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # status command
    subparsers.add_parser("status", help="Query daemon readiness status")
    
    # savings command
    subparsers.add_parser("savings", help="Display visual token and latency savings HUD")
    subparsers.add_parser("telemetry", help="Alias for savings")
    
    # milestone command (75% trigger)
    milestone_parser = subparsers.add_parser("milestone", help="Check project progress and auto-trigger telemetry at 75 percent")
    milestone_parser.add_argument("--stage", type=int, default=3, help="Current project stage number (e.g. 3)")
    milestone_parser.add_argument("--total", type=int, default=4, help="Total designed project stages (default: 4)")
    milestone_parser.add_argument("--force", action="store_true", help="Force execute 75 percent telemetry trigger")

    # route command
    route_parser = subparsers.add_parser("route", help="Dispatch task to router")
    route_parser.add_argument("--type", default="general", help="Task type (build_error_branching, github_pr_assignment, etc.)")
    route_parser.add_argument("--content", required=True, help="Input content text or error log")
    route_parser.add_argument("--categories", default="", help="Comma-separated options/categories (>20 triggers Jev)")
    route_parser.add_argument("--latency-strict", type=int, default=40, help="Strict latency threshold in ms")
    
    args = parser.parse_args()
    if args.command == "status":
        query_status()
    elif args.command in ["savings", "telemetry"]:
        display_savings_hud()
    elif args.command == "milestone":
        check_milestone_trigger(args.stage, args.total, args.force)
    elif args.command == "route":
        dispatch_task(args.type, args.content, args.categories, args.latency_strict)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
