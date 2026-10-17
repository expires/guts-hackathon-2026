"""Project internal `SimState` onto the wire `Life` model."""

from __future__ import annotations

import math

from lifeline_contracts.domain import (
    Asset,
    AvailableAction,
    Event,
    Finances,
    IndexState,
    Job,
    Life,
    RewindState,
    Ribbon,
    Stats,
    YearLog,
)
from lifeline_sim import params as p
from lifeline_sim.index import IndexWeights, income_base, index_value, r_value
from lifeline_sim.state import SimState


def money_stat(s: SimState, w: IndexWeights) -> int:
    """0-100 bar. 50 = zero net worth. Scales with net worth over twice the yearly income."""
    base = 2 * max(s.income, income_base(s.income0, w))
    return int(max(0, min(100, round(50 + 50 * math.tanh(s.net_worth / base)))))


def index_state(s: SimState, twin: SimState, w: IndexWeights) -> IndexState:
    """Index of player state `s` against the autopilot twin state at the same year."""
    rp = r_value(s.net_worth, s.nw0, s.income0, w)
    ra = r_value(twin.net_worth, s.nw0, s.income0, w)
    value = index_value(rp, ra, s.missed, s.max_dd, twin.missed, twin.max_dd, w)
    return IndexState(
        value=round(value, 2),
        r_player=round(rp, 4),
        r_autopilot=round(ra, 4),
        missed_payments=s.missed,
        max_drawdown=round(min(1.0, s.max_dd), 4),
    )


def _finances(s: SimState) -> Finances:
    return Finances(
        cash=round(s.cash, 2),
        savings=round(s.savings, 2),
        investments=round(s.investments, 2),
        crypto=round(s.crypto, 2),
        pension=round(s.pension, 2),
        property_value=round(s.property_value, 2),
        mortgage_balance=round(s.mortgage_balance, 2),
        mortgage_rate=round(s.mortgage_rate, 2) if s.mortgage_rate is not None and s.mortgage_balance > 0 else None,
        mortgage_fixed_until=s.mortgage_fixed_until if s.mortgage_balance > 0 else None,
        other_debt=round(s.other_debt, 2),
        student_loan=round(s.student_loan, 2),
        annual_income=round(s.income, 2),
        monthly_costs=round(s.monthly_costs, 2),
        net_worth=round(s.net_worth, 2),
    )


def _assets(s: SimState) -> list[Asset]:
    out: list[Asset] = []
    if s.property_value > 0:
        out.append(Asset(id="as-home", kind="home", name="Home", value=round(s.property_value, 2)))
    if s.pension > 0:
        out.append(Asset(id="as-pension", kind="pension", name="Workplace pension", value=round(s.pension, 2)))
    if s.investments > 0:
        out.append(Asset(id="as-shares", kind="investment", name="Shares fund", value=round(s.investments, 2)))
    if s.crypto > 0:
        out.append(Asset(id="as-crypto", kind="crypto", name="Crypto", value=round(s.crypto, 2)))
    if s.savings > 0:
        out.append(Asset(id="as-savings", kind="other", name="Savings account", value=round(s.savings, 2)))
    return out


def to_life(
    s: SimState,
    *,
    life_id: str,
    history: list[YearLog],
    twin: SimState,
    pending: list[Event],
    concepts_unlocked: list[str],
    ribbons: list[Ribbon],
    rewind: RewindState,
    room_code: str | None,
    w: IndexWeights,
    actions: list[AvailableAction] | None = None,
) -> Life:
    job = None
    if s.employed:
        job = Job(
            title=s.job_title,
            annual_income=round(s.income, 2),
            years_in_role=s.years_in_role,
            employer_status="unknown",
        )
    return Life(
        id=life_id,
        seed=s.seed,
        mode=s.mode,
        character=s.character,
        start_year=s.start_year,
        year=s.year,
        age=s.age,
        alive=s.alive,
        cause_of_death=s.cause_of_death,
        stats=Stats(happiness=s.happiness, health=s.health, smarts=s.smarts, money=money_stat(s, w)),
        finances=_finances(s),
        index=index_state(s, twin, w),
        job=job,
        assets=_assets(s),
        relationships=list(s.relationships),
        pending_events=pending if s.alive else [],
        available_actions=list(actions or []) if s.alive else [],
        history=history,
        ribbons=ribbons,
        concepts_unlocked=concepts_unlocked,
        rewind=rewind,
        room_code=room_code,
        reached_present=s.year >= p.PRESENT_YEAR,
    )
