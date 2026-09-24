"""Repository-relative and runtime paths.

Raw telemetry, gold and the signature ledger live outside the repository under
PI_ROUTER_HOME (default ~/.pi-router). Only daily aggregates go to learning/metrics/.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config"
METRICS_DIR = REPO_ROOT / "learning" / "metrics"

DEFAULT_PORT = 9876
BIND_HOST = "127.0.0.1"  # never configurable: no external bind


def router_home() -> Path:
    raw = os.environ.get("PI_ROUTER_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".pi-router"


def router_port() -> int:
    raw = os.environ.get("PI_ROUTER_PORT", "")
    try:
        port = int(raw)
    except ValueError:
        return DEFAULT_PORT
    return port if 0 < port < 65536 else DEFAULT_PORT


def ensure_outside_repo(path: Path) -> Path:
    """Raw data must never land in the git-tracked tree (grafted from track B)."""
    resolved = Path(path).expanduser().resolve()
    root = REPO_ROOT.resolve()
    if resolved == root or root in resolved.parents:
        raise PermissionError(f"PI_ROUTER_HOME must resolve outside the repository: {root}")
    return resolved


def private_dir(path: Path) -> Path:
    """Create path and any missing parents with 0700 and return it.

    Only directories created here are chmod-ed; an existing directory (for example a
    mistaken PI_ROUTER_HOME=$HOME) keeps its permissions. Refuses paths inside the repo.
    """
    ensure_outside_repo(path)
    missing = []
    probe = path
    while not probe.exists():
        missing.append(probe)
        probe = probe.parent
    for d in reversed(missing):
        d.mkdir(mode=0o700, exist_ok=True)
        os.chmod(d, 0o700)
    return path


def telemetry_dir() -> Path:
    return private_dir(router_home() / "telemetry")


def ledger_path() -> Path:
    return private_dir(router_home()) / "signatures.sqlite"


def disabled_marker() -> Path:
    return router_home() / "disabled"
