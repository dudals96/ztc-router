#!/usr/bin/env python3
"""
decision-gate-interceptor.py
PreToolUse & PostToolUse Interceptor for Coding Agents (Claude Code, Anti-Gravity IDE, Codex).
Detects anti-patterns:
  1. Excessive Skill Generation: Applies the configured file-path rule.
  2. Repetitive Error Loops: Classifies failed-command text with local keyword rules.
Token and cost savings are unmeasured; returned actions do not prove resolution.
Logs detailed intervention events to the configured router data directory.
"""

import os
import sys
import re
import json
import time
import argparse
from typing import Dict, Any, Optional
from urllib.request import Request, urlopen
from pathlib import Path
from urllib.error import URLError

REPO_ROOT = os.environ.get("PI_REPO_ROOT", str(Path(__file__).resolve().parent.parent))
RULES_CONFIG_PATH = os.path.join(REPO_ROOT, "config", "anti_pattern_rules.json")
PI_ROUTER_HOME = Path(os.environ.get("PI_ROUTER_HOME", Path.home() / ".pi-router" / "luna")).expanduser()
LOG_PATH = PI_ROUTER_HOME / "interventions.jsonl"
ROUTER_URL = os.environ.get("ROUTER_URL", "http://127.0.0.1:9876")

# Fallback local import if daemon is unreachable
sys.path.insert(0, os.path.join(REPO_ROOT, "engines", "hybrid_router"))
from hierarchical_routing.hierarchical_engine import LayaHierarchicalEngine


