"""In-memory sliding-window rate limiter for the cost-incurring recommend
endpoints. Good enough for a single-process deployment; a multi-instance
deployment would move this state to Redis (INCR + EXPIRE), but the interface
here — check(key) raising 429 when exceeded — wouldn't change.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_WINDOW_SECONDS = 60
_MAX_REQUESTS_PER_WINDOW = 10

_lock = threading.Lock()
_requests: dict[str, deque] = defaultdict(deque)


def check(key: str) -> None:
    now = time.monotonic()
    with _lock:
        bucket = _requests[key]
        while bucket and now - bucket[0] > _WINDOW_SECONDS:
            bucket.popleft()

        if len(bucket) >= _MAX_REQUESTS_PER_WINDOW:
            retry_after = max(1, int(_WINDOW_SECONDS - (now - bucket[0])) + 1)
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: max {_MAX_REQUESTS_PER_WINDOW} requests per {_WINDOW_SECONDS}s.",
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce(request: Request) -> None:
    """FastAPI dependency: Depends(enforce)."""
    check(client_key(request))
