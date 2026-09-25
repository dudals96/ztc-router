#!/usr/bin/env python3
"""Health check for the ZTC router daemon and the evaluation gate (launchd, every 5 min).

Run by LaunchAgent com.pi.router-healthcheck (config/launchd/com.pi.router-healthcheck.plist.template).
Fixes only what is safe to fix without a person:
  1. the daemon job is not loaded in launchd but its plist is installed -> bootstrap it;
  2. GET /health is not "ready" within 2 s -> `launchctl kickstart -k`, then poll up to 15 s.
Reports without fixing:
  - the client auto-disable marker $PI_ROUTER_HOME/disabled (recovery is manual or the
    client's own probe, docs/harness/HOOK_CONTRACT_ztc.md section 6);
  - the evaluation gate: script not executable, repository kill switch off, paused by the
    user, hook entry missing from ~/.claude/settings.json or ~/.codex/config.toml.
Writes one line to $PI_ROUTER_HOME/telemetry/healthcheck.jsonl and the latest result to
$PI_ROUTER_HOME/health_status.json. A macOS notification is shown only when the overall
status changes or a restart brought the daemon back, so a steady state (good or bad) stays quiet.

`--dry-run` checks and prints the result without fixing, notifying or writing state.
Environment overrides for tests: PI_LAUNCHCTL (launchctl command), PI_NOTIFY_CMD
(notification command, gets title and message as arguments), PI_HC_WAIT_SEC.
"""

import json
import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "engines" / "hybrid_router"))
from ztc import telemetry  # noqa: E402
from ztc.paths import BIND_HOST, disabled_marker, router_home, router_port  # noqa: E402

DAEMON_LABEL = "com.pi.router-daemon"
HEALTH_TIMEOUT_SEC = 2.0
GATE_SCRIPT = REPO_ROOT / "scripts" / "hooks" / "ab-prompt-gate.sh"
GATE_CONFIG = REPO_ROOT / "config" / "ab_gate.json"
GATE_MARK = "ab-prompt-gate.sh"
STATUS_FILE = "health_status.json"


def launchctl(*args: str) -> subprocess.CompletedProcess:
    cmd = shlex.split(os.environ.get("PI_LAUNCHCTL", "/bin/launchctl"))
    return subprocess.run([*cmd, *args], capture_output=True, text=True, timeout=20)


def domain() -> str:
    return f"gui/{os.getuid()}"


def daemon_plist() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{DAEMON_LABEL}.plist"


def health() -> str:
    """"ready", "not_ready" (answered, but not ready) or "down" (no answer)."""
    url = f"http://{BIND_HOST}:{router_port()}/health"
    try:
        with urllib.request.urlopen(url, timeout=HEALTH_TIMEOUT_SEC) as resp:
            body = json.loads(resp.read(16 * 1024).decode("utf-8"))
            return "ready" if resp.status == 200 and body.get("status") == "ready" else "not_ready"
    except urllib.error.HTTPError:
        return "not_ready"
    except (OSError, ValueError, AttributeError):
        return "down"


def wait_ready(limit_sec: float) -> str:
    deadline = time.monotonic() + limit_sec
    state = health()
    while state != "ready" and time.monotonic() < deadline:
        time.sleep(1)
        state = health()
    return state


def gate_checks() -> list[str]:
    problems = []
    if not os.access(GATE_SCRIPT, os.X_OK):
        problems.append("gate_script_not_executable")
    for name, path in (("claude", Path.home() / ".claude" / "settings.json"),
                       ("codex", Path.home() / ".codex" / "config.toml")):
        try:
            if GATE_MARK not in path.read_text(encoding="utf-8"):
                problems.append(f"gate_hook_missing_{name}")
        except OSError:
            problems.append(f"gate_hook_missing_{name}")
    return problems


def gate_notes() -> list[str]:
    notes = []
    try:
        if json.loads(GATE_CONFIG.read_text(encoding="utf-8")).get("enabled", True) is False:
            notes.append("gate_kill_switch_off")
    except (OSError, ValueError, AttributeError):
        pass
    try:
        if json.loads((router_home() / "ab_gate_state.json").read_text(encoding="utf-8")).get("paused") is True:
            notes.append("gate_paused_by_user")
    except (OSError, ValueError, AttributeError):
        pass
    if disabled_marker().exists():
        notes.append("client_auto_disabled")
    return notes


def check(fix: bool, wait_sec: float) -> dict:
    actions, problems = [], []
    loaded = launchctl("print", f"{domain()}/{DAEMON_LABEL}").returncode == 0
    state = health()
    if state != "ready" and fix:
        if not loaded and daemon_plist().exists():
            r = launchctl("bootstrap", domain(), str(daemon_plist()))
            actions.append("bootstrap" if r.returncode == 0 else "bootstrap_failed")
            loaded = r.returncode == 0
        elif loaded:
            r = launchctl("kickstart", "-k", f"{domain()}/{DAEMON_LABEL}")
            actions.append("kickstart" if r.returncode == 0 else "kickstart_failed")
        state = wait_ready(wait_sec) if actions else state
    if not loaded:
        problems.append("daemon_not_loaded")
    if state != "ready":
        problems.append(f"daemon_{state}")
    problems += gate_checks()
    status = "problem" if problems else ("recovered" if actions else "ok")
    return {"status": status, "daemon": state, "loaded": loaded, "actions": actions,
            "problems": problems, "notes": gate_notes()}


def notify(title: str, message: str) -> None:
    override = os.environ.get("PI_NOTIFY_CMD")
    try:
        if override:
            subprocess.run([*shlex.split(override), title, message], capture_output=True, timeout=10)
        else:
            script = f"display notification {json.dumps(message)} with title {json.dumps(title)}"
            subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


def write_status(result: dict) -> None:
    home = router_home()
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = home / f".{STATUS_FILE}.{os.getpid()}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        os.write(fd, json.dumps({"ts": round(time.time(), 3), **result}, ensure_ascii=False).encode())
    finally:
        os.close(fd)
    os.replace(tmp, home / STATUS_FILE)


def previous_status() -> str | None:
    try:
        return json.loads((router_home() / STATUS_FILE).read_text(encoding="utf-8")).get("status")
    except (OSError, ValueError, AttributeError):
        return None


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    result = check(fix=not dry, wait_sec=float(os.environ.get("PI_HC_WAIT_SEC", "15")))
    if dry:
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] != "problem" else 1
    before = previous_status()
    try:
        telemetry.append("healthcheck", result)
    except OSError:
        pass
    write_status(result)
    now_ok = result["status"] != "problem"
    was_ok = before != "problem" if before is not None else True
    # Quiet steady states: notify on a change of status, or when a restart fixed it.
    if was_ok != now_ok or (now_ok and result["actions"]):
        if not now_ok:
            notify("ZTC 라우터 점검 필요", ", ".join(result["problems"]))
        elif result["actions"]:
            notify("ZTC 라우터 복구됨", ", ".join(result["actions"]))
        else:
            notify("ZTC 라우터 정상", "상태가 정상으로 돌아왔습니다")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if now_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
