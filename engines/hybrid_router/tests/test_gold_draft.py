#!/usr/bin/env python3
"""gold_draft.py (extract / label / status) on synthetic transcripts in a temp dir (no real data)."""

import contextlib
import io
import json
import os
import stat
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from _support import REPO_ROOT, IsolatedHomeTest, load_script_module
from ztc import gold

gd = load_script_module("gold_draft", "bench/gold_draft.py")
SECRET = "sk-ant-api03-" + "Q" * 40


def session_named(split: str, start: int = 0) -> str:
    """A synthetic session id whose hash lands in the wanted split."""
    import hashlib

    i = start
    while True:
        sid = f"sess-{split}-{i}"
        if gd.split_for(hashlib.sha256(sid.encode()).hexdigest()[:12]) == split:
            return sid
        i += 1


class Fixture:
    """Writes Claude Code-shaped JSONL: assistant tool_use + user tool_result pairs."""

    def __init__(self, root: Path):
        self.root = root
        self.n = 0

    def session(self, sid: str, failures: list, project: str = "proj-a", sidechain: bool = False,
                subdir: str | None = None, day: str = "2026-10-01") -> Path:
        cwd = f"/Users/someone/work/{project}"
        folder = self.root / f"-Users-someone-work-{project}"
        if subdir:
            folder = folder / sid / subdir
        folder.mkdir(parents=True, exist_ok=True)
        lines = []
        for f in failures:
            if isinstance(f, str):
                f = {"error": f}
            self.n += 1
            tid = f"toolu_{self.n:06d}"
            ts = f"{f.get('day', day)}T03:00:00.000Z"
            common = {"sessionId": sid, "cwd": cwd, "isSidechain": sidechain, "timestamp": ts}
            lines.append({**common, "type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": tid, "name": f.get("tool", "Bash"),
                 "input": {"command": f.get("command", "npm run build")}}]}})
            content = f["error"] if not f.get("blocks") else [{"type": "text", "text": f["error"]}]
            user = {**common, "type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": tid, "content": content, "is_error": f.get("is_error", True)}]}}
            if f.get("interrupted"):
                user["toolUseResult"] = {"interrupted": True}
            lines.append(user)
        path = folder / f"{sid}.jsonl"
        with open(path, "a", encoding="utf-8") as fh:
            for rec in lines:
                fh.write(json.dumps(rec) + "\n")
        return path


class GoldDraftBase(IsolatedHomeTest):
    def setUp(self):
        super().setUp()
        self.troot = Path(self._tmp.name) / "projects"
        self.fx = Fixture(self.troot)

    def extract(self, n=120, seed=7, since="2026-09-24", force=False):
        return gd.extract(self.troot, since, n, seed, force=force, out=io.StringIO())

    def candidates(self):
        return gd._read_jsonl(self.home / "gold" / "candidates.jsonl")


