import importlib.util
import json
import multiprocessing
import os
import socket
import socketserver
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO_ROOT / "engines" / "hybrid_router"))
from router_data_safety import append_bounded_jsonl
from router_daemon_runtime import ShadowEventQueue
import router_daemon_runtime

DAEMON_SPEC = importlib.util.spec_from_file_location("hybrid_router_daemon", SCRIPTS / "hybrid-router-daemon.py")
if DAEMON_SPEC is None or DAEMON_SPEC.loader is None:
    raise RuntimeError("Could not load router daemon for shadow fixtures")
DAEMON_MODULE = importlib.util.module_from_spec(DAEMON_SPEC)
DAEMON_SPEC.loader.exec_module(DAEMON_MODULE)

CLIENT_PATH = SCRIPTS / "shadow_hook_client.py"


class SlowHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.recv(4096)
        time.sleep(0.2)


class TestShadowHookFixtures(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_home = Path(self.temp_dir.name) / "router-home"
        self.old_queue = DAEMON_MODULE.SHADOW_QUEUE
        self.old_home = DAEMON_MODULE.PI_ROUTER_HOME
        self.old_router = DAEMON_MODULE.router_instance
        self.queue = ShadowEventQueue(self.data_home / "interventions.jsonl", REPO_ROOT, maxsize=64)
        self.queue.start()
        DAEMON_MODULE.SHADOW_QUEUE = self.queue
        DAEMON_MODULE.PI_ROUTER_HOME = self.data_home
        DAEMON_MODULE.router_instance = object()
        self.server = DAEMON_MODULE.BoundedThreadingHTTPServer(("127.0.0.1", 0), DAEMON_MODULE.RouterHTTPHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.port = self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=1)
        self.assertTrue(self.queue.stop())
        DAEMON_MODULE.SHADOW_QUEUE = self.old_queue
        DAEMON_MODULE.PI_ROUTER_HOME = self.old_home
        DAEMON_MODULE.router_instance = self.old_router
        self.temp_dir.cleanup()

    def run_client(self, payload, port=None, timeout=2):
        environment = os.environ.copy()
        environment["PI_ROUTER_PORT"] = str(port or self.port)
        environment["PI_ROUTER_HOME"] = str(self.data_home)
        return subprocess.run(
            [sys.executable, str(CLIENT_PATH)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=environment,
            timeout=timeout,
            check=False,
        )

    def wait_for_queue(self):
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            if self.queue.events.unfinished_tasks == 0:
                return
            time.sleep(0.005)
        self.fail("shadow queue did not drain")

    def hook_input(self, event_name="PreToolUse", request_id="toolu_call_01"):
        secret = "sk_test_NeverLogThis1234567890abcdef"
        return {
            "hook_event_name": event_name,
            "tool_use_id": request_id,
            "tool_name": "Bash",
            "cwd": "/Users/alice/private-project",
            "permission_mode": "ask",
            "tool_input": {
                "command": f"cat /Users/alice/private-project/src/a.py token={secret}",
                "file_path": "/Users/alice/private-project/src/a.py:17",
                "result_path": "/Users/alice/private-project/out/result.json",
            },
            "tool_response": {"stderr": f"alice@example.com {secret}"},
        }

    def test_pre_and_post_events_pair_by_tool_use_id_and_stay_neutral(self):
        before = self.run_client(self.hook_input("PreToolUse"))
        after = self.run_client(self.hook_input("PostToolUse"))

        for result in (before, after):
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "{}\n")
            self.assertNotIn("permissionDecision", result.stdout)
            self.assertNotIn("additionalContext", result.stdout)
            self.assertNotIn("updatedInput", result.stdout)
            self.assertNotIn("updatedToolOutput", result.stdout)

        self.wait_for_queue()
        log_path = self.data_home / "interventions.jsonl"
        log_text = log_path.read_text(encoding="utf-8")
        rows = [json.loads(line) for line in log_text.splitlines()]
        self.assertEqual([row["intervention_type"] for row in rows], ["PreToolUse", "PostToolUse"])
        self.assertEqual({row["request_id"] for row in rows}, {"toolu_call_01"})
        for sensitive_value in ("sk_test_NeverLogThis1234567890abcdef", "alice", "private-project", "a.py", "result.json", "alice@example.com"):
            self.assertNotIn(sensitive_value, log_text)
        self.assertEqual(stat.S_IMODE(log_path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(log_path.parent.stat().st_mode), 0o700)

    def test_security_hook_fields_are_ignored_and_permissions_remain_undecided(self):
        payload = self.hook_input()
        payload["hookSpecificOutput"] = {"permissionDecision": "deny", "additionalContext": "must not pass through"}
        result = self.run_client(payload)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "{}\n")
        self.assertNotIn("must not pass through", result.stdout)

    def test_server_health_is_loopback_and_checks_router_and_queue(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        connection = HTTPConnection("127.0.0.1", self.port, timeout=1)
        connection.request("GET", "/health")
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(response.status, 200)
        self.assertEqual(payload["status"], "ready")
        self.assertTrue(payload["router_ready"])
        self.assertTrue(payload["shadow_queue"]["ready"])
        self.assertEqual(payload["port"], self.port)
        connection.close()

    def test_cancel_endpoint_prevents_admission_and_schema_rejects_decisions(self):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=1)
        cancel_body = json.dumps({"requestId": "toolu_cancel_01"}).encode("utf-8")
        connection.request("POST", "/cancel", body=cancel_body, headers={"Content-Type": "application/json"})
        cancel_response = connection.getresponse()
        self.assertEqual(cancel_response.status, 202)
        cancel_response.read()

        invalid_event = {
            "requestId": "toolu_cancel_01",
            "hookEvent": "PreToolUse",
            "toolName": "Bash",
            "fingerprint": "0123456789abcdef",
            "maskedFields": {},
            "permissionDecision": "allow",
        }
        event_body = json.dumps(invalid_event).encode("utf-8")
        connection.request("POST", "/shadow", body=event_body, headers={"Content-Type": "application/json"})
        event_response = connection.getresponse()

        self.assertEqual(event_response.status, 400)
        event_response.read()
        self.assertEqual(self.queue.events.qsize(), 0)
        connection.close()

    def test_telemetry_exposes_only_allowlisted_aggregate_fields(self):
        append_bounded_jsonl(
            self.data_home / "interventions.jsonl",
            {
                "cycle": "hybrid-router-intervention",
                "timestamp": "2026-09-24T00:00:00+0000",
                "intervention_type": "PostToolUse",
                "error_class": "shadow_observation",
                "request_id": "toolu_sensitive_id",
                "masked_fields": {"stderr": "never expose this field"},
                "latency_ms": 10,
                "latency_kind": "measured_wall_clock",
            },
            REPO_ROOT,
        )
        connection = HTTPConnection("127.0.0.1", self.port, timeout=1)
        connection.request("GET", "/telemetry")
        response = connection.getresponse()
        response_text = response.read().decode("utf-8")

        self.assertEqual(response.status, 200)
        self.assertNotIn("toolu_sensitive_id", response_text)
        self.assertNotIn("never expose this field", response_text)
        self.assertNotIn("masked_fields", response_text)
        self.assertIn('"interventions_count":1', response_text)
        connection.close()

    def test_malformed_input_and_oversized_input_return_neutral_json(self):
        environment = os.environ.copy()
        environment["PI_ROUTER_PORT"] = str(self.port)
        malformed = subprocess.run([sys.executable, str(CLIENT_PATH)], input="{", text=True, capture_output=True, env=environment, check=False)
        oversized = subprocess.run([sys.executable, str(CLIENT_PATH)], input=" " * (64 * 1024 + 1), text=True, capture_output=True, env=environment, check=False)

        for result in (malformed, oversized):
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "{}\n")
        self.assertEqual(self.queue.events.qsize(), 0)

    def test_oversized_http_payload_gets_413_without_queueing(self):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=1)
        connection.request("POST", "/shadow", body=b" " * (64 * 1024 + 1), headers={"Content-Length": str(64 * 1024 + 1)})
        response = connection.getresponse()

        self.assertEqual(response.status, 413)
        self.assertEqual(self.queue.events.qsize(), 0)
        connection.close()

    def test_malformed_http_json_gets_400_without_queueing(self):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=1)
        connection.request("POST", "/shadow", body=b"{", headers={"Content-Length": "1", "Content-Type": "application/json"})
        response = connection.getresponse()

        self.assertEqual(response.status, 400)
        self.assertEqual(self.queue.events.qsize(), 0)
        connection.close()

    def test_daemon_absent_and_rpc_timeout_return_neutral_json(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            unused_port = probe.getsockname()[1]
        absent = self.run_client(self.hook_input(), port=unused_port)
        self.assertEqual(absent.returncode, 0)
        self.assertEqual(absent.stdout, "{}\n")

        slow_server = socketserver.TCPServer(("127.0.0.1", 0), SlowHandler)
        slow_thread = threading.Thread(target=slow_server.serve_forever, daemon=True)
        slow_thread.start()
        try:
            timed_out = self.run_client(self.hook_input("PostToolUse", "toolu_timeout_01"), port=slow_server.server_address[1])
        finally:
            slow_server.shutdown()
            slow_server.server_close()
            slow_thread.join(timeout=1)
        self.assertEqual(timed_out.returncode, 0)
        self.assertEqual(timed_out.stdout, "{}\n")

    def test_malformed_response_returns_neutral_json(self):
        class MalformedHandler(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.recv(8192)
                self.request.sendall(b"HTTP/1.1 202 Accepted\r\nContent-Length: 3\r\nConnection: close\r\n\r\nbad")

        malformed_server = socketserver.TCPServer(("127.0.0.1", 0), MalformedHandler)
        malformed_thread = threading.Thread(target=malformed_server.serve_forever, daemon=True)
        malformed_thread.start()
        try:
            result = self.run_client(self.hook_input("PostToolUse", "toolu_bad_response"), port=malformed_server.server_address[1])
        finally:
            malformed_server.shutdown()
            malformed_server.server_close()
            malformed_thread.join(timeout=1)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "{}\n")

    def test_queue_deduplicates_cancels_overload_and_stops_without_children(self):
        entered_writer = threading.Event()
        release_writer = threading.Event()

        def slow_writer(*_args):
            entered_writer.set()
            release_writer.wait(timeout=1)
            return True

        queue = ShadowEventQueue(self.data_home / "queue.jsonl", REPO_ROOT, maxsize=1)
        with patch.object(router_daemon_runtime, "append_bounded_jsonl", side_effect=slow_writer):
            queue.start()
            base = {
                "hookEvent": "PreToolUse",
                "toolName": "Bash",
                "fingerprint": "0123456789abcdef",
                "maskedFields": {"command": "echo safe"},
            }
            self.assertEqual(queue.enqueue({**base, "requestId": "request-one"}), (True, "accepted"))
            self.assertTrue(entered_writer.wait(timeout=1))
            self.assertEqual(queue.enqueue({**base, "requestId": "request-two"}), (True, "accepted"))
            self.assertEqual(queue.enqueue({**base, "requestId": "request-three"}), (False, "overloaded"))
            self.assertEqual(queue.enqueue({**base, "requestId": "request-one"}), (True, "duplicate"))
            self.assertTrue(queue.cancel("request-two"))
            release_writer.set()
            deadline = time.monotonic() + 1
            while queue.events.unfinished_tasks and time.monotonic() < deadline:
                time.sleep(0.005)
            self.assertEqual(queue.status()["processed_count"], 1)
            self.assertEqual(queue.status()["dropped_count"], 1)
            self.assertTrue(queue.stop())

        self.assertNotIn(queue.worker, threading.enumerate())
        self.assertIn(self.queue.worker, threading.enumerate())
        self.assertEqual(multiprocessing.active_children(), [])


if __name__ == "__main__":
    unittest.main()
