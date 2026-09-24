#!/usr/bin/env python3
"""Client-side masking (HOOK_CONTRACT_ztc.md §3): secrets, paths, cwd, stderr, truncation."""

import os
import unittest

import _support  # noqa: F401  (sys.path)
from ztc.masking import MAX_TEXT, contains_unmasked_secret, mask_cwd, mask_text

HOME = os.path.expanduser("~")
HEX64 = "3f" * 32


class TestMasking(unittest.TestCase):
    def assert_masked(self, raw, secret, **kw):
        out = mask_text(raw, **kw)
        self.assertNotIn(secret, out)
        self.assertEqual(mask_text(out, **kw), out, "masking must be idempotent")
        return out

    def test_anthropic_and_openai_keys(self):
        for key in ("sk-ant-api03-" + "x" * 40, "sk-" + "A1b2" * 10):
            self.assertIn("<SECRET>", self.assert_masked(f"curl -H 'x-api-key: {key}' api", key))

    def test_github_tokens(self):
        for key in ("ghp_" + "a" * 36, "gho_" + "b" * 36, "github_pat_" + "c" * 60):
            self.assert_masked(f"git push https://{key}@github.com/o/r", key)

    def test_bearer_header(self):
        tok = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        out = self.assert_masked(f"Authorization: Bearer {tok}", tok)
        self.assertIn("<SECRET>", out)
        self.assertIn("<SECRET>", mask_text("curl -H 'Authorization: Bearer abcdefghijklmnop1234'"))

    def test_aws_and_slack(self):
        self.assert_masked("aws AKIAIOSFODNN7EXAMPLE configure", "AKIAIOSFODNN7EXAMPLE")
        slack = "xox" + "b-1234567890-abcdefghij"  # built at runtime so secretlint does not flag the fixture
        self.assert_masked(slack, slack)

    def test_hex64(self):
        out = self.assert_masked(f"approval digest {HEX64} ok", HEX64)
        self.assertIn("<HEX64>", out)
        self.assertIn("a1b2c3d", mask_text("commit a1b2c3d"))  # short git SHAs are not secrets

    def test_env_style_assignments(self):
        for raw, secret in (
            ("OPENAI_API_KEY=abc123def456 python run.py", "abc123def456"),
            ("export DB_PASSWORD='hunter2 hunter2'", "hunter2"),
            ('GITHUB_TOKEN: "t0ps3cr3t"', "t0ps3cr3t"),
        ):
            self.assert_masked(raw, secret)

    def test_url_credentials(self):
        url = "postgres" + "://admin:pa55w0rd@db.local:5432/x"  # built at runtime (secretlint fixture)
        self.assert_masked(url, "pa55w0rd")

    def test_private_key_block(self):
        raw = "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXk\n-----END OPENSSH PRIVATE KEY-----"
        self.assert_masked(raw, "b3BlbnNzaC1rZXk")

    def test_paths_relative_home_and_abs(self):
        cwd = "/srv/work/repo"
        out = mask_text(f"error in {cwd}/src/a.ts:12:3 and {HOME}/notes.txt and /etc/hosts", cwd=cwd)
        self.assertIn("src/a.ts:12:3", out)
        self.assertIn("~/notes.txt", out)
        self.assertIn("<ABS>/hosts", out)
        self.assertNotIn("/srv/work", out)
        self.assertNotIn(HOME, out)

    def test_windows_paths(self):
        out = mask_text(r"cannot open C:\Users\dudal\.pi-secrets\token.txt")
        self.assertNotIn("dudal", out)
        self.assertIn("<ABS>/token.txt", out.replace("\\", "/"))

    def test_cwd_and_filename_and_stderr(self):
        self.assertNotIn(HOME, mask_cwd(f"{HOME}/projects/sample-repo"))
        self.assertEqual(mask_cwd(f"{HOME}/projects/sample-repo"), "~/projects/sample-repo")
        stderr = f"Traceback:\n  File \"{HOME}/proj/app.py\", line 3\nKeyError: 'API_KEY=zzzsecretzzz'"
        out = mask_text(stderr)
        self.assertNotIn("zzzsecretzzz", out)
        self.assertIn("~/proj/app.py", out)

    def test_truncation(self):
        self.assertEqual(len(mask_text("x" * 5000)), MAX_TEXT)
        self.assertEqual(MAX_TEXT, 500)

    def test_detector_for_gold_validator(self):
        self.assertTrue(contains_unmasked_secret("token ghp_" + "z" * 36))
        self.assertFalse(contains_unmasked_secret(mask_text("token ghp_" + "z" * 36)))


if __name__ == "__main__":
    unittest.main()
