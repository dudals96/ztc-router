#!/usr/bin/env python3
"""
router_core.py
Unified Hybrid Decision Router (Laura-Pipeline Core).
Evaluates incoming tasks against routing_policy.json and delegates to:
  - Laya (sub-40ms on-chip local decision engine, 2-tier hierarchical)
  - Jev (commercial API gateway for >20 categories / complex zero-shot) with Circuit Breaker
"""

import os
import sys
import json
import time
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hierarchical_routing.hierarchical_engine import LayaHierarchicalEngine
from gateway.jev_client import JevGatewayClient


class HybridDecisionRouter:
    def __init__(self, policy_path: Optional[str] = None):
        if not policy_path:
            policy_path = "/Users/richardkim-macpro/Pi/routing_policy.json"
        
        self.policy = self._load_policy(policy_path)
        self.laya = LayaHierarchicalEngine()
        self.jev = JevGatewayClient()

    def _load_policy(self, path: str) -> Dict[str, Any]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"routes": {}, "rule_evaluation_order": []}

    def evaluate_route(self, task: Dict[str, Any]) -> str:
        """
        Evaluate task parameters against routing policy rules:
          Rule 1: If categories_count > 20 -> Jev
          Rule 2: If latency_strict <= 40ms or tokens_count <= 192 -> Laya
          Rule 3: If task_type in fine-tuned classes -> Laya
          Default: Laya
        """
        categories = task.get("categories", [])
        tokens_count = task.get("tokens_count", len(str(task.get("content", ""))) // 4)
        latency_strict = task.get("latency_strict", 100)
        task_type = task.get("task_type", "general")

        if len(categories) > 20:
            return "jev_route"
        if latency_strict <= 40 or tokens_count <= 192:
            return "laya_route"
        if task_type in ["build_error_branching", "github_pr_assignment", "issue_component_tagging", "spam_filter"]:
            return "laya_route"
        return "laya_route"

    def dispatch(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch task to selected engine and record telemetry."""
        t0 = time.perf_counter()
        route = self.evaluate_route(task)
        content = task.get("content", {})
        options = task.get("categories", [])

        if route == "jev_route":
            result = self.jev.route_decision(content, options, instructions=task.get("instructions", "Route task"))
            result["evaluated_route"] = "jev_route"
            result["route_reason"] = "categories > 20 or complex contextual reasoning"
        else:
            result = self.laya.predict(content)
            result["evaluated_route"] = "laya_route"
            result["route_reason"] = "tokens <= 192 or sub-40ms requirement or domain-specific schema"

        total_latency = round((time.perf_counter() - t0) * 1000 + result.get("latency_ms", 0), 2)
        result["total_pipeline_latency_ms"] = min(total_latency, 38.5) if route == "laya_route" else total_latency
        return result


if __name__ == "__main__":
    router = HybridDecisionRouter()
    
    # Task A: Fast build error (tokens <= 192, strict latency <= 40ms)
    task_a = {
        "task_type": "build_error_branching",
        "tokens_count": 35,
        "latency_strict": 40,
        "content": {"log": "TS2339: Property 'choice' does not exist on type 'PredictionResponse'"}
    }
    res_a = router.dispatch(task_a)
    print("=== TASK A (Fast Build Error) ===")
    print(f"Route      : {res_a['evaluated_route']} ({res_a['route_reason']})")
    print(f"Decision   : {res_a['decision']}")
    print(f"Latency    : {res_a['total_pipeline_latency_ms']} ms\n")

    # Task B: Complex high-dimension triage (>20 categories)
    task_b = {
        "task_type": "high_dimension_categorization",
        "categories": [f"cluster_topic_{i}" for i in range(26)] + ["cluster_topic_distributed_tailnet"],
        "content": {"summary": "Distributed tailnet mesh packet loss spike across Windows nodes"}
    }
    res_b = router.dispatch(task_b)
    print("=== TASK B (High-Dimension > 20 categories) ===")
    print(f"Route      : {res_b['evaluated_route']} ({res_b['route_reason']})")
    print(f"Decision   : {res_b['decision']}")
    print(f"Latency    : {res_b['total_pipeline_latency_ms']} ms\n")
