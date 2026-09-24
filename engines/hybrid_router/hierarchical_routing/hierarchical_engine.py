#!/usr/bin/env python3
"""
hierarchical_engine.py
2-Tier keyword-heuristic router. It does not load or run Laya/ModernBERT/mmBERT.
The legacy class name is retained for current callers.
  - Tier-1 Core: Routes input to coarse domains (PR, Issue, Build, Security, Infra) [<= 6 choices]
  - Tier-2 Domain: Routes within the selected domain to exact action/assignee/component [<= 15 choices]
"""

import os
import json
import time
from typing import Dict, Any, List, Optional


class LayaHierarchicalEngine:
    def __init__(self, schemas_dir: Optional[str] = None):
        base_dir = schemas_dir or os.path.dirname(os.path.abspath(__file__))
        self.tier1_path = os.path.join(base_dir, "tier1_core", "core_schema.json")
        self.tier2_dir = os.path.join(base_dir, "tier2_domain")
        
        self.tier1_schema = self._load_json(self.tier1_path)
        self.tier2_schemas = {
            "pr_review": self._load_json(os.path.join(self.tier2_dir, "pr_review", "pr_schema.json")),
            "issue_triage": self._load_json(os.path.join(self.tier2_dir, "issue_triage", "issue_schema.json")),
            "build_failure": self._load_json(os.path.join(self.tier2_dir, "build_failure", "build_schema.json"))
        }

    def _load_json(self, path: str) -> Dict[str, Any]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _infer_tier1(self, text_content: str) -> Dict[str, Any]:
        content_lower = text_content.lower()
        scores = {
            "pr_review": 0.05,
            "issue_triage": 0.05,
            "build_failure": 0.05,
            "security_audit": 0.05,
            "infra_ops": 0.05,
            "general_triage": 0.05
        }
        
        if any(w in content_lower for w in ["pull request", "pr ", "merge", "diff", "commit", "review", "refactor"]):
            scores["pr_review"] += 0.95
        elif any(w in content_lower for w in ["log", "traceback", "syntax", "compile", "error", "exception", "modulenotfound", "enoent", "oom", "exit code", "exit status", "fatal:", "ts23"]):
            scores["build_failure"] += 0.95
        elif any(w in content_lower for w in ["bug", "issue", "widget", "defect", "broken", "refresh", "reconnect", "fails"]):
            scores["issue_triage"] += 0.95
        elif any(w in content_lower for w in ["token", "secret", "vulnerability", "auth", "permission denied", "ssh key"]):
            scores["security_audit"] += 0.95
        elif any(w in content_lower for w in ["tailscale", "tailnet", "node", "ping", "ram", "gpu", "host"]):
            scores["infra_ops"] += 0.95
        else:
            scores["general_triage"] += 0.70

        total = sum(scores.values())
        norm_scores = {k: round(v / total, 4) for k, v in scores.items()}
        winner = max(norm_scores, key=norm_scores.get)
        return {
            "domain": winner,
            "heuristic_score": norm_scores[winner],
            "heuristic_score_distribution": norm_scores,
        }

    def _infer_tier2(self, domain: str, text_content: str) -> Dict[str, Any]:
        """Classify domain-specific target within the selected Tier-1 domain."""
        content_lower = text_content.lower()
        
        if domain == "pr_review":
            assignee_scores = {
                "agent_codex": 0.1,
                "agent_claude_code": 0.1,
                "agent_antigravity": 0.1,
                "agent_mano": 0.05,
                "team_security": 0.05,
                "team_infra": 0.05,
                "user_direct": 0.05
            }
            if any(w in content_lower for w in ["runner", "harness", "codex", "daemon", "cli", "python"]):
                assignee_scores["agent_codex"] += 0.7
            elif any(w in content_lower for w in ["council", "protocol", "governance", "report", "brief", "audit"]):
                assignee_scores["agent_claude_code"] += 0.7
            elif any(w in content_lower for w in ["ui", "widget", "dashboard", "ide", "router", "telemetry"]):
                assignee_scores["agent_antigravity"] += 0.7
            elif any(w in content_lower for w in ["secret", "auth", "credential", "security"]):
                assignee_scores["team_security"] += 0.8
            elif any(w in content_lower for w in ["breaking", "license", "critical", "danger"]):
                assignee_scores["user_direct"] += 0.8
                
            winner = max(assignee_scores, key=assignee_scores.get)
            risk = 2 if "breaking" in content_lower else (1 if "refactor" in content_lower else 0)
            return {"assignee": winner, "risk_level": risk, "heuristic_score": assignee_scores[winner]}

        elif domain == "issue_triage":
            comp_scores = {
                "component_ui": 0.1,
                "component_api": 0.1,
                "component_daemon": 0.1,
                "component_tailnet": 0.1,
                "component_model_engine": 0.1,
                "component_storage": 0.1,
                "component_docs": 0.1
            }
            if any(w in content_lower for w in ["widget", "screen", "button", "css", "layout"]):
                comp_scores["component_ui"] += 0.8
            elif any(w in content_lower for w in ["api", "endpoint", "trpc", "http", "rest"]):
                comp_scores["component_api"] += 0.8
            elif any(w in content_lower for w in ["tailscale", "mesh", "ip", "packet", "latency"]):
                comp_scores["component_tailnet"] += 0.8
            elif any(w in content_lower for w in ["laya", "modernbert", "mps", "cuda", "model", "inference"]):
                comp_scores["component_model_engine"] += 0.8

            winner = max(comp_scores, key=comp_scores.get)
            is_reg = any(w in content_lower for w in ["regression", "broke", "previously", "yesterday", "worked before"])
            return {"component": winner, "is_regression": is_reg, "heuristic_score": comp_scores[winner]}

        elif domain == "build_failure":
            err_scores = {
                "syntax_compile": 0.1,
                "lint_formatting": 0.1,
                "dependency_missing": 0.1,
                "timeout_deadlock": 0.1,
                "out_of_memory": 0.1,
                "network_partition": 0.1,
                "permission_auth": 0.1
            }
            if any(w in content_lower for w in ["syntax", "compile", "ts2339", "typeerror"]):
                err_scores["syntax_compile"] += 0.8
            elif any(w in content_lower for w in ["biome", "ruff", "lint", "format"]):
                err_scores["lint_formatting"] += 0.8
            elif any(w in content_lower for w in ["modulenotfound", "enoent", "missing package"]):
                err_scores["dependency_missing"] += 0.8
            elif any(w in content_lower for w in ["oom", "out of memory", "heap", "vram"]):
                err_scores["out_of_memory"] += 0.8
            elif any(w in content_lower for w in ["permission denied", "publickey", "auth", "401"]):
                err_scores["permission_auth"] += 0.8

            winner = max(err_scores, key=err_scores.get)
            requires_human = winner in ["permission_auth", "out_of_memory"]
            return {
                "error_class": winner,
                "requires_human_intervention": requires_human,
                "heuristic_score": err_scores[winner],
            }

        else:
            return {"target": "general_inbox"}

    def predict(self, state: Dict[str, Any], questions: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute 2-tier keyword heuristics and measure their wall-clock duration.
        """
        t0 = time.perf_counter()
        
        # Flatten state into searchable text
        if isinstance(state, dict):
            text_repr = " ".join([f"{k}: {v}" for k, v in state.items()])
        else:
            text_repr = str(state)

        # Tier 1 Classification
        tier1_res = self._infer_tier1(text_repr)
        domain = tier1_res["domain"]
        
        # Tier 2 Classification within the resolved domain
        tier2_res = self._infer_tier2(domain, text_repr)
        
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "engine": "keyword-heuristic-hierarchical",
            "decision_method": "ordered_keyword_rules",
            "model_inference_performed": False,
            "tier1_core": tier1_res,
            "tier2_domain": tier2_res,
            "decision": tier2_res.get("assignee") or tier2_res.get("component") or tier2_res.get("error_class") or domain,
            "latency_ms": elapsed_ms,
            "latency_kind": "measured_wall_clock",
            "status": "success"
        }

    def fallback_resolve(self, state: Dict[str, Any], large_options: List[str]) -> Dict[str, Any]:
        """
        Fallback resolver that picks the option with the most keyword overlap.
        """
        t0 = time.perf_counter()
        text_repr = str(state)
        
        # Score each option based on token similarity / relevance
        scored = []
        for opt in large_options:
            score = sum(1 for token in opt.lower().replace("_", " ").split() if token in text_repr.lower())
            scored.append((opt, score))
            
        scored.sort(key=lambda x: x[1], reverse=True)
        winner = scored[0][0] if scored else "default_fallback"
        
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "engine": "heuristic-keyword-fallback",
            "decision_method": "keyword_overlap",
            "model_inference_performed": False,
            "decision": winner,
            "candidates_evaluated": len(large_options),
            "latency_ms": elapsed_ms,
            "latency_kind": "measured_wall_clock",
            "circuit_breaker_fallback": True
        }


if __name__ == "__main__":
    engine = LayaHierarchicalEngine()
    test_cases = [
        {"title": "fix(core): refactor task runner state machine in Pi harness", "files": ["src/runner.ts"]},
        {"title": "Sidebar widget fails to refresh when Tailscale reconnects", "component": "ui"},
        {"log": "FATAL: ModuleNotFoundError: No module named 'safetensors.torch'", "step": "build"}
    ]
    for tc in test_cases:
        res = engine.predict(tc)
        print(f"Input   : {tc.get('title') or tc.get('log')}")
        print(f"Decision: {res['decision']} | Tier-1: {res['tier1_core']['domain']} | Latency: {res['latency_ms']}ms\n")
