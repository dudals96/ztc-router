#!/usr/bin/env python3
"""
test_hybrid_router.py
Keyword heuristic, policy-driven routing, and the Jev client against a local mock server.
Latency is recorded and format-checked, never asserted against a ceiling.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from _support import REPO_ROOT, FakeServer, IsolatedHomeTest
from gateway.jev_client import CircuitBreakerState, JevGatewayClient
from hierarchical_routing.hierarchical_engine import HeuristicFallbackEngine
from router_core import DEFAULT_POLICY_PATH, HybridDecisionRouter


class TestHeuristicEngine(unittest.TestCase):
    def setUp(self):
        self.engine = HeuristicFallbackEngine()

    def assert_measured_latency(self, res):
        self.assertIsInstance(res["latency_ms"], float)
        self.assertGreaterEqual(res["latency_ms"], 0.0)

    def test_use_case_1_pr_assignment(self):
        res = self.engine.predict({"title": "refactor(harness): update task runner state machine in Pi harness"})
        self.assertEqual(res["tier1_core"]["domain"], "pr_review")
        self.assertIn("agent_", res["decision"])
        self.assert_measured_latency(res)

    def test_use_case_2_issue_component_tagging(self):
        res = self.engine.predict({"title": "Sidebar widget fails to refresh when Tailscale reconnects"})
        self.assertEqual(res["tier1_core"]["domain"], "issue_triage")
        self.assertEqual(res["decision"], "component_ui")
        self.assert_measured_latency(res)

    def test_use_case_3_error_log_branching(self):
        res = self.engine.predict({"log": "FATAL: ModuleNotFoundError: No module named 'safetensors.torch'"})
        self.assertEqual(res["tier1_core"]["domain"], "build_failure")
        self.assertEqual(res["decision"], "dependency_missing")
        self.assert_measured_latency(res)

    def test_engine_is_labelled_heuristic_not_model(self):
        res = self.engine.predict({"log": "SyntaxError"})
        self.assertEqual(res["engine"], "keyword-heuristic")
        self.assertNotIn("confidence", res["tier1_core"])
        self.assertNotIn("confidence", res["tier2_domain"])


class TestRoutingPolicy(IsolatedHomeTest):
    def test_router_reads_config_policy_and_root_copy_is_gone(self):
        self.assertEqual(Path(DEFAULT_POLICY_PATH), REPO_ROOT / "config" / "routing_policy.json")
        self.assertFalse((REPO_ROOT / "routing_policy.json").exists())
        router = HybridDecisionRouter()
        self.assertEqual(router.policy_path, str(REPO_ROOT / "config" / "routing_policy.json"))

    def test_policy_file_change_changes_verdict(self):
        task = {"task_type": "build_error_branching", "categories": ["a", "b", "c"], "content": {"log": "x"}}
        self.assertEqual(HybridDecisionRouter().evaluate_route(task)["route"], "local_route")
        policy = json.loads((REPO_ROOT / "config" / "routing_policy.json").read_text())
        policy["rule_evaluation_order"][0]["when"] = {"categories_count_gt": 2}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "routing_policy.json")
            Path(path).write_text(json.dumps(policy))
            verdict = HybridDecisionRouter(policy_path=path).evaluate_route(task)
        self.assertEqual(verdict["route"], "jev_route")
        self.assertEqual(verdict["priority"], 1)

    def test_pipeline_latency_is_measured_not_capped(self):
        res = HybridDecisionRouter().dispatch({"task_type": "build_error_branching", "content": {"log": "TS2339"}})
        self.assertEqual(res["evaluated_route"], "local_route")
        self.assertIsInstance(res["total_pipeline_latency_ms"], float)


class TestJevClient(IsolatedHomeTest):
    OPTIONS = ["db_failover", "db_read_replica", "db_restart"]

    def test_unconfigured_never_calls_out_and_falls_back(self):
        client = JevGatewayClient(endpoint="")
        res = client.route_decision({"context": "db restart needed"}, self.OPTIONS)
        self.assertEqual(res["upstream_error"], "jev_unconfigured")
        self.assertTrue(res["engine"].startswith("keyword-heuristic"))
        self.assertEqual(client.state, CircuitBreakerState.CLOSED)

    def test_high_dimension_route_uses_http_answer(self):
        cats = [f"domain_target_{i}" for i in range(25)] + ["domain_target_tailnet_mesh"]
        with FakeServer(reply={"decision": "domain_target_7", "confidence": 0.61}) as srv:
            jev = JevGatewayClient(endpoint=f"http://127.0.0.1:{srv.port}/v1/decision")
            res = HybridDecisionRouter(jev=jev).dispatch(
                {"task_type": "high_dimension_categorization", "categories": cats, "content": {"text": "mesh"}}
            )
            sent = json.loads(srv.bodies[0])
        self.assertEqual(res["evaluated_route"], "jev_route")
        self.assertEqual(res["engine"], "jev-http")
        self.assertEqual(res["decision"], "domain_target_7")  # the server's answer, not a local score
        self.assertEqual(res["confidence"], 0.61)
        self.assertEqual(sent["options"], cats)

    def test_invalid_answer_is_a_failure(self):
        with FakeServer(reply={"decision": "not_an_option"}) as srv:
            client = JevGatewayClient(endpoint=f"http://127.0.0.1:{srv.port}/")
            res = client.route_decision({"context": "x"}, self.OPTIONS)
        self.assertIn("ValueError", res["upstream_error"])
        self.assertEqual(client.failure_count, 1)

    def test_circuit_breaker_opens_after_real_failures(self):
        with FakeServer(status=500) as srv:
            client = JevGatewayClient(endpoint=f"http://127.0.0.1:{srv.port}/")
            for _ in range(3):
                client.route_decision({"context": "critical database failure"}, self.OPTIONS)
            self.assertEqual(client.state, CircuitBreakerState.OPEN)
            calls = len(srv.bodies)
            res = client.route_decision({"context": "critical database failure"}, self.OPTIONS)
            self.assertEqual(len(srv.bodies), calls)  # open breaker: no HTTP call
        self.assertTrue(res["deadman_switch_triggered"])
        self.assertEqual(res["upstream_error"], "circuit_open")


if __name__ == "__main__":
    unittest.main()
