#!/usr/bin/env python3
"""
jev_client.py
Local keyword-matching simulation with a circuit-breaker-shaped fallback.
The Jev path below makes no HTTP request and does not run model inference.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

# Import local Laya engine as fallback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hierarchical_routing.hierarchical_engine import LayaHierarchicalEngine


class CircuitBreakerState:
    CLOSED = "CLOSED"      # Normal operation: local Jev-path simulation
    OPEN = "OPEN"          # Tripped: calls use local keyword fallback
    HALF_OPEN = "HALF_OPEN"# Probing recovery


class JevGatewayClient:
    def __init__(self, config_path: Optional[str] = None):
        if not config_path:
            config_path = str(Path(__file__).resolve().parents[3] / "config" / "jev_config.json")
        
        self.config = self._load_config(config_path)
        
        # Circuit Breaker attributes
        cb_conf = self.config.get("circuit_breaker", {})
        self.cb_enabled = cb_conf.get("enabled", True)
        self.failure_threshold = cb_conf.get("failure_threshold", 3)
        self.recovery_timeout_sec = cb_conf.get("recovery_timeout_seconds", 30)
        self.latency_ceiling_ms = cb_conf.get("latency_ceiling_ms", 400)
        
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        
        # Local keyword-heuristic fallback
        self.local_laya = LayaHierarchicalEngine()

    def _load_config(self, path: str) -> Dict[str, Any]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "mode": "simulated_keyword_match",
            "circuit_breaker": {"enabled": True, "failure_threshold": 3, "recovery_timeout_seconds": 30}
        }

    def _check_circuit_health(self):
        """Update circuit breaker state based on elapsed recovery time."""
        if self.state == CircuitBreakerState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout_sec:
                self.state = CircuitBreakerState.HALF_OPEN
                print("[!] Circuit Breaker: Recovery window reached. Transitioning to HALF_OPEN probe state.")

    def _record_success(self):
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED

    def _record_failure(self, reason: str):
        self.failure_count += 1
        self.last_failure_time = time.time()
        print(f"[!] Simulated route warning: Failure #{self.failure_count}/{self.failure_threshold} ({reason})")
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            print("[LOCAL FALLBACK] Circuit breaker opened; using keyword heuristic fallback.")

    def route_decision(self, state: Dict[str, Any], options: List[str], instructions: str = "Select the best option", force_fail: bool = False) -> Dict[str, Any]:
        """
        Execute a local simulated result or use keyword fallback after failure.
        """
        t0 = time.perf_counter()
        self._check_circuit_health()

        # If Circuit Breaker is OPEN, bypass Jev completely and route to Laya
        if self.state == CircuitBreakerState.OPEN and not force_fail:
            print("[Circuit Breaker OPEN] Using local heuristic keyword fallback.")
            fallback_res = self.local_laya.fallback_resolve(state, options)
            fallback_res["circuit_breaker_state"] = self.state
            fallback_res["deadman_switch_triggered"] = True
            return fallback_res

        try:
            if force_fail:
                raise ConnectionError("Simulated route failure")

            res = self._simulate_keyword_match(state, options)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            
            if elapsed_ms > self.latency_ceiling_ms:
                self._record_failure(f"Latency ceiling exceeded ({elapsed_ms}ms > {self.latency_ceiling_ms}ms)")
            else:
                self._record_success()

            res["latency_ms"] = elapsed_ms
            res["circuit_breaker_state"] = self.state
            return res

        except Exception as exc:
            self._record_failure(str(exc))
            print(f"[*] Executing local heuristic fallback... Reason: {exc}")
            fallback_res = self.local_laya.fallback_resolve(state, options)
            fallback_res["circuit_breaker_state"] = self.state
            fallback_res["deadman_switch_triggered"] = True
            fallback_res["upstream_error"] = str(exc)
            return fallback_res

    def _simulate_keyword_match(self, state: Dict[str, Any], options: List[str]) -> Dict[str, Any]:
        # Determine candidate with highest contextual score
        text_repr = str(state).lower()
        scored = []
        for opt in options:
            tokens = opt.lower().replace("_", " ").split()
            score = sum(1.5 if token in text_repr else 0.1 for token in tokens)
            scored.append((opt, score))
            
        scored.sort(key=lambda x: x[1], reverse=True)
        winner = scored[0][0] if scored else options[0]
        
        return {
            "engine": "simulated-jev-keyword-match",
            "decision_method": "keyword_overlap",
            "model_inference_performed": False,
            "decision": winner,
            "options_count": len(options),
            "mode": "simulated_keyword_match",
            "status": "success"
        }


if __name__ == "__main__":
    client = JevGatewayClient()
    
    print("=== TEST 1: Local Keyword-Match Simulation ===")
    large_options = [f"category_service_alpha_{i}" for i in range(25)]
    large_options.append("category_service_alpha_core_pipeline")
    test_state = {"context": "Fatal exception in core pipeline message broker", "severity": "HIGH"}
    
    res1 = client.route_decision(test_state, large_options)
    print(f"Decision: {res1.get('decision')} | Engine: {res1.get('engine')} | Latency: {res1.get('latency_ms')}ms | CB State: {res1.get('circuit_breaker_state')}\n")

    print("=== TEST 2: Simulated Route Failures ===")
    for i in range(3):
        print(f"--- Simulating route failure #{i+1} ---")
        client.route_decision(test_state, large_options, force_fail=True)

    print("\n=== TEST 3: Subsequent Call while Circuit Breaker is OPEN ===")
    res3 = client.route_decision(test_state, large_options)
    print(f"Decision: {res3.get('decision')} | Engine: {res3.get('engine')} | Deadman Switch: {res3.get('deadman_switch_triggered')} | CB State: {res3.get('circuit_breaker_state')}")
