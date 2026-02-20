"""
Rate Limiter - Per-user token bucket to prevent API quota exhaustion
"""

import time
from typing import Dict, List


class RateLimiter:
    """Simple sliding-window rate limiter. Keeps timestamps of recent requests per user."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: Dict[str, List[float]] = {}

    def _prune(self, user_id: str) -> None:
        cutoff = time.monotonic() - self.window_seconds
        self._buckets[user_id] = [t for t in self._buckets.get(user_id, []) if t > cutoff]

    def is_allowed(self, user_id: str) -> bool:
        """Return True if the user has not exceeded the rate limit."""
        self._prune(user_id)
        if len(self._buckets.get(user_id, [])) >= self.max_requests:
            return False
        self._buckets.setdefault(user_id, []).append(time.monotonic())
        return True

    def time_until_allowed(self, user_id: str) -> float:
        """Seconds until the next request would be allowed (0 if already allowed)."""
        self._prune(user_id)
        timestamps = self._buckets.get(user_id, [])
        if len(timestamps) < self.max_requests:
            return 0.0
        oldest_in_window = timestamps[0]
        return max(0.0, self.window_seconds - (time.monotonic() - oldest_in_window))
