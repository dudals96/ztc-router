#!/usr/bin/env python3
"""Hook client failure paths (run before any registration, W2-9).

For every case: stdout is exactly "{}", stderr is empty, exit code is 0.
Cases: daemon absent, timeout, permission denied (HTTP 403 and unwritable home),
cancellation (SIGTERM mid-RPC), overload (HTTP 503 and auto-disable), invalid JSON,
stdin over 64 KB, python3 missing. Plus the happy path and masking of what is sent.
"""

import json
import os
import signal
import subprocess
import threading
import time
import unittest

from _support import REPO_ROOT, FakeServer, IsolatedHomeTest, SilentServer, free_port

CLIENT = REPO_ROOT / "scripts" / "hooks" / "router-client.sh"
SECRET = "sk-ant-api03-" + "Q" * 40


def post_payload(stderr="SyntaxError: bad token", command="npm run build", cwd="/Users/someone/repo"):
    return {
        "session_id": "sess-1", "hook_event_name": "PostToolUse", "tool_name": "Bash", "cwd": cwd,
        "tool_input": {"command": command},
        "tool_response": {"stdout": "", "stderr": stderr, "interrupted": False},
    }


class HookClientTest(IsolatedHomeTest):
    def run_client(self, stdin: bytes, port: int, env_extra=None, timeout=5):
        env = {**os.environ, "PI_ROUTER_HOME": str(self.home), "PI_ROUTER_PORT": str(port), **(env_extra or {})}
        return subprocess.run([str(CLIENT)], input=stdin, capture_output=True, env=env, timeout=timeout)

    def assert_neutral(self, proc):
        self.assertEqual(proc.stdout, b"{}")
        self.assertEqual(proc.stderr, b"")
        self.assertEqual(proc.returncode, 0)

    def events(self):
        path = self.home / "telemetry" / "hook_events.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def last_outcome(self):
        return self.events()[-1]["outcome"]


