#!/usr/bin/env python3
"""Router health check: restarts a daemon that is not ready, reports gate wiring, notifies on change."""

import json
import os
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from _support import REPO_ROOT, IsolatedHomeTest, free_port

SCRIPT = REPO_ROOT / "scripts" / "router_healthcheck.py"


class FlipServer:
    """/health answers 503 until the flag file exists, then 200 ready."""

    def __init__(self, flag: Path):
        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                ready = flag.exists()
                data = json.dumps({"status": "ready" if ready else "degraded"}).encode()
                self.send_response(200 if ready else 503)
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


class HealthcheckTest(IsolatedHomeTest):
    def setUp(self):
        super().setUp()
        self.base = self.home.parent
        self.user_home = self.base / "user"
        (self.user_home / ".claude").mkdir(parents=True)
        (self.user_home / ".codex").mkdir(parents=True)
        (self.user_home / ".claude" / "settings.json").write_text('{"hooks": "…/ab-prompt-gate.sh"}')
        (self.user_home / ".codex" / "config.toml").write_text("command = '…/ab-prompt-gate.sh'\n")
        self.flag = self.base / "ready.flag"
        self.calls = self.base / "launchctl.log"
        self.notes = self.base / "notify.log"
        fake = self.base / "fake-launchctl"
        # print -> rc from FAKE_PRINT_RC; kickstart/bootstrap -> make /health ready.
        fake.write_text(f"""#!/bin/sh
echo "$*" >> "{self.calls}"
case "$1" in
print) exit "${{FAKE_PRINT_RC:-0}}" ;;
kickstart|bootstrap) touch "{self.flag}"; exit 0 ;;
esac
exit 0
""")
        fake.chmod(0o755)
        notifier = self.base / "fake-notify"
        notifier.write_text(f'#!/bin/sh\necho "$1|$2" >> "{self.notes}"\n')
        notifier.chmod(0o755)
        self.fake, self.notifier = fake, notifier

    def run_check(self, port: int, *args, env_extra=None):
        env = {**os.environ, "HOME": str(self.user_home), "PI_ROUTER_HOME": str(self.home),
               "PI_ROUTER_PORT": str(port), "PI_LAUNCHCTL": str(self.fake),
               "PI_NOTIFY_CMD": str(self.notifier), "PI_HC_WAIT_SEC": "3", **(env_extra or {})}
        proc = subprocess.run(["python3", str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=30)
        return proc.returncode, json.loads(proc.stdout.strip().splitlines()[-1])

    def calls_made(self):
        return self.calls.read_text().splitlines() if self.calls.exists() else []

    def notifications(self):
        return self.notes.read_text().splitlines() if self.notes.exists() else []

    def test_ready_daemon_is_quiet(self):
        self.flag.touch()
        with FlipServer(self.flag) as srv:
            rc, res = self.run_check(srv.port)
            rc2, _ = self.run_check(srv.port)
        self.assertEqual((rc, rc2, res["status"], res["actions"]), (0, 0, "ok", []))
        self.assertFalse(any(c.startswith("kickstart") for c in self.calls_made()))
        self.assertEqual(self.notifications(), [])
        status = json.loads((self.home / "health_status.json").read_text())
        self.assertEqual(status["status"], "ok")
        self.assertEqual((self.home / "health_status.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual(len((self.home / "telemetry" / "healthcheck.jsonl").read_text().splitlines()), 2)

    def test_not_ready_daemon_is_kickstarted(self):
        with FlipServer(self.flag) as srv:
            rc, res = self.run_check(srv.port)
        self.assertEqual((rc, res["status"], res["daemon"], res["actions"]), (0, "recovered", "ready", ["kickstart"]))
        self.assertTrue(any(c.startswith("kickstart -k gui/") for c in self.calls_made()))
        self.assertEqual(len(self.notifications()), 1)
        self.assertIn("복구", self.notifications()[0])

    def test_unloaded_daemon_is_bootstrapped(self):
        plist = self.user_home / "Library" / "LaunchAgents" / "com.pi.router-daemon.plist"
        plist.parent.mkdir(parents=True)
        plist.write_text("<plist/>")
        with FlipServer(self.flag) as srv:
            rc, res = self.run_check(srv.port, env_extra={"FAKE_PRINT_RC": "113"})
        self.assertEqual((rc, res["actions"], res["loaded"]), (0, ["bootstrap"], True))
        self.assertTrue(any(c.startswith("bootstrap gui/") and c.endswith(str(plist)) for c in self.calls_made()))

    def test_dead_daemon_reports_problem_and_notifies_once(self):
        port = free_port()  # nothing listens; the fake kickstart cannot bring it up
        rc, res = self.run_check(port)
        rc2, _ = self.run_check(port)
        self.assertEqual((rc, rc2, res["status"]), (1, 1, "problem"))
        self.assertIn("daemon_down", res["problems"])
        # a lasting problem notifies once, not every 5 minutes
        self.assertEqual(len(self.notifications()), 1)
        self.assertIn("점검 필요", self.notifications()[0])

    def test_dry_run_changes_nothing(self):
        rc, res = self.run_check(free_port(), "--dry-run")
        self.assertEqual((rc, res["actions"]), (1, []))
        self.assertFalse(any(c.startswith(("kickstart", "bootstrap")) for c in self.calls_made()))
        self.assertFalse((self.home / "health_status.json").exists())
        self.assertEqual(self.notifications(), [])

    def test_missing_gate_hooks_are_problems(self):
        (self.user_home / ".codex" / "config.toml").write_text("model = 'x'\n")
        (self.user_home / ".claude" / "settings.json").unlink()
        self.flag.touch()
        with FlipServer(self.flag) as srv:
            rc, res = self.run_check(srv.port)
        self.assertEqual(rc, 1)
        self.assertEqual({p for p in res["problems"] if p.startswith("gate_")},
                         {"gate_hook_missing_claude", "gate_hook_missing_codex"})

    def test_notes_do_not_fail(self):
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / "ab_gate_state.json").write_text('{"paused": true}')
        (self.home / "disabled").write_text("x")
        self.flag.touch()
        with FlipServer(self.flag) as srv:
            rc, res = self.run_check(srv.port)
        self.assertEqual(rc, 0)
        self.assertEqual(set(res["notes"]), {"gate_paused_by_user", "client_auto_disabled"})


if __name__ == "__main__":
    unittest.main()