class DecisionGateInterceptor:
    def __init__(self, config_path: str = RULES_CONFIG_PATH):
        self.config = self._load_json(config_path)
        self.rules = self.config.get("rules", {})
        self.laya_fallback = LayaHierarchicalEngine()

    def _load_json(self, path: str) -> Dict[str, Any]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _query_laya_daemon(self, task_type: str, content: Dict[str, Any], latency_strict: int = 40) -> Dict[str, Any]:
        """Query the running Laya daemon or fallback to local in-memory engine."""
        payload = {
            "task_type": task_type,
            "content": content,
            "latency_strict": latency_strict
        }
        try:
            req = Request(
                f"{ROUTER_URL}/dispatch",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urlopen(req, timeout=1.5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return self.laya_fallback.predict(content)

    def log_intervention(self, intervention_type: str, description: str, latency_ms: float, metadata: Dict[str, Any]):
        """Append intervention event to learning/interventions.jsonl."""
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z") or "2026-09-22T23:15:00+09:00",
            "cycle": "hybrid-router-intervention",
            "intervention_type": intervention_type,
            "description": description,
            "agent_state": "intervened_by_decision_engine",
            "tokens_saved": None,
            "savings_status": "unmeasured",
            "latency_ms": latency_ms,
            "latency_kind": "measured_wall_clock",
            "metadata": metadata
        }
        log_path = Path(LOG_PATH)
        log_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    @staticmethod
    def format_telemetry_hud(title: str, latency_ms: float, anti_pattern: str, prescription: str) -> str:
        hud = [
            "┌──────────────────────────────────────────────────────────────────────────┐",
            f"│ ⚡ {title.center(68)} │",
            "├──────────────────────────────────────────────────────────────────────────┤",
            f"│ 💸 절감: 미측정 (토큰·비용; 비교 기준선 없음)".ljust(76) + "│",
            f"│ ⏱️ 판정 경로 시간 : {f'{latency_ms:.2f} ms (wall-clock)'.ljust(48)} │",
            f"│ 🛡️ 일치 규칙      : {anti_pattern[:48].ljust(48)} │",
            f"│ 🧭 제안된 다음 조치: {prescription[:48].ljust(48)} │",
            "└──────────────────────────────────────────────────────────────────────────┘"
        ]
        return "\n".join(hud)

    def intercept_pre_tool_use(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if agent is attempting to generate redundant skills or classifiers.
        Returns permission verdict: 'allow' or 'intercepted'.
        """
        skill_rule = self.rules.get("skill_generation_interception", {})
        if not skill_rule.get("enabled", True):
            return {"permission": "allow"}

        target_file = tool_input.get("TargetFile") or tool_input.get("path") or ""
        patterns = skill_rule.get("file_path_patterns", [])

        is_redundant_skill = any(re.search(pat, target_file, re.I) for pat in patterns)
        if is_redundant_skill:
            t0 = time.perf_counter()
            code_content = tool_input.get("CodeContent") or str(tool_input)
            
            # Query Laya decision engine
            decision_res = self._query_laya_daemon(
                task_type="issue_component_tagging",
                content={"intent": "avoid redundant skill", "source": code_content[:300]}
            )
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            decision_val = decision_res.get("decision", "syntax_compile")

            # Generate visual HUD card
            hud_card = self.format_telemetry_hud(
                title="규칙 기반 스킬 생성 차단",
                latency_ms=elapsed_ms,
                anti_pattern=f"불필요한 스킬 파일 생성 ({os.path.basename(target_file)})",
                prescription=f"Laya 판정 [{decision_val}] 즉시 적용"
            )

            # Log intervention
            desc = f"[ANTI-PATTERN BLOCKED] Redundant skill creation denied for '{os.path.basename(target_file)}'. Laya decision injected."
            self.log_intervention(
                intervention_type="directive",
                description=desc,
                latency_ms=elapsed_ms,
                metadata={"blocked_file": target_file, "decision": decision_val}
            )

            return {
                "permission": "intercepted",
                "blocked": True,
                "reason": "FORBIDDEN_SKILL_OVERHEAD: configured file-path rule matched.",
                "visual_hud": hud_card,
                "injected_prescription": {
                    "status": "OVERRIDDEN_BY_DECISION_ENGINE",
                    "decision": decision_val,
                    "action_required": "스킬 파일 생성을 취소하고, Laya 엔진의 판정 결과를 직접 사용하여 다음 작업을 진행하십시오.",
                    "latency_ms": elapsed_ms,
                    "latency_kind": "measured_wall_clock",
                    "tokens_saved": None,
                    "savings_status": "unmeasured",
                    "hud_card": hud_card
                }
            }

        return {"permission": "allow"}

    def intercept_post_tool_use(self, tool_name: str, command: str, exit_code: int, output_text: str) -> Optional[Dict[str, Any]]:
        """
        Classify failed-command text with local rules and return a suggested action.
        """
        error_rule = self.rules.get("error_loop_short_circuit", {})
        if not error_rule.get("enabled", True) or exit_code == 0:
            return None

        t0 = time.perf_counter()
        # Query Laya build_failure schema
        decision_res = self._query_laya_daemon(
            task_type="build_error_branching",
            content={"log": output_text[-500:], "command": command}
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        error_class = decision_res.get("decision", "syntax_compile")
        signatures = error_rule.get("error_signatures", {}).get(error_class, {})
        prescribed_action = signatures.get("prescribed_action", "Apply specific fix directly without architectural reasoning.")

        # Generate visual HUD card
        hud_card = self.format_telemetry_hud(
            title="실패 출력의 규칙 기반 분류",
            latency_ms=elapsed_ms,
            anti_pattern=f"명령어 '{command.split()[0]}' 에러 루프 진입 징후",
            prescription=f"[{error_class}] {prescribed_action}"
        )

        desc = f"[HEURISTIC CLASSIFICATION] Command '{command.split()[0]}' failed with exit code {exit_code}. Classified as '{error_class}' in {elapsed_ms}ms."
        self.log_intervention(
            intervention_type="directive",
            description=desc,
            latency_ms=elapsed_ms,
            metadata={"command": command, "error_class": error_class}
        )

        return {
            "intervened": True,
            "error_class": error_class,
            "requires_human": decision_res.get("tier2_domain", {}).get("requires_human_intervention", False),
            "prescribed_action": prescribed_action,
            "visual_hud": hud_card,
            "prompt_injection": f"\n[SYSTEM DECISION ENGINE OVERRIDE]\n{hud_card}\n* 지침: 장황한 분석이나 도구 작성을 중단하고 위 처방대로 직접 조치하십시오.\n",
            "tokens_saved": None,
            "savings_status": "unmeasured",
            "latency_ms": elapsed_ms,
            "latency_kind": "measured_wall_clock",
        }


def main():
    parser = argparse.ArgumentParser(description="Decision Gate Interceptor")
    parser.add_argument("--eval-file-write", help="Check file path for skill generation interception")
    parser.add_argument("--eval-error", help="Evaluate error log string for loop short-circuiting")
    parser.add_argument("--command", default="run-cmd", help="Command associated with error")
    parser.add_argument("--exit-code", type=int, default=1, help="Exit code of command")
    args = parser.parse_args()

    interceptor = DecisionGateInterceptor()

    if args.eval_file_write:
        res = interceptor.intercept_pre_tool_use("write_to_file", {"TargetFile": args.eval_file_write})
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.eval_error:
        res = interceptor.intercept_post_tool_use("run_command", args.command, args.exit_code, args.eval_error)
        print(json.dumps(res, indent=2, ensure_ascii=False))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
