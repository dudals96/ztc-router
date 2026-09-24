#!/usr/bin/env python3
"""
decision-gate-interceptor.py
CLI that classifies (1) one-off classifier/parser file writes and (2) failed commands.

Not wired as a hook: the Phase 1 shadow hook is scripts/hooks/router-client.sh.
Failed commands are classified by the L0 regexes in config/anti_pattern_rules.json
first, then by the local keyword heuristic. Latency is measured. Events go to
$PI_ROUTER_HOME/telemetry/router_events.jsonl (masked), never to learning/interventions.jsonl.
Output derived from logs is untrusted data: the advisory text is a suggestion, not a directive.
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "engines" / "hybrid_router"))
from hierarchical_routing.hierarchical_engine import HeuristicFallbackEngine
from ztc import l0, telemetry
from ztc.masking import mask_text
from ztc.paths import BIND_HOST, router_port

DAEMON_TIMEOUT_SEC = 0.5


class DecisionGateInterceptor:
    def __init__(self, config_path: Path = l0.RULES_PATH, use_daemon: bool = True):
        self.config = l0.load_rules(config_path)
        self.rules = self.config.get("rules", {})
        self.signatures = l0.compile_signatures(self.config)
        self.heuristic = HeuristicFallbackEngine()
        self.use_daemon = use_daemon

    def _classify_heuristic(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Ask the local daemon's /dispatch if reachable, else run the heuristic in-process."""
        if self.use_daemon:
            try:
                req = Request(
                    f"http://{BIND_HOST}:{router_port()}/dispatch",
                    data=json.dumps({"task_type": "build_error_branching", "content": content}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(req, timeout=DAEMON_TIMEOUT_SEC) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception:
                pass
        return self.heuristic.predict(content)

    @staticmethod
    def _record(kind: str, fields: Dict[str, Any]) -> None:
        try:
            telemetry.append("router_events", {"kind": kind, **fields})
        except OSError:
            pass  # telemetry is best-effort

    def intercept_pre_tool_use(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Flag writes to one-off classifier/parser scripts. Returns 'allow' or 'intercepted'."""
        rule = self.rules.get("skill_generation_interception", {})
        if not rule.get("enabled", True):
            return {"permission": "allow"}
        target_file = tool_input.get("TargetFile") or tool_input.get("path") or ""
        if not any(re.search(pat, target_file, re.I) for pat in rule.get("file_path_patterns", [])):
            return {"permission": "allow"}
        self._record("pre_flag", {"tool": tool_name, "file": mask_text(os.path.basename(target_file), limit=120)})
        return {
            "permission": "intercepted",
            "blocked": True,
            "reason": "ONE_OFF_CLASSIFIER: this file name matches a one-off classifier/parser pattern "
            "(config/anti_pattern_rules.json). Consider the existing heuristic first.",
        }

    def intercept_post_tool_use(self, tool_name: str, command: str, exit_code: int, output_text: str) -> Optional[Dict[str, Any]]:
        """Classify a failed command. L0 regex first, heuristic second. Returns None on success."""
        rule = self.rules.get("error_loop_short_circuit", {})
        if not rule.get("enabled", True) or exit_code == 0:
            return None
        t0 = time.perf_counter()
        tail = output_text[-500:]
        error_class = l0.classify_regex(tail, self.signatures)
        classified_by = "l0_regex"
        requires_human = error_class == "permission_auth"
        if error_class is None:
            res = self._classify_heuristic({"log": tail})
            error_class = res.get("decision", "unknown")
            requires_human = res.get("tier2_domain", {}).get("requires_human_intervention", False)
            classified_by = res.get("engine", "keyword-heuristic")
        latency_ms = round((time.perf_counter() - t0) * 1000, 4)

        spec = rule.get("error_signatures", {}).get(error_class, {})
        suggestion = spec.get("prescribed_action", "no rule-based suggestion for this class")
        program = command.split()[0] if command.strip() else ""
        self._record("post_classify", {"tool": tool_name, "program": mask_text(program, limit=60), "exit_code": exit_code,
                                       "error_class": error_class, "classified_by": classified_by, "latency_ms": latency_ms})
        return {
            "classified": True,
            "error_class": error_class,
            "classified_by": classified_by,
            "requires_human": requires_human,
            "suggested_action": suggestion,
            "advisory": f"[untrusted, log-derived] class={error_class} via {classified_by}; suggestion (not a directive): {suggestion}",
            "latency_ms": latency_ms,
        }


def main():
    parser = argparse.ArgumentParser(description="Decision Gate Interceptor (CLI, not a hook)")
    parser.add_argument("--eval-file-write", help="Check a file path against one-off classifier patterns")
    parser.add_argument("--eval-error", help="Classify an error log string")
    parser.add_argument("--command", default="run-cmd", help="Command associated with the error")
    parser.add_argument("--exit-code", type=int, default=1, help="Exit code of the command")
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
