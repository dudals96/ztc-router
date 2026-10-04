#!/usr/bin/env python3
"""Shadow K1/K2 aggregate on synthetic telemetry (not real hook events)."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import _support  # noqa: F401

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "bench" / "shadow_aggregate.py"
_spec = importlib.util.spec_from_file_location("shadow_aggregate", _SCRIPT)
agg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agg)

DAY = 86400.0
T0 = 1790000000.0


def hook(i, outcome="ok", event="PreToolUse", rpc=2.0, ts=T0):
    return {"ts": ts, "client_version": "ztc-phase1-0.1", "request_id": f"r{i}", "outcome": outcome,
            "event": event, "tool": "Bash", "program": "secret-prog", "exit_code": None,
            "response_keys": [], "rpc_ms": rpc, "client_ms": rpc + 0.1}


def route(i, source, error_class=None):
    return {"ts": T0, "kind": "observe", "request_id": f"r{i}", "event": "PostToolUseFailure",
            "program": "secret-prog", "exit_code": 1, "source": source, "error_class": error_class,
            "signature": "deadbeef" if error_class else None, "queued": None, "handle_ms": 0.1}


class TestShadowAggregate(unittest.TestCase):
    def run_on(self, hooks, routes, window=7):
        with tempfile.TemporaryDirectory() as d:
            tel = Path(d) / "telemetry"
            tel.mkdir()
            (tel / "hook_events.jsonl").write_text("".join(json.dumps(h) + "\n" for h in hooks) + "not json\n")
            (tel / "router_events.jsonl").write_text("".join(json.dumps(r) + "\n" for r in routes))
            return agg.aggregate(Path(d), window)

    def test_k1_k2_and_window(self):
        hooks = [hook(i, rpc=float(i)) for i in range(1, 99)]
        hooks += [hook(99, outcome="timeout"), hook(100, ts=T0 + 3 * DAY)]
        routes = [route(1, "miss"), route(2, "l0_ledger", "syntax_compile"), route(3, "miss", "lint"), route(4, "pre")]
        r = self.run_on(hooks, routes)
        self.assertEqual(r["calls_total"], 100)
        self.assertEqual(r["outcomes"], {"ok": 99, "timeout": 1})
        self.assertEqual(r["k1"]["timeout_rate"], 0.01)
        self.assertEqual(r["k1"]["internal_rpc_ms_ok"]["n"], 99)
        self.assertEqual(r["collection"]["days_with_data"], 2)
        self.assertFalse(r["collection"]["window_met"])
        self.assertEqual((r["k2"]["failed_calls"], r["k2"]["l0_confirmed"]), (3, 2))
        self.assertEqual((r["k2"]["first_sighting"], r["k2"]["ledger_hit"]), (1, 1))

    def test_no_raw_strings_leak(self):
        r = self.run_on([hook(1)], [route(1, "l0_ledger", "syntax_compile")])
        text = json.dumps(r)
        self.assertNotIn("secret-prog", text)
        self.assertNotIn("deadbeef", text)

    def test_empty_home(self):
        with tempfile.TemporaryDirectory() as d:
            r = agg.aggregate(Path(d), 7)
        self.assertEqual(r["calls_total"], 0)
        self.assertIsNone(r["k1"]["timeout_rate"])
        self.assertIsNone(r["k2"]["rate"])


if __name__ == "__main__":
    unittest.main()
