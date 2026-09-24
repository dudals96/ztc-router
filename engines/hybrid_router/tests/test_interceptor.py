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
import json
import stat
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
data_safety = import_module("router_data_safety")


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
        cmd = "npm run build --token=sample-secret"
        output = "TS2339: Property 'state' does not exist on type 'Session' in /Users/alice/private-project/src/app.ts:42"
        res = self.interceptor.intercept_post_tool_use(
            "run_command",
            cmd,
            1,
            output,
            {"cwd": "/Users/alice/private-project", "result_path": "/Users/alice/private-project/dist/out.js"},
        )
        self.assertIsNotNone(res)
        self.assertTrue(res["intervened"])
        self.assertEqual(res["error_class"], "syntax_compile")
        self.assertEqual(res["decision_method"], "configured_regex_l0")
        self.assertFalse(res["model_inference_performed"])
        self.assertIn("[SYSTEM DECISION ENGINE OVERRIDE]", res["prompt_injection"])
        self.assertIsNone(res["tokens_saved"])
        self.assertEqual(res["savings_status"], "unmeasured")
        log_text = (Path(self.log_dir.name) / "interventions.jsonl").read_text(encoding="utf-8")
        for sensitive_value in ("sample-secret", "alice", "private-project", "app.ts", "out.js"):
            self.assertNotIn(sensitive_value, log_text)
        self.assertIn("input_fingerprint", log_text)
        self.assertNotIn("description", log_text)

    def test_unmatched_failure_abstains_without_prescription(self):
        res = self.interceptor.intercept_post_tool_use(
            "run_command",
            "custom-runner",
            1,
            "Unrecognized domain failure: renderer handshake rejected",
        )

        self.assertEqual(res["error_class"], "abstain")
        self.assertFalse(res["intervened"])
        self.assertNotIn("prompt_injection", res)

    def test_error_fields_are_masked_and_distinct_locations_stay_distinct(self):
        first = data_safety.prepare_error_input({
            "command": "build --token=sample-secret",
            "cwd": "/Users/alice/private-project",
            "file_path": "/Users/alice/private-project/src/a.py:12",
            "stderr": "SyntaxError alice@example.com 0123456789abcdef0123456789abcdef",
            "result_path": "/Users/alice/private-project/out/a.py",
        })
        different_path = data_safety.prepare_error_input({
            "command": "build --token=sample-secret",
            "cwd": "/Users/alice/private-project",
            "file_path": "/Users/alice/private-project/src/b.py:12",
            "stderr": "SyntaxError alice@example.com 0123456789abcdef0123456789abcdef",
            "result_path": "/Users/alice/private-project/out/a.py",
        })
        different_line = data_safety.prepare_error_input({
            "command": "build --token=sample-secret",
            "cwd": "/Users/alice/private-project",
            "file_path": "/Users/alice/private-project/src/a.py:13",
            "stderr": "SyntaxError alice@example.com 0123456789abcdef0123456789abcdef",
            "result_path": "/Users/alice/private-project/out/a.py",
        })
        different_hash = data_safety.prepare_error_input({
            "command": "build --token=sample-secret",
            "cwd": "/Users/alice/private-project",
            "file_path": "/Users/alice/private-project/src/a.py:12",
            "stderr": "SyntaxError alice@example.com fedcba9876543210fedcba9876543210",
            "result_path": "/Users/alice/private-project/out/a.py",
        })
        masked = str(first["masked_fields"])

        for sensitive_value in ("sample-secret", "alice", "private-project", "a.py", "alice@example.com", "0123456789abcdef"):
            self.assertNotIn(sensitive_value, masked)
        for changed_input in (different_path, different_line, different_hash):
            self.assertNotEqual(first["fingerprint"], changed_input["fingerprint"])

    def test_external_log_is_private_and_repo_log_is_rejected(self):
        log_path = Path(self.log_dir.name) / "secure.jsonl"
        self.assertTrue(data_safety.append_bounded_jsonl(log_path, {"error_class": "syntax_compile"}, REPO_ROOT))
        self.assertEqual(stat.S_IMODE(log_path.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(log_path.stat().st_mode), 0o600)
        with self.assertRaises(ValueError):
            data_safety.append_bounded_jsonl(REPO_ROOT / "learning" / "raw.jsonl", {"safe": True}, REPO_ROOT)

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
