#!/usr/bin/env python3
"""Gold validator and aggregator on synthetic fixture rows (not gold data)."""

import unittest

import _support  # noqa: F401
from ztc import gold


def row(i, label="syntax_compile", split="holdout", session="s1", signature=None, text="error TS2339: x", source="user"):
    return {
        "id": f"g-{i:08x}", "schema": gold.SCHEMA, "event": "PostToolUse", "tool": "Bash", "program": "npm",
        "group": {"session": session, "signature": signature or f"sig{i}", "project": "pi"},
        "text": text, "exit_code": 1, "label": label, "label_source": source, "split": split,
        "created_at": "2026-09-24T19:00:00+09:00", "attribution": {"head": "abc", "worktree_sha256": "0" * 64},
    }


class TestGoldValidator(unittest.TestCase):
    def test_valid_row(self):
        self.assertEqual(gold.validate_row(row(1)), [])

    def test_rejects_unmasked_secret_and_path(self):
        self.assertIn("text: unmasked secret", gold.validate_row(row(1, text="token ghp_" + "a" * 36)))
        errs = gold.validate_row(row(1, text="error in /Users/someone/app.py"))
        self.assertTrue(any("not masked" in e for e in errs))

    def test_rejects_long_text_and_bad_enums(self):
        errs = gold.validate_row({**row(1, text="x" * 501), "label": "nope", "split": "train"})
        self.assertTrue({"label", "split", "text: over 500 chars"} <= set(errs))

    def test_session_must_stay_in_one_split(self):
        errs = gold.validate([row(1, split="tune"), row(2, split="holdout")])
        self.assertTrue(any("spans both splits" in e for e in errs))

    def test_signature_leak_across_splits(self):
        errs = gold.validate([row(1, split="tune", session="a", signature="S"), row(2, split="holdout", session="b", signature="S")])
        self.assertTrue(any("leaks across splits" in e for e in errs))


class TestGoldAggregate(unittest.TestCase):
    def test_empty_is_honest(self):
        stats = gold.aggregate([])
        self.assertIsNone(stats["k3_shadow_fit_rate"]["value"])
        self.assertIn("기준선 미확보", stats["k3_shadow_fit_rate"]["status"])

    def test_fit_rate_ci_and_discordance(self):
        rows = [row(i) for i in range(18)] + [row(18, label="permission_auth", text="EACCES: denied"),
                                               row(19, label="dependency_missing", text="weird failure"),
                                               row(20, source="agent-draft"), row(21, label="abstain")]
        stats = gold.aggregate(rows, heuristic=lambda text: "syntax_compile")
        k3 = stats["k3_shadow_fit_rate"]
        self.assertEqual(stats["holdout_eval_n"], 20)  # agent-draft and abstain labels excluded
        self.assertEqual(k3["value"], 0.95)
        self.assertEqual(k3["l0_abstained"], 1)
        lo, hi = k3["wilson95"]
        self.assertLess(lo, 0.95)
        self.assertLess(0.95, hi)
        self.assertEqual(stats["paired_vs_heuristic"]["l0_only_correct_b"], 1)
        self.assertFalse(stats["holdout_by_class"]["permission_auth"]["sufficient"])
        self.assertEqual(len(stats["holdout_seal_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
