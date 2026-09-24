"""Client-side minimisation of hook payloads before they leave the hook process.

Rules (HOOK_CONTRACT_ztc.md §3): secrets -> <SECRET>/<HEX64>, absolute paths ->
repo-relative / ~ / <ABS>/basename, text truncated to MAX_TEXT chars.
Content that already sits in the harness transcript cannot be masked retroactively.
"""

import os
import re

MAX_TEXT = 500

_SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)", re.S),
    re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
]
_BEARER = re.compile(r"(?i)\b(bearer|token|basic)\s+[A-Za-z0-9._~+/=-]{12,}")
_URL_CREDS = re.compile(r"(\w+://)[^/\s:@]+:[^/\s@]+@")
_ENV_ASSIGN = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|PASS|PWD|CREDENTIAL|AUTH)[A-Z0-9_]*)"
    r"(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s\"']+)"
)
_HEX64 = re.compile(r"\b[0-9a-fA-F]{64}\b")
_POSIX_ABS = re.compile(r"(?<![\w.~>])/(?:[^\s'\"`:;,()<>|]+)")
_WIN_ABS = re.compile(r"\b[A-Za-z]:[\\/][^\s'\"`;,()<>|]*")


def _mask_secrets(text: str) -> str:
    for pat in _SECRET_PATTERNS:
        text = pat.sub("<SECRET>", text)
    text = _BEARER.sub(lambda m: f"{m.group(1)} <SECRET>", text)
    text = _URL_CREDS.sub(r"\1<SECRET>@", text)
    text = _ENV_ASSIGN.sub(lambda m: f"{m.group(1)}{m.group(2)}<SECRET>", text)
    return _HEX64.sub("<HEX64>", text)


def _relativise(path: str, roots: list[tuple[str, str]]) -> str:
    for prefix, label in roots:
        if prefix and (path == prefix or path.startswith(prefix.rstrip("/\\") + ("/" if "/" in prefix else "\\"))):
            rest = path[len(prefix):].lstrip("/\\")
            if not rest:
                return label or "."
            return f"{label}/{rest}" if label else rest
    base = re.split(r"[\\/]", path.rstrip("/\\"))[-1]
    return f"<ABS>/{base}" if base else "<ABS>"


def _mask_paths(text: str, cwd: str | None) -> str:
    roots = []
    if cwd:
        roots.append((os.path.normpath(cwd), ""))
    home = os.path.expanduser("~")
    if home and home != "/":
        roots.append((home, "~"))
    text = _WIN_ABS.sub(lambda m: _relativise(m.group(0), roots), text)
    return _POSIX_ABS.sub(lambda m: _relativise(m.group(0), roots), text)


def mask_text(text, cwd: str | None = None, limit: int = MAX_TEXT) -> str:
    """Mask secrets and absolute paths, then truncate. Idempotent."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    text = _mask_paths(_mask_secrets(text), cwd)
    return text[:limit]


def mask_cwd(cwd: str | None) -> str:
    """cwd itself is reduced to ~-relative form or its basename."""
    if not cwd:
        return ""
    return mask_text(cwd, cwd=None, limit=200)


def contains_unmasked_secret(text: str) -> bool:
    """True if a secret pattern survives (used by the gold validator)."""
    return _mask_secrets(text) != text
