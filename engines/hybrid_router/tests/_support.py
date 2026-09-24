"""Shared test helpers: isolated PI_ROUTER_HOME, repo paths, tiny fake HTTP servers."""

import json
import os
import socket
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ENGINE_DIR = TESTS_DIR.parent
REPO_ROOT = ENGINE_DIR.parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(ENGINE_DIR))


class IsolatedHomeTest(unittest.TestCase):
    """Each test gets its own PI_ROUTER_HOME and never touches ~/.pi-router."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="ztc-test-")
        self.home = Path(self._tmp.name) / "home"
        self._old_env = {k: os.environ.get(k) for k in ("PI_ROUTER_HOME", "PI_ROUTER_PORT", "JEV_ENDPOINT")}
        os.environ["PI_ROUTER_HOME"] = str(self.home)
        os.environ.pop("JEV_ENDPOINT", None)

    def tearDown(self):
        for k, v in self._old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmp.cleanup()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeServer:
    """HTTP server on 127.0.0.1 with a pluggable behaviour: status code, JSON reply, delay."""

    def __init__(self, status=200, reply=None, delay=0.0):
        self.status, self.reply, self.delay = status, reply or {}, delay
        self.bodies = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                outer.bodies.append(self.rfile.read(n))
                if outer.delay:
                    threading.Event().wait(outer.delay)
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


class SilentServer:
    """Accepts connections and never answers (timeout / cancellation fixtures)."""

    def __init__(self):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.port = self.sock.getsockname()[1]
        self.conns = []
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._accept, daemon=True)

    def _accept(self):
        self.sock.settimeout(0.1)
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
                self.conns.append(conn)
            except OSError:
                continue

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self.thread.join(1)
        for c in self.conns:
            c.close()
        self.sock.close()


def load_script_module(name: str, filename: str):
    """Import a hyphenated script from scripts/ by path."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
