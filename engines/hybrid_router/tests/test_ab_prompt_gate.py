#!/usr/bin/env python3
"""A/B prompt gate (UserPromptSubmit): asks only while the daemon is ready, never blocks.

For every case: exit code 0, stderr empty, stdout is "{}" or one JSON object whose only
decision-bearing content is hookSpecificOutput.additionalContext (no "decision").
"""

import json
import os
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from _support import REPO_ROOT, IsolatedHomeTest, SilentServer, free_port

GATE = REPO_ROOT / "scripts" / "hooks" / "ab-prompt-gate.sh"
HELPER = REPO_ROOT / "scripts" / "hooks" / "ab_prompt_gate.py"
PROMPT = "비밀 지시문 sk-ant-api03-" + "Q" * 40


class HealthServer:
    def __init__(self, status=200, reply=None):
        outer = self
        self.status, self.reply = status, reply if reply is not None else {"status": "ready"}

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                data = json.dumps(outer.reply).encode()
                self.send_response(outer.status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def payload(cwd="/tmp/nowhere"):
    return json.dumps({"session_id": "s1", "hook_event_name": "UserPromptSubmit",
                       "cwd": cwd, "prompt": PROMPT}).encode()


class GateTest(IsolatedHomeTest):
    def run_gate(self, stdin: bytes, port: int, env_extra=None):
        env = {k: v for k, v in os.environ.items() if k not in ("PI_AB_ARM", "CLAUDE_PROJECT_DIR")}
        cfg = self.home.parent / "ab_gate_on.json"
        cfg.write_text('{"enabled": true}')
        env.update({"PI_ROUTER_HOME": str(self.home), "PI_ROUTER_PORT": str(port),
                    "PI_AB_GATE_CONFIG": str(cfg), **(env_extra or {})})
        proc = subprocess.run([str(GATE)], input=stdin, capture_output=True, env=env, timeout=5)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, b"")
        return proc.stdout

    def events(self):
        path = self.home / "telemetry" / "ab_gate.jsonl"
        return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []

    def test_asks_when_daemon_ready(self):
        with HealthServer() as srv:
            out = json.loads(self.run_gate(payload(), srv.port))
        self.assertNotIn("decision", out)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        self.assertIn("AskUserQuestion", ctx)
        ev = self.events()[-1]
        self.assertEqual(ev["outcome"], "asked")
        self.assertIn(ev["gate_id"], ctx)
        self.assertEqual(ev["prompt_len"], len(PROMPT))

    def test_silent_when_switched_off(self):
        cfg = self.home.parent / "ab_gate_off.json"
        cfg.write_text('{"enabled": false}')
        with HealthServer() as srv:
            self.assertEqual(self.run_gate(payload(), srv.port, {"PI_AB_GATE_CONFIG": str(cfg)}), b"{}")
        self.assertEqual(self.events()[-1]["outcome"], "disabled")

    def test_repo_switch_is_off_until_phase2(self):
        cfg = json.loads((REPO_ROOT / "config" / "ab_gate.json").read_text(encoding="utf-8"))
        self.assertIs(cfg["enabled"], False)

    def test_prompt_text_never_stored(self):
        with HealthServer() as srv:
            self.run_gate(payload(), srv.port)
        text = (self.home / "telemetry" / "ab_gate.jsonl").read_text()
        self.assertNotIn("sk-ant", text)
        self.assertNotIn("비밀", text)

    def test_silent_when_daemon_absent(self):
        self.assertEqual(self.run_gate(payload(), free_port()), b"{}")
        self.assertEqual(self.events()[-1]["outcome"], "daemon_not_ready")

    def test_silent_when_daemon_not_ready(self):
        with HealthServer(status=503, reply={"status": "degraded"}) as srv:
            self.assertEqual(self.run_gate(payload(), srv.port), b"{}")

    def test_silent_when_ready_flag_missing(self):
        with HealthServer(reply={"status": "starting"}) as srv:
            self.assertEqual(self.run_gate(payload(), srv.port), b"{}")

    def test_health_timeout_bounded(self):
        with SilentServer() as srv:
            self.assertEqual(self.run_gate(payload(), srv.port), b"{}")
        self.assertLess(self.events()[-1]["gate_ms"], 300 + 100)

    def test_skipped_inside_arm_env(self):
        with HealthServer() as srv:
            self.assertEqual(self.run_gate(payload(), srv.port, {"PI_AB_ARM": "A"}), b"{}")
        self.assertEqual(self.events()[-1]["outcome"], "in_arm")

    def test_skipped_inside_arm_marker(self):
        proj = self.home.parent / "arm-wt"
        proj.mkdir(parents=True)
        (proj / ".pi-ab-arm").write_text("B\n")
        with HealthServer() as srv:
            out = self.run_gate(payload(), srv.port, {"CLAUDE_PROJECT_DIR": str(proj)})
        self.assertEqual(out, b"{}")

    def test_skipped_for_harness_notifications(self):
        for prompt in ("<task-notification>\n<task-id>x</task-id>",
                       "Another Claude session sent a message:\n<agent-message from=\"a1\">report"):
            body = json.dumps({"session_id": "s1", "prompt": prompt}).encode()
            with HealthServer() as srv:
                self.assertEqual(self.run_gate(body, srv.port), b"{}")
            self.assertEqual(self.events()[-1]["outcome"], "system_event")

    def test_bad_json(self):
        with HealthServer() as srv:
            self.assertEqual(self.run_gate(b"not json", srv.port), b"{}")
        self.assertEqual(self.events()[-1]["outcome"], "bad_json")

    def test_python_missing(self):
        env = {"PATH": "/nonexistent", "PI_ROUTER_HOME": str(self.home)}
        proc = subprocess.run(["/bin/sh", str(GATE)], input=payload(), capture_output=True, env=env, timeout=5)
        self.assertEqual((proc.stdout, proc.returncode), (b"{}", 0))

    def test_non_darwin_is_silent(self):
        with HealthServer() as srv:
            out = self.run_gate(payload(), srv.port, {"PI_HOOK_OS": "msys"})
        self.assertEqual(out, b"{}")
        self.assertEqual(self.events(), [])  # python never started

    def test_non_json_helper_output_dropped(self):
        fake = self.home.parent / "bin2"
        fake.mkdir(parents=True)
        (fake / "python3").write_text("#!/bin/sh\ncat >/dev/null; echo 'Python was not found'\n")
        (fake / "python3").chmod(0o755)
        with HealthServer() as srv:
            out = self.run_gate(payload(), srv.port, {"PATH": f"{fake}:{os.environ['PATH']}"})
        self.assertEqual(out, b"{}")

    def test_record_answer(self):
        env = {**os.environ, "PI_ROUTER_HOME": str(self.home)}
        ok = subprocess.run(["python3", str(HELPER), "record", "abc123", "apply"], capture_output=True, env=env)
        bad = subprocess.run(["python3", str(HELPER), "record", "abc123", "maybe"], capture_output=True, env=env)
        self.assertEqual((ok.returncode, bad.returncode), (0, 2))
        ev = self.events()
        self.assertEqual(len(ev), 1)
        self.assertEqual((ev[0]["kind"], ev[0]["decision"]), ("answer", "apply"))


if __name__ == "__main__":
    unittest.main()
