"""Feed watchdog used to turn stale camera input into Unknown."""
from __future__ import annotations

import time


class FeedWatchdog:
    def __init__(self, timeout_seconds: float = 1.5) -> None:
        self.timeout_seconds = timeout_seconds
        self._last_timestamp_ms: int | None = None
        self._last_wall_time = time.monotonic()

    def observe(self, timestamp_ms: int) -> None:
        self._last_timestamp_ms = timestamp_ms
        self._last_wall_time = time.monotonic()

    def is_stale(self, now_monotonic: float | None = None) -> bool:
        now = time.monotonic() if now_monotonic is None else now_monotonic
        return now - self._last_wall_time > self.timeout_seconds

    @property
    def last_timestamp_ms(self) -> int | None:
        return self._last_timestamp_ms
