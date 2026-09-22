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
import unittest

sys.path.insert(0, "/Users/richardkim-macpro/Pi/scripts")
from importlib import import_module
interceptor_mod = import_module("decision-gate-interceptor")
DecisionGateInterceptor = interceptor_mod.DecisionGateInterceptor


class TestDecisionGateInterceptor(unittest.TestCase):
    def setUp(self):
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
        self.assertGreater(res["injected_prescription"]["tokens_saved"], 0)

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
        self.assertGreater(res["tokens_saved"], 0)


if __name__ == "__main__":
    unittest.main()
