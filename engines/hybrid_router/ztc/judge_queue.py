"""Bounded asynchronous judge queue (plan v0.3 §5.4 S4).

- capacity bound: submissions beyond `capacity` are dropped and counted
- de-duplication: a key already pending is merged, not queued twice
- TTL: jobs older than `ttl_sec` when dequeued are cancelled, not run
- cancellation: cancel(key) and shutdown() cancel pending jobs; shutdown joins the worker
- no child processes are spawned by Phase 1 judges (nothing to reap)
"""

import threading
import time
from collections import OrderedDict
from collections.abc import Callable


class JudgeQueue:
    def __init__(self, judge: Callable[[str, dict], None], capacity: int = 64, ttl_sec: float = 30.0):
        self._judge = judge
        self.capacity = capacity
        self.ttl_sec = ttl_sec
        self._pending: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._cv = threading.Condition()
        self._stopping = False
        self.stats = {"submitted": 0, "merged": 0, "dropped_full": 0, "cancelled": 0,
                      "expired": 0, "done": 0, "failed": 0}
        self._worker = threading.Thread(target=self._run, name="ztc-judge", daemon=True)
        self._worker.start()

    def submit(self, key: str, payload: dict) -> str:
        """Returns 'queued', 'merged', 'full' or 'stopping'."""
        with self._cv:
            if self._stopping:
                return "stopping"
            if key in self._pending:
                self.stats["merged"] += 1
                return "merged"
            if len(self._pending) >= self.capacity:
                self.stats["dropped_full"] += 1
                return "full"
            self._pending[key] = (time.monotonic(), payload)
            self.stats["submitted"] += 1
            self._cv.notify()
            return "queued"

    def cancel(self, key: str) -> bool:
        with self._cv:
            if self._pending.pop(key, None) is None:
                return False
            self.stats["cancelled"] += 1
            return True

    def depth(self) -> int:
        with self._cv:
            return len(self._pending)

    def alive(self) -> bool:
        return self._worker.is_alive()

    def shutdown(self, timeout: float = 2.0) -> None:
        with self._cv:
            self._stopping = True
            self.stats["cancelled"] += len(self._pending)
            self._pending.clear()
            self._cv.notify_all()
        self._worker.join(timeout)

    def _run(self) -> None:
        while True:
            with self._cv:
                while not self._pending and not self._stopping:
                    self._cv.wait()
                if self._stopping:
                    return
                key, (enqueued, payload) = self._pending.popitem(last=False)
                if time.monotonic() - enqueued > self.ttl_sec:
                    self.stats["expired"] += 1
                    continue
            try:
                self._judge(key, payload)
                outcome = "done"
            except Exception:
                outcome = "failed"
            with self._cv:
                self.stats[outcome] += 1
