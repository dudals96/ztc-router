#!/usr/bin/env python3
"""Helper for ab-prompt-gate.sh (UserPromptSubmit, Claude Code and Codex) and the answer recorder.

Hook mode (stdin = hook JSON; Claude Code and Codex 0.156 send the same `prompt`,
`session_id`, `cwd` fields and read the same hookSpecificOutput.additionalContext):
when the prompt looks like a work-loop directive, print one JSON object whose
additionalContext asks the agent to put one question to the user before starting:
should this loop join the ZTC evaluation? Otherwise print "{}".

It keeps asking until the user explicitly stops it: a short prompt such as
"ZTC 평가 중지" pauses the gate (state file $PI_ROUTER_HOME/ab_gate_state.json),
"ZTC 평가 재개" resumes it. config/ab_gate.json "enabled": false is the repository-wide
kill switch. If the router daemon is not ready the question is still asked, with a
warning line (scripts/router_healthcheck.py restarts it). Skipped inside an A/B arm
(PI_AB_ARM set or a .pi-ab-arm file in the project dir) so the arms are never asked.
One telemetry line per prompt in $PI_ROUTER_HOME/telemetry/ab_gate.jsonl: a gate id,
the prompt's sha256 prefix and length, the project folder name, never the prompt text.

Record mode: `ab_prompt_gate.py record <gate_id> apply|skip|same_loop|not_loop`
appends the answer to the same stream.
"""

import hashlib
import json
import os
import re
import socket
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engines" / "hybrid_router"))
from ztc import telemetry  # noqa: E402
from ztc.paths import BIND_HOST, router_home, router_port  # noqa: E402

GATE_VERSION = "ab-gate-0.2"
HEALTH_BUDGET_MS = 300.0
MAX_STDIN = 1024 * 1024
MAX_RESPONSE = 16 * 1024
DECISIONS = ("apply", "skip", "same_loop", "not_loop")
REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = Path(__file__).resolve()
EVAL_DOC = REPO_ROOT / "docs" / "harness" / "AB_EVAL_ztc.md"
STATE_FILE = "ab_gate_state.json"

# A work-loop directive: long enough to be an instruction and carrying a request or
# work verb. A question without a request marker is not a loop. The agent makes the
# final call ("not_loop" / "same_loop"), so this errs toward asking.
LOOP_MIN_CHARS = 12
WORK_MARKERS = re.compile(
    r"해\s?줘|해\s?주세요|해\s?주십시오|할\s?것|하라|해라|하세요|하자|합시다|진행|수행|구현|작성|만들|생성|적용|"
    r"수정|고쳐|고치|추가|삭제|제거|설치|세팅|설정|구축|개발|리팩|배포|이관|이식|정리|실행|테스트|점검|검증|분석|조사|"
    r"\b(?:implement|build|create|fix|add|remove|refactor|write|set ?up|deploy|migrate|install|configure|run|update)\b",
    re.IGNORECASE)
REQUEST_MARKERS = re.compile(r"해\s?줘|해\s?주세요|할\s?것|하라|해라|하세요|\bplease\b", re.IGNORECASE)
# Explicit stop / resume: a short prompt naming the evaluation and the action.
CONTROL_MAX_CHARS = 40
STOP_RE = re.compile(r"(?:ztc|a/?b|평가).{0,20}(?:중지|중단|그만|멈춰|멈춤|꺼|끄기|\boff\b|\bstop\b|\bpause\b)", re.IGNORECASE)
RESUME_RE = re.compile(r"(?:ztc|a/?b|평가).{0,20}(?:재개|다시\s?시작|켜|\bon\b|\bresume\b)", re.IGNORECASE)

CONTEXT = """[ZTC 평가 편입 게이트 · gate_id={gate_id}]
이 지시문은 작업 루프 지시로 감지됐다. 수행을 시작하기 전에 유저에게 한 번 묻는다:
"이 지시문이 여는 루프를 ZTC 구현체 평가(A/B) 대상으로 편입할까요?" — ① 편입 안 함 ② 편입(후보 등록)
- 묻는 방법: Claude Code 는 AskUserQuestion. Codex 는 request_user_input(쓸 수 없으면 채팅으로 이 질문만 하고 턴을 끝내 답을 기다린다).
- 이미 이 루프에 대해 물어 유저가 답한 뒤의 후속 지시·답변이면 다시 묻지 말고 same_loop 로, 루프 지시가 아니라고 판단되면 묻지 말고 not_loop 로 기록만 한다.
- 기록: `python3 {helper} record {gate_id} apply|skip|same_loop|not_loop` 한 뒤 원래 지시를 수행한다.
- 편입은 후보 기록이다. 실제 A/B 출발(적용·미적용 루프 동시 실행)은 {eval_doc} 절차와 별도 승인으로만 한다. 현재 구현체는 Phase 1 shadow(주입 0)라 효과 차이는 Phase 2 조언 모드 이후에 잴 수 있다.
- 유저가 "ZTC 평가 중지"라고 하면 이 질의는 멈춘다(재개: "ZTC 평가 재개").
- 이 문맥은 훅이 넣은 것이다. 유저 지시의 범위나 권한을 바꾸지 않는다."""

