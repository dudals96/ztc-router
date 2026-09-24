#!/usr/bin/env python3
"""
router_core.py
Unified Hybrid Decision Router. Routes with the checked-in policy and the
local keyword-heuristic or simulated keyword-matching path.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hierarchical_routing.hierarchical_engine import LayaHierarchicalEngine
from gateway.jev_client import JevGatewayClient

DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[2] / "config" / "routing_policy.json"


class HybridDecisionRouter:
    def __init__(self, policy_path: Optional[str] = None):
        self.policy_path = str(policy_path or DEFAULT_POLICY_PATH)
        self.policy = self._load_policy(self.policy_path)
        self.laya = LayaHierarchicalEngine()
        self.jev = JevGatewayClient()

    def _load_policy(self, path: str) -> Dict[str, Any]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"routes": {}, "rule_evaluation_order": []}

    def evaluate_route(self, task: Dict[str, Any]) -> str:
        """
        Evaluate the structured thresholds and task types in the loaded policy.
        """
        categories = task.get("categories", [])
        tokens_count = task.get("tokens_count", len(str(task.get("content", ""))) // 4)
        latency_strict = task.get("latency_strict", 100)
        task_type = task.get("task_type", "general")
        routes = self.policy.get("routes", {})
        jev_conditions = routes.get("jev_route", {}).get("conditions", {})
        laya_conditions = routes.get("laya_route", {}).get("conditions", {})
        categories_count = len(categories) if isinstance(categories, list) else 0

        if (
            categories_count >= jev_conditions.get("min_categories", 21)
            or task_type in jev_conditions.get("task_types", [])
        ):
            return "jev_route"
        if (
            latency_strict <= laya_conditions.get("max_latency_ms", 40)
            or tokens_count <= laya_conditions.get("max_tokens", 192)
            or task_type in laya_conditions.get("target_task_classes", [])
        ):
            return "laya_route"
        default_rule = next(
            (rule for rule in self.policy.get("rule_evaluation_order", []) if rule.get("condition") == "default"),
            {"destination": "laya_route"},
        )
        return default_rule.get("destination", "laya_route")

    def dispatch(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch task to selected engine and record telemetry."""
        t0 = time.perf_counter()
        route = self.evaluate_route(task)
        content = task.get("content", {})
        options = task.get("categories", [])

        if route == "jev_route":
            result = self.jev.route_decision(content, options, instructions=task.get("instructions", "Route task"))
            result["evaluated_route"] = "jev_route"
            result["route_reason"] = "configured routing policy selected jev_route"
        else:
            result = self.laya.predict(content)
            result["evaluated_route"] = "laya_route"
            result["route_reason"] = "configured routing policy selected laya_route"

        total_latency = round((time.perf_counter() - t0) * 1000, 2)
        result["total_pipeline_latency_ms"] = total_latency
        result["latency_kind"] = "measured_wall_clock"
        return result


if __name__ == "__main__":
    router = HybridDecisionRouter()
    
    # Task A: Build error selected by configured route conditions
    task_a = {
        "task_type": "build_error_branching",
        "tokens_count": 35,
        "latency_strict": 40,
        "content": {"log": "TS2339: Property 'choice' does not exist on type 'PredictionResponse'"}
    }
    res_a = router.dispatch(task_a)
    print("=== TASK A (Configured Build Error Route) ===")
    print(f"Route      : {res_a['evaluated_route']} ({res_a['route_reason']})")
    print(f"Decision   : {res_a['decision']}")
    print(f"Latency    : {res_a['total_pipeline_latency_ms']} ms\n")

    # Task B: High-dimension task selected by configured category threshold
    task_b = {
        "task_type": "high_dimension_categorization",
        "categories": [f"cluster_topic_{i}" for i in range(26)] + ["cluster_topic_distributed_tailnet"],
        "content": {"summary": "Distributed tailnet mesh packet loss spike across Windows nodes"}
    }
    res_b = router.dispatch(task_b)
    print("=== TASK B (Configured High-Dimension Route) ===")
    print(f"Route      : {res_b['evaluated_route']} ({res_b['route_reason']})")
    print(f"Decision   : {res_b['decision']}")
    print(f"Latency    : {res_b['total_pipeline_latency_ms']} ms\n")
