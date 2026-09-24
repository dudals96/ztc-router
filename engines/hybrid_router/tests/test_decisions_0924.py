#!/usr/bin/env python3
"""User decisions 2026-09-24 (after the merge): 14-day telemetry retention and the
PostToolUseFailure payload (hooks reference: `error` = "Exit code N\\n<output>")."""

import json
import os
import time
import unittest

from _support import FakeServer, IsolatedHomeTest
from test_hook_client import HookClientTest
from ztc import telemetry


class TestRetention(IsolatedHomeTest):
    def test_prune_drops_only_records_older_than_14_days(self):
        now = time.time()
        telemetry.append("s", {"n": 1})
        path = self.home / "telemetry" / "s.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": now - 15 * 86400, "n": "old"}) + "\n")
            f.write(json.dumps({"ts": now - 13 * 86400, "n": "recent"}) + "\n")
            f.write("not json\n")
        result = telemetry.prune(now=now)
        self.assertEqual(result["dropped"], 1)
        rows = path.read_text().splitlines()
        self.assertEqual(len(rows), 3)
        self.assertFalse(any('"old"' in r for r in rows))
        self.assertEqual(oct(os.stat(path).st_mode & 0o777), "0o600")

    def test_prune_skips_symlinks(self):
        telemetry.append("s", {"n": 1})
        target = self.home / "outside.jsonl"
        target.write_text(json.dumps({"ts": 1}) + "\n")
        (self.home / "telemetry" / "link.jsonl").symlink_to(target)
        result = telemetry.prune()
        self.assertEqual(result["skipped_symlinks"], 1)
        self.assertIn('"ts": 1', target.read_text())

    def test_default_is_14_days(self):
        self.assertEqual(telemetry.RETENTION_DAYS, 14)


def failure_payload(error, interrupt=False):
    return {"session_id": "s", "hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "cwd": "/tmp/x",
            "tool_input": {"command": "npm test"}, "tool_use_id": "t", "error": error, "is_interrupt": interrupt}


class TestPostToolUseFailure(HookClientTest):
    def sent(self, payload):
        with FakeServer(reply={"verdict": None}) as srv:
            self.assert_neutral(self.run_client(json.dumps(payload).encode(), srv.port))
        return json.loads(srv.bodies[0])

    def test_exit_code_line_is_parsed_and_stripped(self):
        body = self.sent(failure_payload("Exit code 1\nError: Cannot find module 'express'"))
        self.assertEqual(body["exit_code"], 1)
        self.assertEqual(body["event"], "PostToolUseFailure")
        self.assertIn("Cannot find module", body["text"])
        self.assertNotIn("Exit code", body["text"])

    def test_tail_is_kept_for_long_output(self):
        noise = "progress line\n" * 400
        body = self.sent(failure_payload("Exit code 2\n" + noise + "FATAL: the real error"))
        self.assertTrue(body["text"].endswith("FATAL: the real error"))
        self.assertLessEqual(len(body["text"]), 500)

    def test_bare_message_without_exit_line(self):
        body = self.sent(failure_payload("spawn /bin/sh ENOENT"))
        self.assertIsNone(body["exit_code"])
        self.assertIn("ENOENT", body["text"])

    def test_secrets_in_failure_output_are_masked(self):
        secret = "sk-ant-api03-" + "Z" * 40
        body = self.sent(failure_payload(f"Exit code 1\ncurl: auth failed for {secret}"))
        self.assertNotIn(secret, json.dumps(body))


if __name__ == "__main__":
    unittest.main()
