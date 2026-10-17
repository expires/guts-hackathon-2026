"""Health signal from the phone (ADR 0029 item 4): steps and sleep give a bounded Health effect.

Rule (applied once, at the AGE that receives the input):
- Steps per day (average). Bands follow the NHS guidance of 150 minutes of moderate activity a
  week (NHS, "Physical activity guidelines for adults aged 19 to 64"), which is about 8,000 to
  10,000 steps a day:
    >= 10,000: +5 | 8,000-9,999: +3 | 5,000-7,999: 0 | 3,000-4,999: -3 | < 3,000: -5
- Sleep hours per night (average). NHS, "How to get to sleep": most adults need 7 to 9 hours.
    7-9: +5 | 6-7 or 9-10: 0 | < 6: -5 | > 10: -2
- A missing input adds 0. The total is clamped to [-10, +10].

Replay: the input is stored in the AGE history entry (`event_id = "hl-<year>-1"`,
`choice_id = "health?sleep=7.5&steps=8200"`, `decision_id = None`), so replay and rewind apply
the same effect. The input is not a decision: rewind cannot target it, and the autopilot twin
never gets it.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qsl

HEALTH_PREFIX = "hl"
CHOICE_PREFIX = "health"
MAX_EFFECT = 10
MAX_STEPS = 100_000.0
MAX_SLEEP = 24.0


@dataclass(frozen=True)
class HealthInput:
    steps_per_day: float | None = None
    sleep_hours: float | None = None

    def __post_init__(self) -> None:
        if self.steps_per_day is not None and not 0 <= self.steps_per_day <= MAX_STEPS:
            raise ValueError(f"steps_per_day must be between 0 and {MAX_STEPS:,.0f}")
        if self.sleep_hours is not None and not 0 <= self.sleep_hours <= MAX_SLEEP:
            raise ValueError(f"sleep_hours must be between 0 and {MAX_SLEEP:.0f}")

    @property
    def empty(self) -> bool:
        return self.steps_per_day is None and self.sleep_hours is None

    def encode(self) -> str:
        parts = []
        if self.sleep_hours is not None:
            parts.append(f"sleep={round(self.sleep_hours, 2):g}")
        if self.steps_per_day is not None:
            parts.append(f"steps={round(self.steps_per_day):d}")
        return f"{CHOICE_PREFIX}?{'&'.join(parts)}"

    @staticmethod
    def decode(choice_id: str) -> HealthInput | None:
        head, _, query = choice_id.partition("?")
        if head != CHOICE_PREFIX:
            return None
        vals: dict[str, float] = {}
        for k, v in parse_qsl(query):
            try:
                vals[k] = float(v)
            except ValueError:
                return None
        try:
            return HealthInput(steps_per_day=vals.get("steps"), sleep_hours=vals.get("sleep"))
        except ValueError:
            return None


def steps_points(steps: float | None) -> int:
    if steps is None:
        return 0
    if steps >= 10_000:
        return 5
    if steps >= 8_000:
        return 3
    if steps >= 5_000:
        return 0
    if steps >= 3_000:
        return -3
    return -5


def sleep_points(hours: float | None) -> int:
    if hours is None:
        return 0
    if 7 <= hours <= 9:
        return 5
    if 6 <= hours < 7 or 9 < hours <= 10:
        return 0
    if hours < 6:
        return -5
    return -2


def health_effect(h: HealthInput) -> int:
    """Health stat change for one AGE, in [-10, +10]."""
    return max(-MAX_EFFECT, min(MAX_EFFECT, steps_points(h.steps_per_day) + sleep_points(h.sleep_hours)))


def health_id(year: int) -> str:
    return f"{HEALTH_PREFIX}-{year}-1"


def is_health_id(decision_id: str) -> bool:
    return decision_id.startswith(f"{HEALTH_PREFIX}-")
