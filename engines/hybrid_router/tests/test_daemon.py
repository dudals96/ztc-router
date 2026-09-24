#!/usr/bin/env python3
"""Router daemon: local bind, size limit, request ids, real health, sanitised telemetry,
L0 answer path, async judge write-through, and no serialisation behind a slow client."""

import json
import socket
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from _support import IsolatedHomeTest, load_script_module

daemon = load_script_module("hybrid_router_daemon", "hybrid-router-daemon.py")
SECRET = "ghp_" + "S" * 36


class DaemonTest(IsolatedHomeTest):
    def setUp(self):
        super().setUp()
        self.server, self.state = daemon.make_server(port=0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.state.close()
        super().tearDown()

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def post(self, path, body, headers=None):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        req = Request(self.url(path), data=data, headers={"Content-Type": "application/json", **(headers or {})})
        with urlopen(req, timeout=3) as resp:
            return resp.status, json.loads(resp.read()), resp.headers

    def observe(self, text, program="npm", event="PostToolUse"):
        return self.post("/v1/observe", {"event": event, "program": program, "text": text, "exit_code": 1})[1]


class TestDaemon(DaemonTest):
    def test_binds_loopback_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        self.assertEqual(daemon.BIND_HOST, "127.0.0.1")

    def test_health_checks_ledger_and_worker(self):
        with urlopen(self.url("/health"), timeout=3) as resp:
            body = json.loads(resp.read())
        self.assertEqual(body["status"], "ready")
        self.assertTrue(body["ledger"] and body["judge_worker"])
        self.state.queue.shutdown()
        with self.assertRaises(HTTPError) as ctx:
            urlopen(self.url("/health"), timeout=3)
        self.assertEqual(ctx.exception.code, 503)
        ctx.exception.close()

    def test_payload_over_64kb_is_413(self):
        with self.assertRaises(HTTPError) as ctx:
            self.post("/v1/observe", b"{" + b" " * (64 * 1024) + b"}")
        self.assertEqual(ctx.exception.code, 413)
        ctx.exception.close()

    def test_invalid_json_is_400(self):
        with self.assertRaises(HTTPError) as ctx:
            self.post("/v1/observe", b"{not json")
        self.assertEqual(ctx.exception.code, 400)
        ctx.exception.close()

    def test_request_id_echo_and_generation(self):
        _, body, headers = self.post("/v1/observe", {"event": "PreToolUse"}, {"X-Request-Id": "abc-123"})
        self.assertEqual(headers["X-Request-Id"], "abc-123")
        self.assertEqual(body["request_id"], "abc-123")
        _, body, headers = self.post("/v1/observe", {"event": "PreToolUse"}, {"X-Request-Id": "bad id!"})
        self.assertRegex(headers["X-Request-Id"], r"^[0-9a-f]{16}$")

    def test_regex_hit_answers_synchronously(self):
        res = self.observe("error TS2339: Property 'x' does not exist")
        self.assertEqual(res["verdict"]["source"], "l0_regex")
        self.assertEqual(res["verdict"]["error_class"], "syntax_compile")

    def test_miss_is_queued_then_ledger_hit_as_candidate(self):
        text = "fatal: heap out of memory while linking"
        first = self.observe(text)
        self.assertIsNone(first["verdict"])
        self.assertEqual(first["queued"], "queued")
        deadline = time.time() + 3
        while time.time() < deadline and self.state.queue.stats["done"] < 1:
            time.sleep(0.01)
        second = self.observe(text)
        self.assertEqual(second["verdict"]["source"], "l0_ledger")
        self.assertEqual(second["verdict"]["state"], "candidate")
        self.assertEqual(second["verdict"]["error_class"], "out_of_memory")

    def test_telemetry_has_no_commands_cwd_or_paths(self):
        self.post("/v1/observe", {"event": "PostToolUse", "program": "/Users/someone/bin/deploy",
                                  "cwd": "/Users/someone/secret-project", "exit_code": 1,
                                  "text": f"SyntaxError near --token {SECRET} in /Users/someone/app.py"})
        with urlopen(self.url("/telemetry"), timeout=3) as resp:
            snap = resp.read().decode()
        raw = (self.home / "telemetry" / "router_events.jsonl").read_text()
        for blob in (snap, raw):
            self.assertNotIn(SECRET, blob)
            self.assertNotIn("/Users/someone", blob)
            self.assertNotIn("secret-project", blob)
        self.assertIn("counters", json.loads(snap))

    def test_dashboard_has_no_inflated_numbers(self):
        with urlopen(self.url("/dashboard"), timeout=3) as resp:
            html = resp.read().decode()
        self.assertIn("shadow", html)
        self.assertNotIn("800배+ 고속화", html)
        self.assertNotIn("18ms 추론", html)

    def test_slow_client_does_not_serialise_others(self):
        slow = socket.create_connection(("127.0.0.1", self.port))
        slow.sendall(b"POST /v1/observe HTTP/1.1\r\nHost: x\r\nContent-Length: 100\r\n\r\n{\"ev")  # incomplete body
        try:
            t0 = time.perf_counter()
            results = []

            def call():
                results.append(self.post("/v1/observe", {"event": "PreToolUse"})[0])

            threads = [threading.Thread(target=call) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(5)
            elapsed = time.perf_counter() - t0
        finally:
            slow.close()
        self.assertEqual(results, [200, 200, 200])
        self.assertLess(elapsed, daemon.HANDLER_SOCKET_TIMEOUT_SEC)  # not stuck behind the slow client


if __name__ == "__main__":
    unittest.main()
