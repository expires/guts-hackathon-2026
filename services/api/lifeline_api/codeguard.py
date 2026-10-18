"""Wrong-code limiter for room and circle codes (V6 final F-1).

Room codes have 4 digits, so guessing must be slow: at most WRONG_CODE_PER_MINUTE (10) wrong codes per minute
per account. Per IP there is only a high flood guard, WRONG_CODE_IP_PER_MINUTE (120), so one venue Wi-Fi is not
blocked by a few mistyped codes. Separate from the sign-in limiter.

- Only wrong codes count. A player who already has a seat in the room is never blocked.
- Once the limit is reached, new code lookups from that IP or account answer 429 until the minute ends,
  correct or not. Otherwise a blocked guesser would still learn which codes exist.
- Counters are fixed one-minute windows in Redis (shared by replicas), with a process fallback.
"""

from __future__ import annotations

import logging
import time

from lifeline_api.errors import ApiError
from lifeline_api.state import AppState

log = logging.getLogger(__name__)

WINDOW_SECONDS = 60
PREFIX = "lifeline:wrong-code"


def _keys(ip: str, sub: str | None) -> list[str]:
    window = int(time.time()) // WINDOW_SECONDS
    keys = [f"{PREFIX}:ip:{ip}:{window}"]
    if sub:
        keys.append(f"{PREFIX}:sub:{sub}:{window}")
    return keys


def _retry_after() -> int:
    return WINDOW_SECONDS - int(time.time()) % WINDOW_SECONDS or 1


async def _count(state: AppState, key: str) -> int:
    if state.redis is not None:
        try:
            raw = await state.redis.get(key)
            return int(raw or 0)
        except Exception as exc:
            log.info("wrong-code counter read failed (%s); process counter used", type(exc).__name__)
    return int(state.memo.get(("wrong-code", key), 0))


async def is_blocked(state: AppState, ip: str, sub: str | None) -> bool:
    for key in _keys(ip, sub):
        limit = (state.settings.wrong_code_ip_per_minute if ":ip:" in key
                 else state.settings.wrong_code_per_minute)
        if await _count(state, key) >= limit:
            return True
    return False


async def record_wrong(state: AppState, ip: str, sub: str | None) -> None:
    for key in _keys(ip, sub):
        if state.redis is not None:
            try:
                await state.redis.incr(key)
                await state.redis.expire(key, 2 * WINDOW_SECONDS)
                continue
            except Exception as exc:
                log.info("wrong-code counter write failed (%s); process counter used", type(exc).__name__)
        mk = ("wrong-code", key)
        state.memo[mk] = int(state.memo.get(mk, 0)) + 1


def too_many() -> ApiError:
    return ApiError(429, "rate_limited", "Too many wrong codes. Try again in a minute.",
                    headers={"Retry-After": str(_retry_after())})


async def guard(state: AppState, ip: str, sub: str | None) -> None:
    """Call before looking up a code. Raises 429 when this IP or account used up its wrong codes."""
    if await is_blocked(state, ip, sub):
        raise too_many()
