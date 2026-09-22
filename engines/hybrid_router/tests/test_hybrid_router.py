#!/usr/bin/env python3
"""
test_hybrid_router.py
Comprehensive test suite for the Hybrid Decision Engine (LAURA-PIPELINE).
Tests:
  1. 2-Tier Hierarchical Laya Engine accuracy across 3 custom use cases
  2. Latency verification (<40ms for Laya)
  3. Jev API Gateway routing (>20 categories)
  4. Circuit Breaker Deadman's Switch fallback
  5. Routing policy resolution
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hierarchical_routing.hierarchical_engine import LayaHierarchicalEngine
from gateway.jev_client import JevGatewayClient, CircuitBreakerState
from router_core import HybridDecisionRouter


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
        self.assertLessEqual(res["latency_ms"], 40.0)

    def test_use_case_2_issue_component_tagging(self):
        state = {"title": "Sidebar widget fails to refresh when Tailscale reconnects"}
        res = self.laya.predict(state)
        self.assertEqual(res["tier1_core"]["domain"], "issue_triage")
        self.assertEqual(res["decision"], "component_ui")
        self.assertLessEqual(res["latency_ms"], 40.0)

    def test_use_case_3_error_log_branching(self):
        state = {"log": "FATAL: ModuleNotFoundError: No module named 'safetensors.torch'"}
        res = self.laya.predict(state)
        self.assertEqual(res["tier1_core"]["domain"], "build_failure")
        self.assertEqual(res["decision"], "dependency_missing")
        self.assertLessEqual(res["latency_ms"], 40.0)

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
        self.assertEqual(res.get("engine"), "laya-fallback-cluster")


if __name__ == "__main__":
    unittest.main()
