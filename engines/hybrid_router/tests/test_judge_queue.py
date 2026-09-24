#!/usr/bin/env python3
"""Bounded judge queue: capacity, de-duplication, cancellation, TTL, shutdown."""

import threading
import time
import unittest

import _support  # noqa: F401
from ztc.judge_queue import JudgeQueue


class Gate:
    """Judge that blocks until released, recording what it ran."""

    def __init__(self):
        self.release = threading.Event()
        self.started = threading.Event()
        self.ran = []

    def __call__(self, key, payload):
        self.started.set()
        self.release.wait(5)
        self.ran.append(key)


def wait_for(pred, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.005)
    return False


class TestJudgeQueue(unittest.TestCase):
    def test_capacity_merge_and_drop(self):
        gate = Gate()
        q = JudgeQueue(gate, capacity=2)
        try:
            q.submit("busy", {})
            self.assertTrue(gate.started.wait(2))  # worker is now occupied
            self.assertEqual(q.submit("a", {}), "queued")
            self.assertEqual(q.submit("a", {}), "merged")
            self.assertEqual(q.submit("b", {}), "queued")
            self.assertEqual(q.submit("c", {}), "full")
            self.assertEqual(q.stats["dropped_full"], 1)
            gate.release.set()
            self.assertTrue(wait_for(lambda: q.stats["done"] == 3))
            self.assertEqual(gate.ran, ["busy", "a", "b"])
        finally:
            gate.release.set()
            q.shutdown()

    def test_cancel_pending(self):
        gate = Gate()
        q = JudgeQueue(gate, capacity=4)
        try:
            q.submit("busy", {})
            gate.started.wait(2)
            q.submit("x", {})
            self.assertTrue(q.cancel("x"))
            self.assertFalse(q.cancel("x"))
            gate.release.set()
            self.assertTrue(wait_for(lambda: q.stats["done"] == 1))
            self.assertNotIn("x", gate.ran)
        finally:
            gate.release.set()
            q.shutdown()

    def test_ttl_expiry(self):
        gate = Gate()
        q = JudgeQueue(gate, capacity=4, ttl_sec=0.05)
        try:
            q.submit("busy", {})
            gate.started.wait(2)
            q.submit("stale", {})
            time.sleep(0.1)
            gate.release.set()
            self.assertTrue(wait_for(lambda: q.stats["expired"] == 1))
            self.assertNotIn("stale", gate.ran)
        finally:
            gate.release.set()
            q.shutdown()

    def test_shutdown_cancels_and_joins(self):
        gate = Gate()
        q = JudgeQueue(gate, capacity=8)
        q.submit("busy", {})
        gate.started.wait(2)
        for k in "abc":
            q.submit(k, {})
        gate.release.set()
        q.shutdown()
        self.assertFalse(q.alive())
        self.assertEqual(q.submit("late", {}), "stopping")
        self.assertGreaterEqual(q.stats["cancelled"] + q.stats["done"], 3)

    def test_failing_judge_does_not_kill_worker(self):
        def boom(key, payload):
            raise RuntimeError("judge failed")

        q = JudgeQueue(boom)
        try:
            q.submit("a", {})
            self.assertTrue(wait_for(lambda: q.stats["failed"] == 1))
            self.assertTrue(q.alive())
        finally:
            q.shutdown()


if __name__ == "__main__":
    unittest.main()
