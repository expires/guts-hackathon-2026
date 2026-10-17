"""Quick Life plan (ADR 0052, ADR 0059): ages 18 to 25 in 5 or 6 AGE taps, with 2 or 3 events.

The plan is a pure function of the seed and the start year, so every player in a room with the same seed,
path and start year plays the same taps and meets the same events. Choices never change the plan.

- Taps: 7 years split into 5 or 6 blocks. Each block is 1 or 2 years long (5 taps: two 2-year blocks;
  6 taps: one). One AGE tap moves to the end of the next block.
- Events: 2 or 3 of the taps before the last one end with one student event each. The last tap ends the life
  at 25 with the summary card, so it has no event.
"""

from __future__ import annotations

from dataclasses import dataclass

from lifeline_sim.paths import QUICK_END_AGE, QUICK_START_AGE
from lifeline_sim.rng import rng

QUICK_YEARS = QUICK_END_AGE - QUICK_START_AGE  # 7


@dataclass(frozen=True)
class QuickPlan:
    stops: tuple[int, ...]  # the year each AGE tap ends at, ascending; the last is end_year
    event_years: tuple[int, ...]  # the stop years that end with one event
    end_year: int


def plan(seed: int, start_year: int) -> QuickPlan:
    r = rng(seed, "quick", "plan")
    taps = r.choice((5, 6))
    doubles = QUICK_YEARS - taps  # number of 2-year blocks: 2 for 5 taps, 1 for 6 taps
    lengths = [1] * taps
    for i in r.sample(range(taps), doubles):
        lengths[i] = 2
    stops: list[int] = []
    y = start_year
    for n in lengths:
        y += n
        stops.append(y)
    n_events = r.choice((2, 3))
    event_years = tuple(sorted(r.sample(stops[:-1], n_events)))
    return QuickPlan(stops=tuple(stops), event_years=event_years, end_year=stops[-1])


def next_stop(qp: QuickPlan, year: int) -> int | None:
    """The year the next AGE tap ends at, or None when the Quick Life is over."""
    return next((s for s in qp.stops if s > year), None)
