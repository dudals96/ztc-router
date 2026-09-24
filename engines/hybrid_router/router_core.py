#!/usr/bin/env python3
"""
router_core.py
Routes a task to the local keyword heuristic or to the Jev client, following
config/routing_policy.json (rule_evaluation_order). The policy file is the only
source of routing rules. Latencies are measured; nothing is added or capped.
"""

import json
import os
import sys
import time
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gateway.jev_client import JevGatewayClient
from hierarchical_routing.hierarchical_engine import HeuristicFallbackEngine
from ztc.paths import CONFIG_DIR

DEFAULT_POLICY_PATH = CONFIG_DIR / "routing_policy.json"
LOCAL_ROUTE, JEV_ROUTE = "local_route", "jev_route"


def _task_facts(task: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "categories_count": len(task.get("categories", [])),
        "tokens_count": task.get("tokens_count", len(str(task.get("content", ""))) // 4),
        "latency_strict": task.get("latency_strict", 100),
        "task_type": task.get("task_type", "general"),
    }


def _predicate_holds(name: str, arg: Any, facts: Dict[str, Any]) -> bool:
    if name == "categories_count_gt":
        return facts["categories_count"] > arg
    if name == "latency_strict_lte":
        return facts["latency_strict"] <= arg
    if name == "tokens_count_lte":
        return facts["tokens_count"] <= arg
    if name == "task_type_in":
        return facts["task_type"] in arg
    if name == "default":
        return bool(arg)
    raise ValueError(f"unknown policy predicate: {name}")


class HybridDecisionRouter:
    def __init__(self, policy_path: Optional[str] = None, jev: Optional[JevGatewayClient] = None):
        self.policy_path = str(policy_path or DEFAULT_POLICY_PATH)
        self.policy = self._load_policy(self.policy_path)
        self.local = HeuristicFallbackEngine()
        self.jev = jev or JevGatewayClient()

    @staticmethod
    def _load_policy(path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            policy = json.load(f)
        if not policy.get("rule_evaluation_order"):
            raise ValueError(f"routing policy has no rule_evaluation_order: {path}")
        return policy

    def evaluate_route(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """First rule (by priority) with any matching predicate wins. Returns route + rule."""
        facts = _task_facts(task)
        for rule in sorted(self.policy["rule_evaluation_order"], key=lambda r: r["priority"]):
            if any(_predicate_holds(k, v, facts) for k, v in rule["when"].items()):
                return {"route": rule["destination"], "priority": rule["priority"], "reason": rule.get("reason", "")}
        return {"route": LOCAL_ROUTE, "priority": None, "reason": "no rule matched"}

    def dispatch(self, task: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.perf_counter()
        verdict = self.evaluate_route(task)
        content = task.get("content", {})
        if verdict["route"] == JEV_ROUTE:
            result = self.jev.route_decision(content, task.get("categories", []), instructions=task.get("instructions", "Route task"))
        else:
            result = self.local.predict(content)
        result["evaluated_route"] = verdict["route"]
        result["route_rule_priority"] = verdict["priority"]
        result["route_reason"] = verdict["reason"]
        result["total_pipeline_latency_ms"] = round((time.perf_counter() - t0) * 1000, 4)
        return result


if __name__ == "__main__":
    router = HybridDecisionRouter()
    demo = {"task_type": "build_error_branching", "content": {"log": "TS2339: Property 'choice' does not exist"}}
    print(json.dumps(router.dispatch(demo), ensure_ascii=False, indent=2))