class TestFailurePaths(HookClientTest):
    def test_01_daemon_absent(self):
        proc = self.run_client(json.dumps(post_payload()).encode(), free_port())
        self.assert_neutral(proc)
        self.assertEqual(self.last_outcome(), "absent")

    def test_02_timeout_respects_internal_budget(self):
        with SilentServer() as srv:
            t0 = time.perf_counter()
            proc = self.run_client(json.dumps(post_payload()).encode(), srv.port)
            elapsed = (time.perf_counter() - t0) * 1000
        self.assert_neutral(proc)
        ev = self.events()[-1]
        self.assertEqual(ev["outcome"], "timeout")
        self.assertLess(ev["rpc_ms"], 30 + 15)  # budget is enforced inside the client
        self.assertLess(elapsed, 2000)

    def test_03a_permission_denied_by_daemon(self):
        with FakeServer(status=403) as srv:
            proc = self.run_client(json.dumps(post_payload()).encode(), srv.port)
        self.assert_neutral(proc)
        self.assertEqual(self.last_outcome(), "denied")

    def test_03b_unwritable_home(self):
        self.home.mkdir(parents=True)
        os.chmod(self.home, 0o500)
        try:
            with FakeServer() as srv:
                proc = self.run_client(json.dumps(post_payload()).encode(), srv.port)
        finally:
            os.chmod(self.home, 0o700)
        self.assert_neutral(proc)

    def test_04_cancelled_mid_rpc(self):
        with SilentServer() as srv:
            env = {**os.environ, "PI_ROUTER_HOME": str(self.home), "PI_ROUTER_PORT": str(srv.port)}
            proc = subprocess.Popen([str(CLIENT)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, env=env)
            proc.stdin.write(json.dumps(post_payload()).encode())
            proc.stdin.close()
            deadline = time.monotonic() + 3
            while not srv.conns and time.monotonic() < deadline:  # helper is now inside the RPC
                time.sleep(0.001)
            # cancel the helper (a harness-side cancel would kill the whole hook; see contract)
            subprocess.run(["pkill", "-TERM", "-P", str(proc.pid)], check=False)
            out, err = proc.communicate(timeout=5)
        self.assertEqual((out, err, proc.returncode), (b"{}", b"", 0))
        # the 30 ms budget may expire before the signal lands; both end neutral and are recorded
        self.assertIn(self.last_outcome(), {"cancelled", "timeout"})

    def test_05a_overloaded_daemon(self):
        with FakeServer(status=503) as srv:
            proc = self.run_client(json.dumps(post_payload()).encode(), srv.port)
        self.assert_neutral(proc)
        self.assertEqual(self.last_outcome(), "overloaded")

    def test_05b_auto_disable_after_repeated_failure(self):
        port = free_port()
        for _ in range(21):
            self.assert_neutral(self.run_client(json.dumps(post_payload()).encode(), port))
        marker = self.home / "disabled"
        self.assertTrue(marker.exists())
        with FakeServer() as srv:
            proc = self.run_client(json.dumps(post_payload()).encode(), srv.port)
            self.assertEqual(srv.bodies, [])  # disabled: daemon is not called
        self.assert_neutral(proc)
        self.assertEqual(self.last_outcome(), "disabled")
        self.assertTrue(any("auto_disabled" in e for e in self.events()))

    def test_06_invalid_json(self):
        with FakeServer() as srv:
            proc = self.run_client(b"{not json", srv.port)
            self.assertEqual(srv.bodies, [])
        self.assert_neutral(proc)
        self.assertEqual(self.last_outcome(), "bad_json")

    def test_07_stdin_over_64kb(self):
        big = json.dumps(post_payload(stderr="x" * (70 * 1024))).encode()
        with FakeServer() as srv:
            proc = self.run_client(big, srv.port)
            self.assertEqual(srv.bodies, [])
        self.assert_neutral(proc)
        self.assertEqual(self.last_outcome(), "oversize")

    def test_08_python_missing(self):
        proc = self.run_client(json.dumps(post_payload()).encode(), free_port(), {"PATH": "/nonexistent"})
        # /bin/sh builtins still work; printf is a builtin in sh
        self.assertEqual(proc.stdout, b"{}")
        self.assertEqual(proc.returncode, 0)

    def test_09_settings_guard_when_script_absent(self):
        guard = '[ -x "./scripts/hooks/router-client.sh" ] && ./scripts/hooks/router-client.sh || printf "{}"'
        with self.subTest("absent"):
            proc = subprocess.run(["/bin/sh", "-c", guard], input=b"{}", capture_output=True, cwd=str(self.home.parent))
            self.assertEqual((proc.stdout, proc.returncode), (b"{}", 0))


class TestHappyPath(HookClientTest):
    def test_ok_and_masked_body(self):
        payload = post_payload(stderr=f"SyntaxError at /Users/someone/repo/src/a.py:3 key={SECRET}",
                               command=f"/Users/someone/bin/tool --api-key {SECRET}")
        with FakeServer(reply={"verdict": None}) as srv:
            proc = self.run_client(json.dumps(payload).encode(), srv.port)
            sent = srv.bodies[0].decode()
        self.assert_neutral(proc)
        self.assertNotIn(SECRET, sent)
        self.assertNotIn("/Users/someone", sent)
        body = json.loads(sent)
        self.assertEqual(body["program"], "<ABS>/tool")
        self.assertIn("src/a.py:3", body["text"])
        ev = self.events()[-1]
        self.assertEqual(ev["outcome"], "ok")
        self.assertEqual(ev["response_keys"], ["interrupted", "stderr", "stdout"])
        self.assertIsNotNone(ev["rpc_ms"])
        self.assertNotIn(SECRET, (self.home / "telemetry" / "hook_events.jsonl").read_text())

    def test_pre_tool_use(self):
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ls -la"}}
        with FakeServer() as srv:
            proc = self.run_client(json.dumps(payload).encode(), srv.port)
            body = json.loads(srv.bodies[0])
        self.assert_neutral(proc)
        self.assertEqual((body["event"], body["program"], body["text"]), ("PreToolUse", "ls", ""))

    def test_concurrent_invocations_all_neutral(self):
        with FakeServer() as srv:
            procs = []
            threads = [threading.Thread(target=lambda: procs.append(
                self.run_client(json.dumps(post_payload()).encode(), srv.port))) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(10)
        self.assertEqual(len(procs), 3)
        for p in procs:
            self.assert_neutral(p)


class TestNonMac(HookClientTest):
    def test_non_darwin_skips_python(self):
        with FakeServer() as srv:
            proc = self.run_client(json.dumps(post_payload()).encode(), srv.port, {"PI_HOOK_OS": "msys"})
            self.assertEqual(srv.bodies, [])
        self.assert_neutral(proc)
        self.assertEqual(self.events(), [])


if __name__ == "__main__":
    unittest.main()
