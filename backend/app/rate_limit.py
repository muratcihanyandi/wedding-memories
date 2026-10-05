"""Basit in-memory sliding window rate limiter.

Tek uvicorn worker uzerinde calistigi icin process ici state yeterlidir.
Limiter ornekleri app.state uzerinde tutulur; boylece her test kendi
temiz limiter'ini alir.
"""

import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: int):
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Event kaydeder; limit asildiysa False doner."""
        now = time.monotonic()
        with self._lock:
            queue = self._events[key]
            cutoff = now - self.window_seconds
            while queue and queue[0] < cutoff:
                queue.popleft()
            if len(queue) >= self.max_events:
                return False
            queue.append(now)
            if len(self._events) > 5000:
                self._purge_locked(now)
            return True

    def _purge_locked(self, now: float) -> None:
        cutoff = now - self.window_seconds
        stale = [k for k, q in self._events.items() if not q or q[-1] < cutoff]
        for key in stale:
            del self._events[key]

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
