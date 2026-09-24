#!/usr/bin/env python3
"""L0: regexes from config are used, normalisation (10 cases incl. over-merge), ledger rules, hit latency."""

import json
import shutil
import time
import unittest

from _support import IsolatedHomeTest, REPO_ROOT
from ztc import l0
from ztc.paths import ledger_path
from ztc.telemetry import percentile

RULES = l0.load_rules()
SIGS = l0.compile_signatures(RULES)
ATTR = {"head": "test", "worktree_sha256": "0" * 64}


class TestRegexV0(unittest.TestCase):
    def test_patterns_come_from_config(self):
        classes = [cls for cls, _ in SIGS]
        self.assertEqual(classes, list(RULES["rules"]["error_loop_short_circuit"]["error_signatures"]))

    def test_each_class_matches(self):
        cases = {
            "syntax_compile": "src/a.ts(3,1): error TS2339: Property 'x' does not exist",
            "dependency_missing": "Error: Cannot find module 'left-pad'",
            "lint_formatting": "Biome format check failed for 3 files",
            "permission_auth": "fatal: could not read Username: Permission denied (publickey)",
        }
        for cls, text in cases.items():
            self.assertEqual(l0.classify_regex(text, SIGS), cls)
        self.assertIsNone(l0.classify_regex("all good", SIGS))


class TestNormalisation(unittest.TestCase):
    def sig(self, text, program="npm"):
        return l0.signature(program, text, SIGS)

    def test_01_paths_collapse(self):
        self.assertEqual(self.sig("SyntaxError in /a/b/c.py"), self.sig("SyntaxError in /x/y/z.py"))

    def test_02_line_and_column_collapse(self):
        self.assertEqual(self.sig("a.ts:12:4 error TS2339"), self.sig("a.ts:99:1 error TS2339"))

    def test_03_python_line_word(self):
        self.assertEqual(self.sig('File "x.py", line 10\nSyntaxError: bad'), self.sig('File "x.py", line 77\nSyntaxError: bad'))

    def test_04_hashes_collapse(self):
        self.assertEqual(self.sig("TypeError at 0xdeadbeef01"), self.sig("TypeError at 0xabcdef9876"))

    def test_05_counts_collapse(self):
        self.assertEqual(self.sig("Biome format check failed for 3 files"), self.sig("Biome format check failed for 41 files"))

    def test_06_ts_codes_stay_distinct(self):
        self.assertNotEqual(self.sig("error TS2339: x"), self.sig("error TS2345: x"))

    def test_07_module_names_stay_distinct(self):
        self.assertNotEqual(self.sig("ModuleNotFoundError: No module named 'foo'"),
                            self.sig("ModuleNotFoundError: No module named 'bar'"))

    def test_08_program_is_part_of_signature(self):
        self.assertNotEqual(self.sig("SyntaxError: x", "node"), self.sig("SyntaxError: x", "python3"))

    def test_09_whitespace_and_noise_lines(self):
        noisy = "building...\n\n  SyntaxError:   unexpected   token\n done in 3s"
        self.assertEqual(self.sig(noisy), self.sig("SyntaxError: unexpected token"))

    def test_10_error_class_does_not_overmerge(self):
        self.assertNotEqual(self.sig("Permission denied (publickey)"), self.sig("Cannot find module 'x'"))

    def test_11_no_error_line_uses_last_line(self):
        self.assertEqual(l0.signature_lines("first\nsecond line 3", SIGS), ["second line <N>"])


class TestLedger(IsolatedHomeTest):
    def setUp(self):
        super().setUp()
        self.ledger = l0.Ledger(ledger_path(), "policy-a")

    def tearDown(self):
        self.ledger.close()
        super().tearDown()

    def test_wal_and_file_mode(self):
        mode = self.ledger._conn.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(mode, "wal")
        self.assertEqual(ledger_path().stat().st_mode & 0o777, 0o600)
        self.assertEqual(ledger_path().parent.stat().st_mode & 0o777, 0o700)

    def test_missing_parents_are_private_too(self):
        from ztc.paths import private_dir

        deep = self.home.parent / "a" / "b" / "c"
        private_dir(deep)
        for d in (deep, deep.parent, deep.parent.parent):
            self.assertEqual(d.stat().st_mode & 0o777, 0o700, d)

    def test_candidate_row_has_provenance(self):
        self.ledger.put_candidate("s1", "syntax_compile", "heuristic", "keyword-heuristic", "c1", ATTR)
        row = self.ledger._conn.execute(
            "SELECT state, source_layer, source_model, policy_version, client_version, head, created_at, expires_at, revoked_at"
            " FROM signatures WHERE signature='s1'"
        ).fetchone()
        self.assertEqual(row[:6], ("candidate", "heuristic", "keyword-heuristic", "policy-a", "c1", "test"))
        self.assertGreater(row[7], row[6])
        self.assertIsNone(row[8])

    def test_no_automatic_promotion(self):
        for _ in range(10):
            self.ledger.put_candidate("s1", "syntax_compile", "heuristic", "m", "c", ATTR)
            self.assertEqual(self.ledger.lookup("s1")["state"], "candidate")
        self.assertFalse(any(hasattr(self.ledger, n) for n in ("promote", "verify", "mark_verified")))

    def test_candidate_never_overwrites_verified(self):
        self.ledger.put_candidate("s1", "syntax_compile", "heuristic", "m", "c", ATTR)
        self.ledger._conn.execute("UPDATE signatures SET state='verified' WHERE signature='s1'")  # manual, out of band
        self.ledger.put_candidate("s1", "lint_formatting", "heuristic", "m", "c", ATTR)
        self.assertEqual(self.ledger.lookup("s1"), {"signature": "s1", "error_class": "syntax_compile",
                                                    "state": "verified", "source_layer": "heuristic"})

    def test_expiry_revocation_and_policy_change(self):
        self.ledger.put_candidate("old", "syntax_compile", "heuristic", "m", "c", ATTR, ttl=-1)
        self.assertIsNone(self.ledger.lookup("old"))
        self.ledger.put_candidate("rev", "syntax_compile", "heuristic", "m", "c", ATTR)
        self.ledger.revoke("rev")
        self.assertIsNone(self.ledger.lookup("rev"))
        self.ledger.put_candidate("pol", "syntax_compile", "heuristic", "m", "c", ATTR)
        other = l0.Ledger(ledger_path(), "policy-b")
        try:
            self.assertIsNone(other.lookup("pol"))
        finally:
            other.close()

    def test_policy_version_tracks_rule_file(self):
        tmp = self.home.parent / "rules.json"
        shutil.copy(REPO_ROOT / "config" / "anti_pattern_rules.json", tmp)
        before = l0.policy_version(tmp)
        data = json.loads(tmp.read_text())
        data["version"] = "9.9.9"
        tmp.write_text(json.dumps(data))
        self.assertNotEqual(before, l0.policy_version(tmp))

    def test_reobservation_hit_p50_under_1ms(self):
        sigs = [f"sig{i}" for i in range(200)]
        for s in sigs:
            self.ledger.put_candidate(s, "syntax_compile", "heuristic", "m", "c", ATTR)
        samples = []
        for _ in range(5):
            for s in sigs:
                t0 = time.perf_counter()
                self.assertIsNotNone(self.ledger.lookup(s))
                samples.append((time.perf_counter() - t0) * 1000)
        self.assertLess(percentile(samples, 50), 1.0)

    def test_attribution_has_head_and_digest(self):
        attr = l0.attribution()
        self.assertEqual(len(attr["worktree_sha256"]), 64)
        self.assertTrue(attr["head"])


if __name__ == "__main__":
    unittest.main()
