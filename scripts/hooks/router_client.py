#!/usr/bin/env python3
"""Helper for router-client.sh. Writes nothing to stdout; the wrapper prints "{}".

stdin JSON -> size/format checks -> masking -> POST /v1/observe on 127.0.0.1 with a
30 ms internal budget -> one telemetry line in $PI_ROUTER_HOME/telemetry/hook_events.jsonl.
Auto-disable (plan v0.3 §5.4 S6): if >20% of the last 50 calls failed or ran over budget,
write $PI_ROUTER_HOME/disabled and stop calling the daemon. Recovery: once the marker
is REENABLE_AFTER_SEC old, one call probes the daemon; an in-budget ok removes the marker
and resets the window, anything else re-arms the wait. Deleting the marker by hand still works.
"""

import signal


class Cancelled(Exception):
    pass


def _on_signal(signum, frame):
    raise Cancelled()


# Installed before the remaining imports so an early cancel is still handled.
signal.signal(signal.SIGTERM, _on_signal)
signal.signal(signal.SIGINT, _on_signal)

import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import socket  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
import uuid  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engines" / "hybrid_router"))
from ztc import telemetry  # noqa: E402
from ztc.masking import MAX_TEXT, mask_cwd, mask_text  # noqa: E402
import re  # noqa: E402
from ztc.paths import BIND_HOST, disabled_marker, private_dir, router_home, router_port  # noqa: E402

CLIENT_VERSION = "ztc-phase2-0.1"
BUDGET_MS = 30.0
MAX_STDIN = 64 * 1024
MAX_RESPONSE = 16 * 1024
WINDOW = 50
MIN_SAMPLES = 20
DISABLE_RATE = 0.2
EXIT_LINE = re.compile(r"^Exit code (\d{1,3})\s*$")
REENABLE_AFTER_SEC = 60.0


def _exit_code(resp):
    if isinstance(resp, dict):
        for key in ("exit_code", "exitCode", "returncode", "code"):
            if isinstance(resp.get(key), int):
                return resp[key]
    return None


_ARM_RE = re.compile(r"[A-Za-z0-9_-]{1,8}")


def ab_arm(payload: dict) -> str | None:
    """A/B arm label (AB_EVAL_ztc §6 U5): PI_AB_ARM, else a .pi-ab-arm file in the project
    dir (the same rule as the A/B prompt gate). Anything but a short label reads as unknown."""
    raw = os.environ.get("PI_AB_ARM")
    if raw is None:
        project = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ""
        try:
            raw = (Path(project) / ".pi-ab-arm").read_text(encoding="utf-8")[:16] if project else None
        except (OSError, ValueError):
            raw = None
    if raw is None:
        return None
    raw = raw.strip()
    return raw if _ARM_RE.fullmatch(raw) else "invalid"


def build_body(payload: dict) -> dict:
    event = str(payload.get("hook_event_name", ""))[:32]
    tool = str(payload.get("tool_name", ""))[:64]
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    command = tool_input.get("command") if isinstance(tool_input.get("command"), str) else ""
    program = command.split()[0] if command.strip() else tool
    body = {"event": event, "tool": tool, "program": mask_text(program, cwd=cwd, limit=60),
            "cwd": mask_cwd(cwd), "client_version": CLIENT_VERSION,
            "session": hashlib.sha256(str(payload.get("session_id", "")).encode()).hexdigest()[:12]}
    resp = payload.get("tool_response")
    code = _exit_code(resp)
    text = ""
    if isinstance(resp, dict):
        stderr = resp.get("stderr") if isinstance(resp.get("stderr"), str) else ""
        stdout = resp.get("stdout") if isinstance(resp.get("stdout"), str) else ""
        text = stderr or (stdout[-2000:] if code not in (None, 0) else "")
    elif isinstance(resp, str) and event == "PostToolUseFailure":
        text = resp
    if event == "PostToolUseFailure" and not text:
        # hooks reference: Bash failures arrive as `error` = "Exit code N\n<stdout+stderr>";
        # a bare message without that line means the shell could not start.
        error = payload.get("error") if isinstance(payload.get("error"), str) else ""
        first, _, rest = error.partition("\n")
        m = EXIT_LINE.match(first)
        if m:
            code = int(m.group(1)) if code is None else code
            text = rest
        else:
            text = error
        body["interrupt"] = payload.get("is_interrupt") is True
    body["exit_code"] = code
    # the failing line is usually at the end: mask a wide tail first, then keep its last MAX_TEXT chars
    body["text"] = mask_text(text[-4 * MAX_TEXT:], cwd=cwd, limit=4 * MAX_TEXT)[-MAX_TEXT:]
    body["response_keys"] = sorted(resp.keys())[:20] if isinstance(resp, dict) else None
    return body


