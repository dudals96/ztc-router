#!/usr/bin/env python3
"""
test_interceptor.py
Unit tests for Decision Gate Interceptor.
Verifies:
  1. Skill generation interception & blocking
  2. Error loop diagnosis & prompt injection
  3. Safe passthrough of normal files
  4. Logging to interventions.jsonl
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from importlib import import_module
interceptor_mod = import_module("decision-gate-interceptor")
DecisionGateInterceptor = interceptor_mod.DecisionGateInterceptor


class TestDecisionGateInterceptor(unittest.TestCase):
    def setUp(self):
        self.log_dir = tempfile.TemporaryDirectory()
        log_path = str(Path(self.log_dir.name) / "interventions.jsonl")
        self.log_path_patch = patch.object(interceptor_mod, "LOG_PATH", log_path)
        self.log_path_patch.start()
        self.addCleanup(self.log_path_patch.stop)
        self.addCleanup(self.log_dir.cleanup)
        self.interceptor = DecisionGateInterceptor()

    def test_block_redundant_skill_creation(self):
        tool_input = {
            "TargetFile": "/Users/richardkim-macpro/Pi/skills/my_error_classifier.skill.md",
            "CodeContent": "def classify_error(): pass"
        }
        res = self.interceptor.intercept_pre_tool_use("write_to_file", tool_input)
        self.assertEqual(res["permission"], "intercepted")
        self.assertTrue(res["blocked"])
        self.assertIn("FORBIDDEN_SKILL_OVERHEAD", res["reason"])
        self.assertIsNone(res["injected_prescription"]["tokens_saved"])
        self.assertEqual(res["injected_prescription"]["savings_status"], "unmeasured")
        self.assertIn("미측정", res["visual_hud"])

    def test_allow_legitimate_source_file(self):
        tool_input = {
            "TargetFile": "/Users/richardkim-macpro/Pi/src/components/Header.tsx",
            "CodeContent": "export const Header = () => null;"
        }
        res = self.interceptor.intercept_pre_tool_use("write_to_file", tool_input)
        self.assertEqual(res["permission"], "allow")

    def test_short_circuit_error_loop(self):
        cmd = "npm run build"
        output = "TS2339: Property 'state' does not exist on type 'Session'"
        res = self.interceptor.intercept_post_tool_use("run_command", cmd, 1, output)
        self.assertIsNotNone(res)
        self.assertTrue(res["intervened"])
        self.assertEqual(res["error_class"], "syntax_compile")
        self.assertIn("[SYSTEM DECISION ENGINE OVERRIDE]", res["prompt_injection"])
        self.assertIsNone(res["tokens_saved"])
        self.assertEqual(res["savings_status"], "unmeasured")

    def test_telemetry_hud_does_not_claim_savings(self):
        hud = DecisionGateInterceptor.format_telemetry_hud(
            title="heuristic result",
            latency_ms=12.5,
            anti_pattern="test pattern",
            prescription="suggested next action",
        )

        self.assertIn("절감: 미측정", hud)
        self.assertNotIn("Tokens", hud)


if __name__ == "__main__":
    unittest.main()
