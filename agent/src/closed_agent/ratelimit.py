from __future__ import annotations

from collections import defaultdict, deque
from time import monotonic

from closed_agent.settings import settings


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        window = 60.0
        limit = max(1, settings.rate_limit_per_minute)
        now = monotonic()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


rate_limiter = RateLimiter()