def rpc(body: dict, deadline: float, request_id: str) -> tuple[str, float]:
    """POST /v1/observe with a hard deadline. Returns (outcome, rpc_ms)."""
    t0 = time.perf_counter()
    data = json.dumps(body, separators=(",", ":")).encode("utf-8")
    head = (
        f"POST /v1/observe HTTP/1.1\r\nHost: {BIND_HOST}\r\nContent-Type: application/json\r\n"
        f"Content-Length: {len(data)}\r\nX-Request-Id: {request_id}\r\nConnection: close\r\n\r\n"
    ).encode("ascii")

    def remaining() -> float:
        left = deadline - time.perf_counter()
        if left <= 0:
            raise socket.timeout()
        return left

    try:
        with socket.create_connection((BIND_HOST, router_port()), timeout=remaining()) as sock:
            sock.settimeout(remaining())
            sock.sendall(head + data)
            chunks = []
            size = 0
            while size < MAX_RESPONSE:
                sock.settimeout(remaining())
                chunk = sock.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if b"\r\n\r\n" in b"".join(chunks) and size >= 12:
                    status = b"".join(chunks).split(b" ", 2)
                    if len(status) >= 2 and status[1] != b"200":
                        break  # status known, body irrelevant
        status_line = b"".join(chunks).split(b"\r\n", 1)[0].split(b" ")
        code = status_line[1].decode("ascii", "replace") if len(status_line) > 1 else "none"
        outcome = "ok" if code == "200" else {"403": "denied", "413": "rejected_413", "503": "overloaded"}.get(code, f"http_{code}")
    except socket.timeout:
        outcome = "timeout"
    except ConnectionRefusedError:
        outcome = "absent"
    except PermissionError:
        outcome = "denied"
    except OSError:
        outcome = "error"
    return outcome, (time.perf_counter() - t0) * 1000


def update_window(outcome: str) -> str | None:
    """Rolling window of the last WINDOW outcomes; returns a reason if auto-disable fires."""
    state_path = router_home() / "client_window.json"
    try:
        window = json.loads(state_path.read_text()).get("w", "")
    except (OSError, ValueError, AttributeError):
        window = ""
    window = (window + ("o" if outcome == "ok" else "f"))[-WINDOW:]
    private_dir(router_home())
    tmp = state_path.with_name(f".client_window.{os.getpid()}")
    tmp.write_text(json.dumps({"w": window}))
    os.chmod(tmp, 0o600)
    os.replace(tmp, state_path)
    if len(window) >= MIN_SAMPLES and window.count("f") / len(window) > DISABLE_RATE:
        return f"{window.count('f')}/{len(window)} failed or over budget"
    return None


def marker_age_sec() -> float:
    try:
        ts = float(json.loads(disabled_marker().read_text()).get("ts", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        ts = 0.0
    return time.time() - ts


def write_marker(reason: str) -> None:
    private_dir(router_home())
    path = disabled_marker()
    tmp = path.with_name(f".disabled.{os.getpid()}")
    tmp.write_text(json.dumps({"reason": reason, "ts": time.time()}))
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def reset_window() -> None:
    try:
        (router_home() / "client_window.json").unlink()
    except OSError:
        pass


def main() -> None:
    t_start = time.perf_counter()
    record = {"client_version": CLIENT_VERSION, "request_id": uuid.uuid4().hex[:16]}
    outcome, rpc_ms, body, arm = "error", None, None, None
    try:
        raw = sys.stdin.buffer.read(MAX_STDIN + 1)
        if len(raw) > MAX_STDIN:
            outcome = "oversize"
        else:
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                payload = None
            if not isinstance(payload, dict):
                outcome = "bad_json"
            elif disabled_marker().exists():
                body = build_body(payload)
                arm = ab_arm(payload)
                if marker_age_sec() < REENABLE_AFTER_SEC:
                    outcome = "disabled"
                else:
                    outcome, rpc_ms = rpc(body, t_start + BUDGET_MS / 1000, record["request_id"])
                    if outcome == "ok":
                        disabled_marker().unlink(missing_ok=True)
                        reset_window()
                        record["auto_reenabled"] = True
                    else:
                        write_marker(f"re-enable probe {outcome}")
                        record["reenable_probe"] = outcome
                        outcome = "disabled"
            else:
                body = build_body(payload)
                arm = ab_arm(payload)
                outcome, rpc_ms = rpc(body, t_start + BUDGET_MS / 1000, record["request_id"])
    except Cancelled:
        outcome = "cancelled"
    except Exception:
        outcome = "error"
    record.update({
        "outcome": outcome,
        "event": body["event"] if body else None,
        "tool": body["tool"] if body else None,
        "program": body["program"] if body else None,
        "exit_code": body["exit_code"] if body else None,
        "response_keys": body["response_keys"] if body else None,
        "rpc_ms": round(rpc_ms, 3) if rpc_ms is not None else None,
        "client_ms": round((time.perf_counter() - t_start) * 1000, 3),
        "session": body["session"] if body else None,
        "arm": arm,
    })
    try:
        if outcome not in ("disabled", "oversize", "bad_json") and not record.get("auto_reenabled"):
            reason = update_window(outcome)
            if reason and not disabled_marker().exists():
                write_marker(reason)
                record["auto_disabled"] = reason
        telemetry.append("hook_events", record)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        pass
    sys.exit(0)
