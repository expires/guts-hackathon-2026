"""Stable randomness. Never uses Python `hash()` or the global RNG.

Every random draw is keyed by a tuple of parts, for example (seed, year, "death").
The same parts always give the same draw, on every machine and every run.
"""

from __future__ import annotations

import hashlib
import random


def stable_hash(*parts: object) -> int:
    """64-bit integer from the SHA-256 of the parts joined with a separator."""
    text = "\x1f".join(repr(p) for p in parts)
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def rng(*parts: object) -> random.Random:
    """A private `random.Random` seeded from the parts."""
    return random.Random(stable_hash(*parts))


def uniform(*parts: object) -> float:
    """One draw in [0, 1) keyed by the parts."""
    return stable_hash(*parts) / 2.0**64
