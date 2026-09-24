#!/usr/bin/env python3
"""Honesty gate: simulation constants and inflated dashboard claims stay out of the code."""

import re
import unittest

from _support import ENGINE_DIR, REPO_ROOT

# Same expression as the directive's completion grep (W2-1).
CONSTANTS = re.compile(r"18\.5|34\.2|38\.5|18\.0|18\.2|12\.0|0\.045|0\.98")
CLAIMS = ("18ms", "18 ms 추론", "800배", "99.8% 시간", "100% 토큰 절감")
SCOPE = [
    *(p for p in ENGINE_DIR.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix in (".py", ".json")),
    REPO_ROOT / "scripts" / "hybrid-router-daemon.py",
    REPO_ROOT / "scripts" / "decision-gate-interceptor.py",
]
THIS_FILE = __file__


class TestHonesty(unittest.TestCase):
    def test_no_simulation_constants(self):
        hits = []
        for path in SCOPE:
            if path.samefile(THIS_FILE):
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if CONSTANTS.search(line):
                    hits.append(f"{path.relative_to(REPO_ROOT)}:{n}: {line.strip()}")
        self.assertEqual(hits, [])

    def test_daemon_has_no_inflated_claims_outside_the_disclaimer(self):
        text = (REPO_ROOT / "scripts" / "hybrid-router-daemon.py").read_text(encoding="utf-8")
        for claim in CLAIMS:
            for line in text.splitlines():
                if claim in line:
                    self.assertTrue("상수" in line or "constants" in line, line)

    def test_no_laya_named_engine_while_no_model_is_loaded(self):
        for path in SCOPE:
            if path.suffix == ".py" and "finetune" not in path.parts and not path.samefile(THIS_FILE):
                self.assertNotIn("LayaHierarchicalEngine", path.read_text(encoding="utf-8"), path)

    def test_simulated_sleep_is_gone(self):
        jev = (ENGINE_DIR / "gateway" / "jev_client.py").read_text(encoding="utf-8")
        self.assertNotIn("time.sleep", jev)


if __name__ == "__main__":
    unittest.main()