class TestExtract(GoldDraftBase):
    def test_inclusion_and_exclusions(self):
        sid = session_named("tune")
        self.fx.session(sid, [
            "Exit code 1\nSyntaxError: invalid syntax",
            {"error": "Exit code 2\nModuleNotFoundError: No module named 'zz'", "blocks": True},
            "Exit code 0\nall fine",
            "Permission to use Bash has been denied.",
            "The user doesn't want to proceed with this tool use.",
            "PreToolUse:Bash hook error: blocked",
            "Exit code 143\nCommand timed out after 2m 0.0s",
            {"error": "Exit code 1\nsomething", "interrupted": True},
            "Exit code 1\n   \n",
            {"error": "Exit code 1\nok but not error", "is_error": False},
            {"error": "Exit code 1\nold failure", "day": "2026-09-20"},
            {"error": "Exit code 1\nnot bash", "tool": "Read"},
            "Exit code 1\nPOISON row the validator rejects",
        ])
        real = gold.validate_row
        with mock.patch.object(gd.gold, "validate_row", lambda r: ["poison"] if "POISON" in r["text"] else real(r)):
            s = self.extract()
        self.assertEqual(s["selected"], 2)
        ex = s["excluded"]
        self.assertEqual(ex["not_exit_code"], 3)
        self.assertEqual(ex["exit_zero"], 1)
        self.assertEqual(ex["timeout"], 2)
        self.assertEqual(ex["empty_body"], 1)
        self.assertEqual(ex["before_since"], 1)
        self.assertEqual(ex["invalid_after_mask"], 1)
        self.assertEqual(s["bash_failures_seen"], 11)  # is_error=false and non-Bash are never seen

    def test_masking_applied_and_rows_validate(self):
        self.fx.session(session_named("tune"), [{
            "error": f"Exit code 1\nTypeError in /Users/someone/work/proj-a/src/app.py\nkey {SECRET}",
            "command": "/Users/someone/work/proj-a/.venv/bin/python -m app"}])
        self.extract()
        (c,) = self.candidates()
        self.assertNotIn("/Users/", c["text"])
        self.assertNotIn(SECRET, c["text"])
        self.assertIn("<SECRET>", c["text"])
        self.assertIn("src/app.py", c["text"])  # cwd-relative, as the hook client does
        self.assertNotIn("/Users/", c["program"])
        self.assertEqual(c["exit_code"], 1)
        self.assertEqual(c["event"], "PostToolUseFailure")
        self.assertEqual(c["group"]["project"], "proj-a")
        self.assertEqual(len(c["group"]["session"]), 12)
        row = {**c, "label": "other", "label_source": "user", "created_at": gd._now()}
        self.assertEqual(gold.validate_row(row), [])

    def test_session_cap(self):
        self.fx.session(session_named("tune"), [f"Exit code 1\ndistinct failure kind {chr(97 + i)}x" for i in range(7)])
        self.assertEqual(self.extract()["selected"], gd.SESSION_CAP)

    def test_signature_cap(self):
        for i in range(4):
            self.fx.session(session_named("tune", i * 1000), ["Exit code 1\nSyntaxError: same thing"])
        self.extract()
        sigs = [c["group"]["signature"] for c in self.candidates()]
        self.assertEqual(len(sigs), gd.SIGNATURE_CAP)
        self.assertEqual(len(set(sigs)), 1)

    def test_project_share_cap(self):
        for i in range(6):
            self.fx.session(session_named("tune", i * 1000), [f"Exit code 1\nbig project error {chr(97 + i)}{chr(97 + j)}"
                                                             for j in range(3)], project="big")
        for i in range(2):
            self.fx.session(session_named("tune", 50000 + i * 1000), [f"Exit code 1\nsmall error {chr(97 + i)}"],
                            project="small")
        s = self.extract(n=10)
        projects = [c["group"]["project"] for c in self.candidates()]
        self.assertLessEqual(projects.count("big"), 5)
        self.assertEqual(projects.count("small"), 2)
        self.assertEqual(s["selected"], 7)

    def test_subagent_flag(self):
        self.fx.session(session_named("tune"), ["Exit code 1\nSyntaxError: sub"], sidechain=True, subdir="subagents")
        self.extract()
        (c,) = self.candidates()
        self.assertTrue(c["source"]["subagent"])

    def test_deterministic_split_and_holdout_signature_drop(self):
        tune_sid, hold_sid = session_named("tune"), session_named("holdout")
        self.fx.session(tune_sid, ["Exit code 1\nSyntaxError: shared", "Exit code 1\ntune only"])
        self.fx.session(hold_sid, ["Exit code 1\nSyntaxError: shared", "Exit code 1\nholdout only"], project="proj-b")
        s = self.extract(seed=1)
        first = self.candidates()
        self.assertEqual(s["excluded"]["holdout_signature_in_tune"], 1)
        self.assertEqual(s["by_split"], {"tune": 2, "holdout": 1})
        hold_sigs = {c["group"]["signature"] for c in first if c["split"] == "holdout"}
        tune_sigs = {c["group"]["signature"] for c in first if c["split"] == "tune"}
        self.assertFalse(hold_sigs & tune_sigs)
        # same session -> same split regardless of seed; same seed -> same rows in the same order
        self.extract(seed=1, force=True)
        self.assertEqual([c["id"] for c in self.candidates()], [c["id"] for c in first])
        self.extract(seed=99, force=True)
        self.assertEqual({c["id"]: c["split"] for c in self.candidates()}, {c["id"]: c["split"] for c in first})

    def test_draft_only_on_tune(self):
        self.fx.session(session_named("tune"), ["Exit code 1\nModuleNotFoundError: x", "Exit code 1\nweird"])
        self.fx.session(session_named("holdout"), ["Exit code 1\nSyntaxError: y"], project="proj-b")
        self.extract()
        for c in self.candidates():
            if c["split"] == "tune":
                self.assertIn("draft_label", c)
            else:
                self.assertNotIn("draft_label", c)
        drafts = {c["draft_label"] for c in self.candidates() if c["split"] == "tune"}
        self.assertEqual(drafts, {"dependency_missing", None})

    def test_refuses_overwrite_without_force(self):
        self.fx.session(session_named("tune"), ["Exit code 1\nSyntaxError: a"])
        self.extract()
        with self.assertRaises(FileExistsError):
            self.extract()

    def test_file_modes(self):
        self.fx.session(session_named("tune"), ["Exit code 1\nSyntaxError: a"])
        self.extract()
        gd.label(inp=io.StringIO("1\n"), out=io.StringIO())
        g = self.home / "gold"
        self.assertEqual(stat.S_IMODE(g.stat().st_mode), 0o700)
        for name in ("candidates.jsonl", "v1.jsonl", "extract_meta.json"):
            self.assertEqual(stat.S_IMODE((g / name).stat().st_mode), 0o600, name)


