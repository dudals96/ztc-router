#!/usr/bin/env python3
"""
jev_client.py
Jev decision API client with a circuit breaker.

The HTTP call happens only when JEV_ENDPOINT is set explicitly in the environment.
There is no default endpoint and no stub key, so no paid call can happen by accident.
Without an endpoint every call raises JevUnconfigured and the local keyword
heuristic answers instead (reported as such). The decision and any confidence
come from the HTTP response; nothing is simulated.
"""

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hierarchical_routing.hierarchical_engine import HeuristicFallbackEngine
from ztc.paths import CONFIG_DIR

MAX_RESPONSE_BYTES = 64 * 1024


class JevUnconfigured(RuntimeError):
    """JEV_ENDPOINT is not set; the client never guesses an endpoint."""


class CircuitBreakerState:
    CLOSED = "CLOSED"  # calls go to Jev
    OPEN = "OPEN"  # calls go to the local heuristic
    HALF_OPEN = "HALF_OPEN"  # next call probes Jev


class JevGatewayClient:
    def __init__(self, config_path: Optional[str] = None, endpoint: Optional[str] = None):
        self.config = self._load_config(config_path or str(CONFIG_DIR / "jev_config.json"))
        self.endpoint = endpoint if endpoint is not None else os.environ.get("JEV_ENDPOINT", "")
        self.api_key = os.environ.get(self.config.get("api_key_env", "JEV_API_KEY"), "")
        self.timeout_ms = self.config.get("timeout_ms", 500)

        cb_conf = self.config.get("circuit_breaker", {})
        self.cb_enabled = cb_conf.get("enabled", True)
        self.failure_threshold = cb_conf.get("failure_threshold", 3)
        self.recovery_timeout_sec = cb_conf.get("recovery_timeout_seconds", 30)
        self.latency_ceiling_ms = cb_conf.get("latency_ceiling_ms", 400)

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.local = HeuristicFallbackEngine()

    def _load_config(self, path: str) -> Dict[str, Any]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"circuit_breaker": {"enabled": True, "failure_threshold": 3, "recovery_timeout_seconds": 30}}

    def _check_circuit_health(self):
        if self.state == CircuitBreakerState.OPEN and time.time() - self.last_failure_time > self.recovery_timeout_sec:
            self.state = CircuitBreakerState.HALF_OPEN

    def _record_success(self):
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED

    def _record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.cb_enabled and self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN

    def _fallback(self, state, options, reason: str) -> Dict[str, Any]:
        res = self.local.fallback_resolve(state, options)
        res["circuit_breaker_state"] = self.state
        res["deadman_switch_triggered"] = True
        res["upstream_error"] = reason
        return res

    def route_decision(self, state: Dict[str, Any], options: List[str], instructions: str = "Select the best option") -> Dict[str, Any]:
        """Ask Jev; on open breaker, missing endpoint or any failure, answer with the local heuristic."""
        t0 = time.perf_counter()
        self._check_circuit_health()
        if self.state == CircuitBreakerState.OPEN:
            return self._fallback(state, options, "circuit_open")
        try:
            res = self._execute_jev_call(state, options, instructions)
        except JevUnconfigured:
            return self._fallback(state, options, "jev_unconfigured")
        except Exception as exc:
            self._record_failure()
            return self._fallback(state, options, f"{type(exc).__name__}: {exc}"[:200])

        elapsed_ms = (time.perf_counter() - t0) * 1000
        if elapsed_ms > self.latency_ceiling_ms:
            self._record_failure()
        else:
            self._record_success()
        res["latency_ms"] = round(elapsed_ms, 3)
        res["circuit_breaker_state"] = self.state
        return res

    def _execute_jev_call(self, state: Dict[str, Any], options: List[str], instructions: str) -> Dict[str, Any]:
        """POST to JEV_ENDPOINT. The response must name one of the options."""
        if not self.endpoint:
            raise JevUnconfigured("JEV_ENDPOINT not set")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = json.dumps({"state": state, "options": options, "instructions": instructions}).encode("utf-8")
        req = Request(self.endpoint, data=body, headers=headers, method="POST")
        with urlopen(req, timeout=self.timeout_ms / 1000) as resp:
            data = json.loads(resp.read(MAX_RESPONSE_BYTES).decode("utf-8"))
        decision = data.get("decision")
        if decision not in options:
            raise ValueError("Jev response decision is not one of the options")
        return {
            "engine": "jev-http",
            "decision": decision,
            "confidence": data.get("confidence"),  # as reported by Jev, may be None
            "options_count": len(options),
            "status": "success",
        }
