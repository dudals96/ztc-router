#!/usr/bin/env python3
"""
test_hybrid_router.py
Behavior tests for the heuristic router and local simulation.
Tests:
  1. Hierarchical keyword-rule behavior across 3 cases
  2. Measured wall-clock reporting without a latency guarantee
  3. Local keyword-match simulation routing
  4. Circuit breaker fallback behavior
  5. Routing policy resolution
"""

import json
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hierarchical_routing.hierarchical_engine import LayaHierarchicalEngine
from gateway.jev_client import JevGatewayClient, CircuitBreakerState
from router_core import HybridDecisionRouter

DAEMON_SPEC = importlib.util.spec_from_file_location(
    "hybrid_router_daemon",
    Path(__file__).resolve().parents[3] / "scripts" / "hybrid-router-daemon.py",
)
if DAEMON_SPEC is None or DAEMON_SPEC.loader is None:
    raise RuntimeError("Could not load daemon module for telemetry tests")
DAEMON_MODULE = importlib.util.module_from_spec(DAEMON_SPEC)
DAEMON_SPEC.loader.exec_module(DAEMON_MODULE)


class TestHybridRouter(unittest.TestCase):
    def setUp(self):
        self.laya = LayaHierarchicalEngine()
        self.jev = JevGatewayClient()
        self.router = HybridDecisionRouter()

    def test_use_case_1_pr_assignment(self):
        state = {"title": "refactor(harness): update task runner state machine in Pi harness"}
        res = self.laya.predict(state)
        self.assertEqual(res["tier1_core"]["domain"], "pr_review")
        self.assertIn("agent_", res["decision"])
        self.assertEqual(res["latency_kind"], "measured_wall_clock")
        self.assertEqual(res["decision_method"], "ordered_keyword_rules")
        self.assertFalse(res["model_inference_performed"])

    def test_use_case_2_issue_component_tagging(self):
        state = {"title": "Sidebar widget fails to refresh when Tailscale reconnects"}
        res = self.laya.predict(state)
        self.assertEqual(res["tier1_core"]["domain"], "issue_triage")
        self.assertEqual(res["decision"], "component_ui")
        self.assertGreaterEqual(res["latency_ms"], 0.0)

    def test_use_case_3_error_log_branching(self):
        state = {"log": "FATAL: ModuleNotFoundError: No module named 'safetensors.torch'"}
        res = self.laya.predict(state)
        self.assertEqual(res["tier1_core"]["domain"], "build_failure")
        self.assertEqual(res["decision"], "dependency_missing")
        self.assertNotIn("confidence", res["tier1_core"])
        self.assertIn("heuristic_score", res["tier1_core"])

    def test_latency_is_reported_as_measured_without_synthetic_padding(self):
        with patch(
            "hierarchical_routing.hierarchical_engine.time.perf_counter",
            side_effect=[10.0, 10.055],
        ):
            result = self.laya.predict({"title": "ordinary routing task"})

        self.assertEqual(result["latency_ms"], 55.0)
        self.assertEqual(result["latency_kind"], "measured_wall_clock")

    def test_router_loads_thresholds_from_the_selected_policy(self):
        policy = {
            "routes": {
                "jev_route": {"conditions": {"min_categories": 2}},
                "laya_route": {
                    "conditions": {
                        "max_tokens": 0,
                        "max_latency_ms": 0,
                        "target_task_classes": [],
                    }
                },
            }
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_path = Path(temp_dir) / "policy.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            router = HybridDecisionRouter(policy_path=str(policy_path))

            route = router.evaluate_route(
                {
                    "categories": ["one", "two"],
                    "tokens_count": 500,
                    "latency_strict": 100,
                    "task_type": "general",
                }
            )

        self.assertEqual(route, "jev_route")

    def test_router_default_policy_is_worktree_config(self):
        expected = Path(__file__).resolve().parents[3] / "config" / "routing_policy.json"
        self.assertEqual(Path(self.router.policy_path), expected)

    def test_total_pipeline_latency_is_not_double_counted_or_capped(self):
        with (
            patch.object(
                self.router.laya,
                "predict",
                return_value={"decision": "build_failure", "latency_ms": 80.0},
            ),
            patch("router_core.time.perf_counter", side_effect=[10.0, 10.1]),
        ):
            result = self.router.dispatch({"tokens_count": 1, "content": {"log": "error"}})

        self.assertEqual(result["latency_ms"], 80.0)
        self.assertEqual(result["total_pipeline_latency_ms"], 100.0)

    def test_daemon_telemetry_only_averages_measured_interventions(self):
        events = [
            {"cycle": "hybrid-router-intervention", "latency_kind": "measured_wall_clock", "latency_ms": 12.5},
            {"cycle": "hybrid-router-intervention", "latency_kind": "unmeasured", "latency_ms": 900},
            {"cycle": "hybrid-router-milestone", "latency_kind": "measured_wall_clock", "latency_ms": 50},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "interventions.jsonl"
            log_path.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")

            telemetry = DAEMON_MODULE.load_telemetry_data(log_path)

        self.assertEqual(telemetry["interventions_count"], 2)
        self.assertEqual(telemetry["avg_latency_ms"], 12.5)
        self.assertEqual(telemetry["latency_samples"], 1)
        self.assertEqual(telemetry["savings_status"], "unmeasured")
        self.assertNotIn("total_tokens_saved", telemetry)

    def test_high_dimension_jev_routing(self):
        categories = [f"domain_target_{i}" for i in range(25)] + ["domain_target_tailnet_mesh"]
        task = {
            "task_type": "high_dimension_categorization",
            "categories": categories,
            "content": {"text": "Tailnet mesh routing packet drop across distributed nodes"}
        }
        res = self.router.dispatch(task)
        self.assertEqual(res["evaluated_route"], "jev_route")
        self.assertEqual(res["decision"], "domain_target_tailnet_mesh")

    def test_circuit_breaker_deadman_switch(self):
        client = JevGatewayClient()
        test_state = {"context": "critical database failure"}
        opts = ["db_failover", "db_read_replica", "db_restart"]
        
        # Trip the circuit breaker by simulating 3 failures
        for _ in range(3):
            client.route_decision(test_state, opts, force_fail=True)
            
        self.assertEqual(client.state, CircuitBreakerState.OPEN)
        
        # Next call must divert to Laya fallback
        res = client.route_decision(test_state, opts)
        self.assertTrue(res.get("deadman_switch_triggered"))
        self.assertEqual(res.get("engine"), "heuristic-keyword-fallback")


if __name__ == "__main__":
    unittest.main()