class TestRefusal(IsolatedHomeTest):
    def test_inside_this_repo(self):
        target = REPO_ROOT / "ztc-gold-should-not-exist"
        os.environ["PI_ROUTER_HOME"] = str(target)
        with self.assertRaises(PermissionError):
            gd.gold_dir()
        self.assertFalse(target.exists())
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(gd.main(["status"]), 2)
        self.assertIn("refused", err.getvalue())
        self.assertFalse(target.exists())

    def test_inside_other_git_work_tree(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".git").mkdir()
            os.environ["PI_ROUTER_HOME"] = str(Path(d) / "nested" / "home")
            with self.assertRaises(PermissionError):
                gd.gold_dir()
            self.assertFalse((Path(d) / "nested").exists())


class TestLabel(GoldDraftBase):
    def setUp(self):
        super().setUp()
        self.fx.session(session_named("tune"), ["Exit code 1\nModuleNotFoundError: t1", "Exit code 1\nSyntaxError: t2",
                                                "Exit code 1\nweird t3"])
        self.fx.session(session_named("holdout"), ["Exit code 1\nEACCES h1", "Exit code 1\nmystery h2"], project="proj-b")
        self.extract()

    def run_label(self, keys: str, **kw) -> tuple[int, str]:
        out = io.StringIO()
        n = gd.label(inp=io.StringIO(keys), out=out, **kw)
        return n, out.getvalue()

    def v1(self):
        return gd._read_jsonl(self.home / "gold" / "v1.jsonl")

    def test_holdout_blind_tune_draft(self):
        _, hold = self.run_label("s\ns\n", split="holdout")
        self.assertNotIn("draft", hold)
        self.assertIn("split=holdout", hold)
        _, tune = self.run_label("q\n", split="tune")
        self.assertIn("draft (L0 regex):", tune)

    def test_append_resume_skip_quit(self):
        n, _ = self.run_label("1\ns\nq\n", split="tune")
        self.assertEqual(n, 1)
        rows = self.v1()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["label_source"], "user")
        self.assertEqual(rows[0]["label"], "syntax_compile")
        self.assertIn("created_at", rows[0])
        self.assertNotIn("draft_label", rows[0])
        first_id = rows[0]["id"]
        # resume: the labelled candidate is not offered again; skipped ones are
        n, out = self.run_label("x\n5\n6\n2\n4\n")
        self.assertIn("keys: 1-6, s, q", out)
        self.assertEqual(n, 4)
        rows = self.v1()
        self.assertEqual(len(rows), 5)
        self.assertEqual(len({r["id"] for r in rows}), 5)
        self.assertEqual(sum(r["id"] == first_id for r in rows), 1)
        self.assertEqual(gold.validate(gold.load(self.home / "gold" / "v1.jsonl")), [])
        n, out = self.run_label("1\n")
        self.assertEqual(n, 0)

    def test_limit_and_eof(self):
        n, out = self.run_label("1\n1\n1\n", limit=2)
        self.assertEqual(n, 2)
        n, out = self.run_label("")
        self.assertEqual(n, 0)
        self.assertIn("end of input", out)

    def test_status_counts_only(self):
        self.run_label("1\n2\n", split="holdout")
        out = io.StringIO()
        report = gd.status(out=out)
        self.assertEqual(report["candidates"], {"tune": 3, "holdout": 2})
        self.assertEqual(report["labelled"], {"tune": 0, "holdout": 2})
        self.assertEqual(report["remaining"], {"tune": 3, "holdout": 0})
        self.assertEqual(sum(report["by_day"].values()), 2)
        self.assertEqual(report["validate_errors"], 0)
        text = out.getvalue()
        for body in ("EACCES", "mystery", "ModuleNotFoundError", "weird"):
            self.assertNotIn(body, text)


if __name__ == "__main__":
    unittest.main()
