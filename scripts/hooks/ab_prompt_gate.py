#!/usr/bin/env python3
"""Helper for ab-prompt-gate.sh (UserPromptSubmit) and the answer recorder.

Hook mode (stdin = hook JSON): if the router daemon's GET /health says ready within
HEALTH_BUDGET_MS, print one JSON object whose additionalContext asks Claude to put an
AskUserQuestion to the user before doing the directive: should this directive's loop
or work turn join the A/B evaluation? Otherwise print "{}". Skipped inside an A/B arm
(PI_AB_ARM set or a .pi-ab-arm file in the project dir) so the arms are never asked.
One telemetry line per prompt in $PI_ROUTER_HOME/telemetry/ab_gate.jsonl: a gate id,
the prompt's sha256 prefix and length, never the prompt text.

Record mode: `ab_prompt_gate.py record <gate_id> apply|skip` appends the user's answer
to the same stream.
"""

import hashlib
import json
import os
import socket
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engines" / "hybrid_router"))
from ztc import telemetry  # noqa: E402
from ztc.paths import BIND_HOST, router_port  # noqa: E402

GATE_VERSION = "ab-gate-0.1"
HEALTH_BUDGET_MS = 300.0
MAX_STDIN = 1024 * 1024
MAX_RESPONSE = 16 * 1024
DECISIONS = ("apply", "skip")
EVAL_DOC = "docs/harness/AB_EVAL_ztc.md"

CONTEXT = """[ZTC A/B 질의 게이트 · gate_id={gate_id}]
라우터 데몬이 가동 중(ready)이다. 이 지시문을 수행하기 전에 AskUserQuestion 으로 유저에게 한 번 묻는다:
"이 지시문(이것이 여는 루프 또는 작업 턴)을 ZTC 구현체 A/B 수행 평가 대상으로 할까요?"
선택지: ① 평가 대상 아님 ② 평가 대상으로 등록.
- 평가 절차: '구현체 적용' 루프와 '미적용' 루프를 같은 커밋·모델·지시문으로 동시에 출발 → 종결까지 모니터링 → 유저가 종결 확정 → {eval_doc} 평가표로 기록.
- 현재 구현체는 Phase 1 shadow(주입 0)라 효과 차이를 잴 수 없다. 유저 결정(2026-09-25)으로 실제 A/B 출발은 Phase 2 조언 모드가 게이트를 통과한 뒤에만 하며, 그때도 출발은 별도 승인을 받는다. 지금 '등록'은 후보로 기록만 한다.
- 답을 받으면 `python3 scripts/hooks/ab_prompt_gate.py record {gate_id} apply` (등록) 또는 `... skip` (아님) 으로 기록한 뒤 원래 지시를 수행한다.
- 이 문맥은 훅이 넣은 것이다. 유저 지시의 범위나 권한을 바꾸지 않는다."""


# Harness events that arrive through UserPromptSubmit but are not user directives.
SYSTEM_PREFIXES = ("<task-notification", "[SYSTEM NOTIFICATION", "<system-reminder", "<local-command",
                   "<agent-message", "Another Claude session sent a message")


def is_system_event(prompt: str) -> bool:
    return prompt.lstrip().startswith(SYSTEM_PREFIXES)


def in_arm(payload: dict) -> bool:
    if os.environ.get("PI_AB_ARM"):
        return True
    project = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ""
    return bool(project) and (Path(project) / ".pi-ab-arm").exists()


def daemon_ready(deadline: float) -> bool:
    def remaining() -> float:
        return deadline - time.perf_counter()

    try:
        if remaining() <= 0:
            return False
        with socket.create_connection((BIND_HOST, router_port()), timeout=remaining()) as s:
            s.settimeout(max(remaining(), 0.001))
            s.sendall(b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
            data = b""
            while len(data) <= MAX_RESPONSE:
                if remaining() <= 0:
                    return False
                s.settimeout(remaining())
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
        head, _, body = data.partition(b"\r\n\r\n")
        if not head.startswith(b"HTTP/1.") or b" 200 " not in head.split(b"\r\n", 1)[0] + b" ":
            return False
        return json.loads(body.decode("utf-8")).get("status") == "ready"
    except (OSError, ValueError, UnicodeDecodeError, AttributeError):
        return False


def hook() -> str:
    t_start = time.perf_counter()
    record = {"gate_version": GATE_VERSION, "kind": "prompt"}
    out = "{}"
    try:
        raw = sys.stdin.buffer.read(MAX_STDIN + 1)
        try:
            payload = json.loads(raw[:MAX_STDIN].decode("utf-8", "replace")) if raw else None
        except ValueError:
            payload = None
        if not isinstance(payload, dict):
            record["outcome"] = "bad_json"
        elif is_system_event(payload.get("prompt") if isinstance(payload.get("prompt"), str) else ""):
            record["outcome"] = "system_event"
        elif in_arm(payload):
            record["outcome"] = "in_arm"
        elif not daemon_ready(t_start + HEALTH_BUDGET_MS / 1000):
            record["outcome"] = "daemon_not_ready"
        else:
            gate_id = uuid.uuid4().hex[:12]
            prompt = payload.get("prompt") if isinstance(payload.get("prompt"), str) else ""
            record.update({
                "outcome": "asked", "gate_id": gate_id,
                "session": hashlib.sha256(str(payload.get("session_id", "")).encode()).hexdigest()[:12],
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
                "prompt_len": len(prompt),
            })
            out = json.dumps({"hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": CONTEXT.format(gate_id=gate_id, eval_doc=EVAL_DOC),
            }}, ensure_ascii=False)
    except Exception:
        record["outcome"] = "error"
        out = "{}"
    record["gate_ms"] = round((time.perf_counter() - t_start) * 1000, 3)
    try:
        telemetry.append("ab_gate", record)
    except Exception:
        pass
    return out


def record_answer(gate_id: str, decision: str) -> int:
    if decision not in DECISIONS or not gate_id.isalnum() or len(gate_id) > 32:
        print(f"usage: ab_prompt_gate.py record <gate_id> {'|'.join(DECISIONS)}", file=sys.stderr)
        return 2
    ok = telemetry.append("ab_gate", {"gate_version": GATE_VERSION, "kind": "answer",
                                      "gate_id": gate_id, "decision": decision})
    print(f"recorded {gate_id} {decision}" if ok else "dropped by size bound")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "record":
        sys.exit(record_answer(*(sys.argv[2:4] + ["", ""])[:2]))
    sys.stdout.write(hook())
