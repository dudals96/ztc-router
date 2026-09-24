#!/usr/bin/env python3
"""
hybrid-router-cli.py
Command-line interface for the keyword-heuristic router daemon.
Dispatches masked routing queries and shows observed telemetry.
Token, cost and time savings are not measured and are never claimed here.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "engines" / "hybrid_router"))
from ztc import telemetry  # noqa: E402
from ztc.masking import mask_text  # noqa: E402
from ztc.paths import router_port  # noqa: E402

ROUTER_URL = f"http://127.0.0.1:{router_port()}"
LABEL_LIMIT = 128


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
        "task_type": mask_text(task_type, limit=LABEL_LIMIT),
        "content": {"text": mask_text(content)},
        "latency_strict": latency_strict,
    }
    if categories_str:
        payload["categories"] = [mask_text(c.strip(), limit=LABEL_LIMIT) for c in categories_str.split(",") if c.strip()]

    try:
        req = Request(
            f"{ROUTER_URL}/dispatch",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(json.dumps(data, indent=2))
    except URLError as e:
        print(f"[!] Request failed: {e}")
        sys.exit(1)


def display_telemetry_hud():
    """Summarise observed router events from PI_ROUTER_HOME/telemetry/router_events.jsonl."""
    events = [e for e in telemetry.read("router_events") if e.get("kind") in ("observe", "classify", "intercept")]
    handle_ms = [e["handle_ms"] for e in events if isinstance(e.get("handle_ms"), (int, float))]
    p50 = telemetry.percentile(handle_ms, 50)
    p99 = telemetry.percentile(handle_ms, 99)

    print("\n" + "═" * 78)
    print(" [HYBRID-ROUTER] 관측된 휴리스틱 경로 telemetry")
    print("═" * 78)
    print(f" │ 규칙 판정 이벤트        : {len(events)} 회")
    print(" │ 토큰·비용·시간 절감     : 미측정 (비교 기준선 없음)")
    if p50 is None:
        print(" │ 데몬 내부 처리 시간     : 미측정")
    else:
        print(f" │ 데몬 내부 처리 시간     : p50 {p50:.2f} ms / p99 {p99:.2f} ms ({len(handle_ms)}개 측정, 훅 전체 지연 아님)")
    print("─" * 78)
    print(" 현재 판정 방식: 로컬 키워드 휴리스틱 + L0 정규식·시그니처 원장 (모델 추론·해결 성과 미검증)")
    print(" │ 토큰·비용·대기시간 절감은 전후 기준선이 없어 주장하지 않습니다.")
    print("─" * 78)
    print(" 최근 판정 내역 (최신 5건):")
    if not events:
        print(" │ (아직 기록된 판정이 없습니다)")
        return
    for idx, ev in enumerate(events[-5:], 1):
        ts = time.strftime("%H:%M:%S", time.localtime(ev.get("ts", 0)))
        desc = ev.get("error_class") or ev.get("source") or ev.get("kind")
        ms = ev.get("handle_ms")
        label = f"{ms:.2f}ms" if isinstance(ms, (int, float)) else "미측정"
        print(f" │ [{idx}] {ts} | 절감 미측정 | {label} | {str(desc)[:48]}")


def check_milestone(stage: int, total_stages: int, force: bool = False):
    total = max(total_stages, 1)
    progress_pct = round((stage / total) * 100, 1)

    print("\n" + "─" * 78)
    print(f" 프로젝트 진행률: {stage}/{total} 단계 ({progress_pct}%)")
    print("─" * 78)

    if progress_pct >= 75.0 or force:
        print(" [MANUAL CHECK] 75% 기준에 도달했습니다. 자동 lifecycle trigger 는 연결돼 있지 않습니다.\n")
        display_telemetry_hud()
        try:
            telemetry.append("router_events", {
                "kind": "milestone", "stage": stage, "total": total, "progress_percentage": progress_pct,
            })
        except OSError:
            print(" [!] telemetry 기록 실패 (표시는 완료).")
    else:
        print(f" 75% 기준 미달 ({progress_pct}%). telemetry 표시는 --force 로만 실행합니다.")


def main():
    parser = argparse.ArgumentParser(description="Hybrid Decision Router CLI (keyword heuristic)")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    subparsers.add_parser("status", help="Query daemon readiness status")
    subparsers.add_parser("savings", help="Display observed router telemetry; savings remain unmeasured")
    subparsers.add_parser("telemetry", help="Alias for savings")

    milestone_parser = subparsers.add_parser("milestone", help="Manually check project progress and display telemetry at 75 percent")
    milestone_parser.add_argument("--stage", type=int, default=3, help="Current project stage number (e.g. 3)")
    milestone_parser.add_argument("--total", type=int, default=4, help="Total designed project stages (default: 4)")
    milestone_parser.add_argument("--force", action="store_true", help="Display telemetry regardless of progress")

    route_parser = subparsers.add_parser("route", help="Dispatch task to router")
    route_parser.add_argument("--type", default="general", help="Task type (build_error_branching, github_pr_assignment, etc.)")
    route_parser.add_argument("--content", required=True, help="Input content text or error log (masked before sending)")
    route_parser.add_argument("--categories", default="", help="Comma-separated options/categories; routing policy decides the route")
    route_parser.add_argument("--latency-strict", type=int, default=40, help="Strict latency threshold in ms")

    args = parser.parse_args()
    if args.command == "status":
        query_status()
    elif args.command in ["savings", "telemetry"]:
        display_telemetry_hud()
    elif args.command == "milestone":
        check_milestone(args.stage, args.total, args.force)
    elif args.command == "route":
        dispatch_task(args.type, args.content, args.categories, args.latency_strict)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
