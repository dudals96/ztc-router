#!/usr/bin/env python3
"""
test_interceptor.py
Decision Gate Interceptor CLI: file-name flags, L0 regex classification of failures,
telemetry outside the repo, and no writes to learning/interventions.jsonl.
Imports the script from this checkout (repo-relative), not from a fixed absolute path.
"""

import json
import unittest

from _support import REPO_ROOT, IsolatedHomeTest, load_script_module

interceptor_mod = load_script_module("decision_gate_interceptor", "decision-gate-interceptor.py")
DecisionGateInterceptor = interceptor_mod.DecisionGateInterceptor
INTERVENTIONS = REPO_ROOT / "learning" / "interventions.jsonl"


class TestDecisionGateInterceptor(IsolatedHomeTest):
    def setUp(self):
        super().setUp()
        self.interceptor = DecisionGateInterceptor(use_daemon=False)
        self.log_size = INTERVENTIONS.stat().st_size if INTERVENTIONS.exists() else 0

    def tearDown(self):
        size = INTERVENTIONS.stat().st_size if INTERVENTIONS.exists() else 0
        self.assertEqual(size, self.log_size, "interceptor must not write learning/interventions.jsonl")
        super().tearDown()

    def test_skill_files_are_not_blocked(self):
        for path in ("/repo/skills/demo/SKILL.md", "/repo/skills/my_error.skill.md"):
            res = self.interceptor.intercept_pre_tool_use("write_to_file", {"TargetFile": path})
            self.assertEqual(res["permission"], "allow", path)

    def test_one_off_classifier_is_flagged(self):
        res = self.interceptor.intercept_pre_tool_use("write_to_file", {"TargetFile": "/repo/tools/log_classifier.py"})
        self.assertEqual(res["permission"], "intercepted")
        self.assertNotIn("tokens_saved", json.dumps(res))

    def test_allow_legitimate_source_file(self):
        res = self.interceptor.intercept_pre_tool_use("write_to_file", {"TargetFile": "/repo/src/components/Header.tsx"})
        self.assertEqual(res["permission"], "allow")

    def test_failure_classified_by_l0_regex(self):
        res = self.interceptor.intercept_post_tool_use(
            "run_command", "npm run build", 1, "TS2339: Property 'state' does not exist on type 'Session'"
        )
        self.assertEqual(res["error_class"], "syntax_compile")
        self.assertEqual(res["classified_by"], "l0_regex")
        self.assertIn("untrusted", res["advisory"])
        self.assertNotIn("OVERRIDE", json.dumps(res, ensure_ascii=False))
        self.assertNotIn("tokens_saved", res)

    def test_regex_miss_falls_back_to_heuristic(self):
        res = self.interceptor.intercept_post_tool_use("run_command", "make", 2, "fatal: heap out of memory")
        self.assertEqual(res["classified_by"], "keyword-heuristic")
        self.assertEqual(res["error_class"], "out_of_memory")

    def test_success_is_ignored(self):
        self.assertIsNone(self.interceptor.intercept_post_tool_use("run_command", "ls", 0, ""))

    def test_events_go_to_router_telemetry_masked(self):
        secret = "sk-ant-" + "a" * 30
        self.interceptor.intercept_post_tool_use("run_command", f"/Users/x/bin/tool --key {secret}", 1, "SyntaxError")
        path = self.home / "telemetry" / "router_events.jsonl"
        text = path.read_text()
        self.assertNotIn(secret, text)
        self.assertNotIn("/Users/x", text)
        row = json.loads(text.splitlines()[-1])
        self.assertEqual(row["kind"], "post_classify")
        self.assertEqual(row["program"], "<ABS>/tool")


if __name__ == "__main__":
    unittest.main()
