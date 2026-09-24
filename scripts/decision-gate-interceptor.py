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
import re
import json
import time
import argparse
from typing import Dict, Any, Optional
from pathlib import Path
from router_data_safety import append_bounded_jsonl, classify_error, prepare_error_input, resolve_router_home

REPO_ROOT = Path(os.environ.get("PI_REPO_ROOT", Path(__file__).resolve().parent.parent)).resolve()
RULES_CONFIG_PATH = REPO_ROOT / "config" / "anti_pattern_rules.json"
PI_ROUTER_HOME = resolve_router_home(REPO_ROOT)
LOG_PATH = PI_ROUTER_HOME / "interventions.jsonl"


class DecisionGateInterceptor:
    def __init__(self, config_path: str = RULES_CONFIG_PATH):
        self.config = self._load_json(config_path)
        self.rules = self.config.get("rules", {})

    def _load_json(self, path: str) -> Dict[str, Any]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def log_intervention(self, intervention_type: str, error_class: str, fingerprint: str, latency_ms: float):
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "cycle": "hybrid-router-intervention",
            "intervention_type": intervention_type,
            "error_class": error_class,
            "input_fingerprint": fingerprint,
            "tokens_saved": None,
            "savings_status": "unmeasured",
            "latency_ms": latency_ms,
            "latency_kind": "measured_wall_clock"
        }
        return append_bounded_jsonl(Path(LOG_PATH), entry, REPO_ROOT)

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
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            decision_val = "configured_path_rule"
            safe_input = prepare_error_input({"file_path": target_file})

            # Generate visual HUD card
            hud_card = self.format_telemetry_hud(
                title="규칙 기반 스킬 생성 차단",
                latency_ms=elapsed_ms,
                anti_pattern=f"불필요한 스킬 파일 생성 ({os.path.basename(target_file)})",
                prescription="설정된 경로 규칙과 일치"
            )

            self.log_intervention(
                intervention_type="directive",
                error_class="configured_path_rule",
                fingerprint=str(safe_input["fingerprint"]),
                latency_ms=elapsed_ms
            )

            return {
                "permission": "intercepted",
                "blocked": True,
                "reason": "FORBIDDEN_SKILL_OVERHEAD: configured file-path rule matched.",
                "visual_hud": hud_card,
                "injected_prescription": {
                    "status": "OVERRIDDEN_BY_DECISION_ENGINE",
                    "decision": decision_val,
                    "action_required": "설정된 경로 규칙과 일치했습니다. 작업 목적과 범위를 직접 확인하십시오.",
                    "latency_ms": elapsed_ms,
                    "latency_kind": "measured_wall_clock",
                    "tokens_saved": None,
                    "savings_status": "unmeasured",
                    "hud_card": hud_card
                }
            }

        return {"permission": "allow"}

    def intercept_post_tool_use(self, tool_name: str, command: str, exit_code: int, output_text: str, context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Classify failed-command text with local rules and return a suggested action.
        """
        error_rule = self.rules.get("error_loop_short_circuit", {})
        if not error_rule.get("enabled", True) or exit_code == 0:
            return None

        t0 = time.perf_counter()
        error_input = dict(context or {})
        error_input["command"] = command
        error_input["stderr"] = output_text
        prepared = prepare_error_input(error_input)
        matched = classify_error(
            str(prepared["classification_text"]),
            error_rule.get("error_signatures", {}),
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        if matched is None:
            self.log_intervention("abstain", "abstain", str(prepared["fingerprint"]), elapsed_ms)
            return {
                "intervened": False,
                "error_class": "abstain",
                "decision_method": "configured_regex_l0",
                "model_inference_performed": False,
                "tokens_saved": None,
                "savings_status": "unmeasured",
                "latency_ms": elapsed_ms,
                "latency_kind": "measured_wall_clock",
            }

        error_class, prescribed_action = matched

        # Generate visual HUD card
        hud_card = self.format_telemetry_hud(
            title="실패 출력의 규칙 기반 분류",
            latency_ms=elapsed_ms,
                anti_pattern=f"실패한 명령 출력과 {error_class} 규칙 일치",
            prescription=f"[{error_class}] {prescribed_action}"
        )

        self.log_intervention(
            intervention_type="directive",
            error_class=error_class,
            fingerprint=str(prepared["fingerprint"]),
            latency_ms=elapsed_ms
        )

        return {
            "intervened": True,
            "error_class": error_class,
            "decision_method": "configured_regex_l0",
            "model_inference_performed": False,
            "requires_human": error_class in {"permission_auth", "out_of_memory"},
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
