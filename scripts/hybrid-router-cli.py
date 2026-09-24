#!/usr/bin/env python3
"""
hybrid-router-cli.py
Command-line interface for the keyword-heuristic router.
Allows direct execution of classification and routing queries,
and displays telemetry with savings marked unmeasured.
"""

import os
import sys
import json
import time
import argparse
from urllib.request import Request, urlopen
from pathlib import Path
from urllib.error import URLError
from router_data_safety import append_bounded_jsonl, mask_text, prepare_error_input, resolve_router_home

REPO_ROOT = Path(__file__).resolve().parent.parent
ROUTER_URL = os.environ.get("ROUTER_URL", "http://127.0.0.1:9876")
PI_ROUTER_HOME = resolve_router_home(REPO_ROOT)
LOG_PATH = PI_ROUTER_HOME / "interventions.jsonl"


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
    prepared = prepare_error_input({"stderr": content})
    payload = {
        "task_type": mask_text(task_type)[:128],
        "content": {"text": prepared["masked_text"]},
        "latency_strict": latency_strict
    }
    if categories_str:
        payload["categories"] = [mask_text(c.strip())[:128] for c in categories_str.split(",") if c.strip()]
        
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
    total_latency = 0.0
    latency_count = 0
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
                    if data.get("cycle") == "hybrid-router-intervention":
                        count += 1
                        recent_events.append(data)
                        if data.get("latency_kind") == "measured_wall_clock":
                            latency = data.get("latency_ms")
                            if isinstance(latency, (int, float)):
                                total_latency += latency
                                latency_count += 1
                except Exception:
                    pass

    avg_latency = round(total_latency / latency_count, 2) if latency_count else None

    print("\n" + "═"*78)
    print(" ⚡ [HYBRID-ROUTER] 관측된 휴리스틱 경로 telemetry")
    print("═"*78)
    print(f" │ 📊 규칙 분류 이벤트   : {count} 회")
    print(" │ 💸 토큰·비용·시간 절감: 미측정 (비교 기준선 없음)")
    print(f" │ ⏱️ 판정 경로 wall-clock: {avg_latency:.2f} ms ({latency_count}개 측정)" if avg_latency is not None else " │ ⏱️ 판정 경로 wall-clock: 미측정")
    print("─"*78)
    print(" 📈 현재 판정 방식: 로컬 키워드 휴리스틱 (모델 추론·해결 성과 미검증)")
    print(" │ 토큰·비용·대기시간 절감은 전후 기준선이 없어 주장하지 않습니다.")
    print("─"*78)
    print(" 🛡️ 최근 규칙 분류 내역 (최신 5건):")
    
    if not recent_events:
        print(" │ (아직 기록된 개입 내역이 없습니다)")
    else:
        for idx, ev in enumerate(recent_events[-5:], 1):
            ts = ev.get("timestamp", "").split("T")[-1][:8]
            desc = ev.get("error_class", ev.get("intervention_type", "분류 이벤트"))
            latency = ev.get("latency_ms") if ev.get("latency_kind") == "measured_wall_clock" else None
            latency_label = f"{latency:.2f}ms" if isinstance(latency, (int, float)) else "미측정"
            print(f" │ [{idx}] {ts} | 절감 미측정 | {latency_label} | {desc[:48]}")
            
def check_milestone_trigger(stage: int, total_stages: int, force: bool = False):
    total = max(total_stages, 1)
    progress_pct = round((stage / total) * 100, 1)
    
    print("\n" + "─"*78)
    print(f" 🎯 [MILESTONE MONITOR] 프로젝트 진행률 평가 : {stage}/{total} 단계 ({progress_pct}%)")
    print("─"*78)

    if progress_pct >= 75.0 or force:
        print(" [MANUAL CHECK] 75% 기준에 도달했습니다.")
        print(" 📊 현재 관측 telemetry를 표시합니다. 자동 lifecycle trigger는 연결돼 있지 않습니다.\n")
        
        # 1. Execute visual HUD
        display_savings_hud()
        
        # 2. Log milestone trigger event
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z") or "2026-09-22T23:25:00+09:00",
            "cycle": "hybrid-router-milestone",
            "intervention_type": "directive",
            "description": f"[MANUAL MILESTONE CHECK] Project reached {progress_pct}% ({stage}/{total} stages). Telemetry displayed.",
            "agent_state": "manual_milestone_telemetry_rendered",
            "progress_percentage": progress_pct
        }
        append_bounded_jsonl(LOG_PATH, entry, REPO_ROOT)
            
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
    subparsers.add_parser("savings", help="Display observed router telemetry; savings remain unmeasured")
    subparsers.add_parser("telemetry", help="Alias for observed router telemetry")
    
    # milestone command (75% trigger)
    milestone_parser = subparsers.add_parser("milestone", help="Manually check project progress and display telemetry at 75 percent")
    milestone_parser.add_argument("--stage", type=int, default=3, help="Current project stage number (e.g. 3)")
    milestone_parser.add_argument("--total", type=int, default=4, help="Total designed project stages (default: 4)")
    milestone_parser.add_argument("--force", action="store_true", help="Force execute 75 percent telemetry trigger")

    # route command
    route_parser = subparsers.add_parser("route", help="Dispatch task to router")
    route_parser.add_argument("--type", default="general", help="Task type (build_error_branching, github_pr_assignment, etc.)")
    route_parser.add_argument("--content", required=True, help="Input content text or error log")
    route_parser.add_argument("--categories", default="", help="Comma-separated options/categories; policy may select the simulated route")
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