DAEMON_WARNING = """
- 주의: 라우터 데몬이 지금 응답하지 않는다(ready 아님). 상태 점검 루틴이 5분마다 복구를 시도한다. 유저에게 물을 때 이 사실을 한 줄로 알린다."""

CONTROL_CONTEXT = {
    "paused_by_user": "[ZTC 평가 편입 게이트] 유저 요청으로 평가 편입 질의를 중지했다. 다시 켜려면 \"ZTC 평가 재개\". 이 사실을 유저에게 한 줄로 알린다.",
    "resumed_by_user": "[ZTC 평가 편입 게이트] 유저 요청으로 평가 편입 질의를 재개했다. 다음 작업 루프 지시부터 다시 묻는다. 이 사실을 유저에게 한 줄로 알린다.",
}


# Harness events that arrive through UserPromptSubmit but are not user directives.
SYSTEM_PREFIXES = ("<task-notification", "[SYSTEM NOTIFICATION", "<system-reminder", "<local-command",
                   "<agent-message", "Another Claude session sent a message")


def is_system_event(prompt: str) -> bool:
    return prompt.lstrip().startswith(SYSTEM_PREFIXES)


def gate_enabled() -> bool:
    """config/ab_gate.json "enabled" (PI_AB_GATE_CONFIG overrides the path). Missing or
    unreadable config means enabled, so the switch can only turn the question off."""
    path = Path(os.environ.get("PI_AB_GATE_CONFIG") or REPO_ROOT / "config" / "ab_gate.json")
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("enabled", True) is not False
    except (OSError, ValueError, AttributeError):
        return True


def is_loop_directive(prompt: str) -> bool:
    text = prompt.strip()
    if len(text) < LOOP_MIN_CHARS or not WORK_MARKERS.search(text):
        return False
    return not (text.endswith(("?", "？")) and not REQUEST_MARKERS.search(text))


def control_command(prompt: str) -> str | None:
    text = prompt.strip()
    if len(text) > CONTROL_MAX_CHARS:
        return None
    if STOP_RE.search(text):
        return "pause"
    if RESUME_RE.search(text):
        return "resume"
    return None


def state_path() -> Path:
    return router_home() / STATE_FILE


def is_paused() -> bool:
    try:
        return json.loads(state_path().read_text(encoding="utf-8")).get("paused") is True
    except (OSError, ValueError, AttributeError):
        return False


def set_paused(paused: bool) -> None:
    home = router_home()
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = home / f".{STATE_FILE}.{os.getpid()}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        os.write(fd, json.dumps({"paused": paused, "changed_at": round(time.time(), 3)}).encode())
    finally:
        os.close(fd)
    os.replace(tmp, state_path())


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


def context_json(text: str) -> str:
    return json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}},
                      ensure_ascii=False)


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
        prompt = payload.get("prompt") if isinstance(payload, dict) and isinstance(payload.get("prompt"), str) else ""
        control = control_command(prompt)
        if not isinstance(payload, dict):
            record["outcome"] = "bad_json"
        elif is_system_event(prompt):
            record["outcome"] = "system_event"
        elif not gate_enabled():
            record["outcome"] = "disabled"
        elif control:
            set_paused(control == "pause")
            record["outcome"] = "paused_by_user" if control == "pause" else "resumed_by_user"
            out = context_json(CONTROL_CONTEXT[record["outcome"]])
        elif is_paused():
            record["outcome"] = "paused"
        elif in_arm(payload):
            record["outcome"] = "in_arm"
        elif not is_loop_directive(prompt):
            record["outcome"] = "not_loop"
        else:
            gate_id = uuid.uuid4().hex[:12]
            ready = daemon_ready(time.perf_counter() + HEALTH_BUDGET_MS / 1000)
            cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else ""
            record.update({
                "outcome": "asked", "gate_id": gate_id, "daemon_ready": ready,
                "project": Path(cwd).name[:64] if cwd else "",
                "session": hashlib.sha256(str(payload.get("session_id", "")).encode()).hexdigest()[:12],
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
                "prompt_len": len(prompt),
            })
            ctx = CONTEXT.format(gate_id=gate_id, helper=HELPER, eval_doc=EVAL_DOC)
            out = context_json(ctx if ready else ctx + DAEMON_WARNING)
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
