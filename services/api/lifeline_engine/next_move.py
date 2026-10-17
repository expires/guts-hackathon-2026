"""Next Move engine (ADR 0018): "What is my next money move?" Pure: no I/O, no clock, no global RNG.

Inputs: the user's FinanceSnapshot, the MacroTable, `today`, and a seed (used only by the emergency
fund shock draw).

Method for each candidate move:
1. The move is a candidate only when the data supports it (see the `_<kind>` builders).
2. Twins: the K_TWINS nearest people to the user's profile in the synthetic population (twins.py).
   Periods: the K_PERIODS past start years whose macro state is most like today (periods.py), with
   a full horizon of data that ended before today (no look-ahead).
3. Each (twin, period) pair is simulated: gain = GBP per year vs doing nothing. Today's quoted rates
   are known; the past period supplies how rates and prices then CHANGED (delta method).
4. impact_per_year = mean gain for the user's own amounts over the periods. worst_case_per_year =
   the worst period for the user. confidence = share of (twin, period) pairs where the move beat
   doing nothing (mortgage: beat doing nothing AND the other fix length, see ADR request in the report).
5. Rank: score = (impact + 0.5 * min(0, worst)) * confidence. Ties: nearer deadline, then kind order.

Labelled assumptions (no data source): VARIABLE_MARGIN (same as lifeline_sim.params), TRACKER_MARGIN,
BEST_SAVINGS_*, SAFETY_MONTHS, SHOCK_*, CUT_* thresholds.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np

from lifeline_contracts.domain import DecisionProfile, SourceRef
from lifeline_contracts.finance import FinanceSnapshot
from lifeline_contracts.macro import MacroKey, MacroTable
from lifeline_contracts.next_move import (
    EvidencePoint,
    Move,
    MoveKind,
    MoveOption,
    NextMoveBacktest,
    NextMoveResponse,
    TestPeriod,
)
from lifeline_engine.decision import candidate_starts, mortgage_interest
from lifeline_engine.decision import _twins as nearest_twins
from lifeline_engine.macro_access import latest_year, source_ref, value_or
from lifeline_engine.money import finance_meta
from lifeline_engine.money import dates
from lifeline_engine.money.categorise import label as category_label
from lifeline_engine.money.profile import (
    debt_total,
    full_months_before,
    liquid,
    monthly_spend,
    profile,
    savings_rate_pct,
    savings_total,
)
from lifeline_engine.money.recurring import detect_salary, detect_subscriptions
from lifeline_engine.money.spending import by_category
from lifeline_engine.money.text import digit_facts, gbp, money_value, pct, pct_value, unsupported_numbers
from lifeline_engine.periods import similar_years
from lifeline_engine.population import Person

K_TWINS = 20
K_PERIODS = 5
MORTGAGE_HORIZON = 5
SAVINGS_HORIZON = 3
ONE_YEAR = 1
DEAL_WINDOW_DAYS = 365
ENERGY_WINDOW_DAYS = 60

VARIABLE_MARGIN = 2.0  # standard variable rate = Bank Rate + 2.0 (same as lifeline_sim.params)
TRACKER_MARGIN = 1.0  # tracker = Bank Rate + 1.0
REMORTGAGE_MIN_GAP = 0.25  # percent points above today's best fix before a remortgage is a move
BEST_SAVINGS_GAP = 0.5  # best easy-access rate >= Bank Rate - 0.5
BEST_SAVINGS_PREMIUM = 1.0  # best easy-access rate >= market average + 1.0
MIN_SAVINGS = 1_000.0
MIN_DEBT = 100.0
SAFETY_MONTHS = 1.0  # keep one month of spending when savings pay off debt
EMERGENCY_MONTHS = 3
SHOCK_COST = 1_500.0  # a typical unexpected bill (boiler, car)
SHOCK_BASE_PROB = 0.2  # yearly chance of such a bill, plus the unemployment rate of the period
CUT_MIN_GBP = 30.0
CUT_MIN_SHARE = 0.2
CUT_MIN_AVERAGE = 50.0  # ignore categories with a usual spend under £50 a month
PAYDOWN_MONTHLY = 100.0  # extra card payment per month when there is no spare money (cut spending to fund it)
CUT_CATEGORIES = ("eating_out", "shopping", "entertainment", "travel", "personal_care", "transport", "groceries")

MORTGAGE_TEST = TestPeriod(start=2021, end=2023, label="2021-2023 rate shock")
SAVINGS_TEST = TestPeriod(start=2008, end=2010, label="2008-2010 rate cuts")
ENERGY_TEST = TestPeriod(start=2021, end=2023, label="2021-2023 energy price shock")

KIND_ORDER: tuple[MoveKind, ...] = (
    "fix_mortgage",
    "remortgage",
    "pay_off_debt",
    "move_savings",
    "switch_energy",
    "build_emergency_fund",
    "cancel_subscription",
    "switch_subscription",
    "cut_budget",
)

# Sim template tag per move kind (lifeline_sim templates, ADR 0018). Every option of a move uses the same tag.
MOVE_TAG: dict[MoveKind, str] = {
    "fix_mortgage": "mortgage_deal_end",
    "remortgage": "mortgage_deal_end",
    "move_savings": "savings_rate_change",
    "switch_energy": "energy_bill",
    "pay_off_debt": "card_debt",
    "cancel_subscription": "subscription",
    "switch_subscription": "subscription",
    "cut_budget": "budget_overspend",
    "build_emergency_fund": "emergency_fund",
}
POLICY_DEAL_END = "__deal_end_year"

MORTGAGE_OPTIONS = ("fix_5y", "fix_2y", "tracker")
OPTION_LABEL: dict[str, str] = {
    "fix_5y": "Fix for 5 years",
    "fix_2y": "Fix for 2 years",
    "tracker": "Take a tracker",
    "keep": "Do nothing",
    "switch": "Move your savings",
    "fix": "Fix your energy price",
    "pay_off": "Pay off the card",
    "cancel": "Cancel it",
    "cut": "Cut back",
    "save": "Build a safety net",
}
FIX_YEARS = {"fix_5y": 5, "fix_2y": 2}


# ---------- small helpers ----------


def confidence_label(confidence: float) -> str:
    """'7 in 10 twins in similar past periods did better'. Never '10 in 10' or '0 in 10'."""
    tail = "twins in similar past periods did better"
    n = int(round(confidence * 10))
    if confidence >= 1.0:
        return f"All {tail}"
    if n >= 10:
        return f"More than 9 in 10 {tail}"
    if confidence <= 0.0:
        return f"No {tail}"
    if n == 0:
        return f"Fewer than 1 in 10 {tail}"
    return f"{n} in 10 {tail}"


SURE_LABEL = "A sure saving. It does not depend on markets"


def _ev(text: str, facts: dict[str, float], source: SourceRef | None = None) -> EvidencePoint:
    bad = unsupported_numbers(text, facts)
    if bad:
        raise ValueError(f"evidence number not in facts: {bad} in {text!r}")
    return EvidencePoint(text=text, facts=facts, source=source)


def _v(macro: MacroTable, key: MacroKey, year: int, default: float) -> float:
    return value_or(macro, key, year, None, default)


def _bank(macro: MacroTable, year: int) -> float:
    return _v(macro, MacroKey.BANK_RATE, year, 4.0)


def _fix(macro: MacroTable, key: MacroKey, year: int) -> float:
    margin = 1.5 if key == MacroKey.MORTGAGE_2Y_FIX else 1.9
    return _v(macro, key, year, _bank(macro, year) + margin)


def _savings_avg(macro: MacroTable, year: int) -> float:
    return _v(macro, MacroKey.SAVINGS_RATE, year, max(0.0, _bank(macro, year) - 1.5))


def _best_savings(macro: MacroTable, year: int) -> float:
    return max(_bank(macro, year) - BEST_SAVINGS_GAP, _savings_avg(macro, year) + BEST_SAVINGS_PREMIUM)


def _card(macro: MacroTable, year: int) -> float:
    return _v(macro, MacroKey.CARD_RATE, year, _bank(macro, year) + 18.0)


def _refs(macro: MacroTable, year: int, keys: Sequence[MacroKey]) -> list[SourceRef]:
    return [r for r in (source_ref(macro, k, year) for k in keys) if r is not None]


def _bank_ref(snapshot: FinanceSnapshot) -> SourceRef:
    return SourceRef(
        source=f"bank:{snapshot.source}",
        series_id=snapshot.persona or "transactions",
        status=snapshot.status,
        note="Sample data" if snapshot.status == "mock" else None,
    )


def _slug(text: str) -> str:
    return "-".join("".join(c if c.isalnum() else " " for c in text.lower()).split())[:40] or "item"


# ---------- context ----------


@dataclass
class Context:
    snapshot: FinanceSnapshot
    macro: MacroTable
    today: dates.date
    year: int
    profile: DecisionProfile
    seed: int
    twins: list[Person] = field(default_factory=list)
    _periods: dict[int, list[int]] = field(default_factory=dict)

    def periods(self, horizon: int) -> list[int]:
        """K_PERIODS past start years most like `year`, whose `horizon`-year window ended before `year`."""
        if horizon not in self._periods:
            pool = candidate_starts(self.macro, before=self.year, horizon=horizon)
            self._periods[horizon] = [m.year for m in similar_years(self.macro, self.year, K_PERIODS, candidates=pool)]
        return self._periods[horizon]

    def matched_test_period(self) -> TestPeriod:
        starts = self.periods(3)
        s = starts[0] if starts else MORTGAGE_TEST.start
        return TestPeriod(start=s, end=s + 2, label=f"{s}-{s + 2}, the past period most like today")

    @property
    def n_twins(self) -> int:
        return max(1, len(self.twins))


@dataclass(frozen=True)
class Candidate:
    move: Move
    score: float


def _score(impact: float, worst: float, confidence: float) -> float:
    return (impact + 0.5 * min(0.0, worst)) * confidence


def _grid(ctx: Context, starts: Sequence[int], amount_of: Callable[[Person], float], gain: Callable[[float, int], float]
          ) -> np.ndarray:
    """gain(amount, start) for every (twin, period) pair. Shape (twins, periods)."""
    people = ctx.twins or []
    amounts = [amount_of(p) for p in people] or [amount_of_default(ctx)]
    return np.array([[gain(a, s) for s in starts] for a in amounts], dtype=np.float64)


def amount_of_default(ctx: Context) -> float:
    return 0.0


def _move(
    ctx: Context,
    kind: MoveKind,
    move_id: str,
    action: str,
    headline: str,
    impact: float,
    worst: float,
    confidence: float,
    confidence_text: str,
    evidence: list[EvidencePoint],
    sources: list[SourceRef],
    options: list[MoveOption],
    test_period: TestPeriod | None,
    concept_id: str,
    deadline: str | None = None,
) -> Candidate:
    days_left = None
    if deadline is not None:
        days_left = max(0, (dates.parse(deadline) - ctx.today).days)
    move = Move(
        id=move_id,
        kind=kind,
        action=action,
        headline=headline,
        impact_per_year=round(impact, 2),
        worst_case_per_year=round(worst, 2),
        confidence=round(min(1.0, max(0.0, confidence)), 4),
        confidence_label=confidence_text,
        evidence=evidence,
        sources=sources,
        options=options,
        deadline=deadline,
        days_left=days_left,
        testable=test_period is not None,
        test_period=test_period,
        concept_id=concept_id,
    )
    return Candidate(move=move, score=_score(impact, worst, confidence))


def _options(recommended: str, others: Sequence[str]) -> list[MoveOption]:
    ids = [recommended, *[o for o in others if o != recommended]][:4]
    return [MoveOption(id=o, label=OPTION_LABEL[o], is_recommended=o == recommended) for o in ids]


# ---------- mortgage ----------


def mortgage_paths(
    macro: MacroTable, start: int, q2: float, q5: float, keep_now: float, bank_now: float, horizon: int
) -> dict[str, list[float]]:
    """Rate path (percent per year) for each option, from today's quotes plus the changes seen from `start`.

    - fix_2y: today's 2-year rate, then re-fix every 2 years at today's rate + the change in 2-year rates.
    - fix_5y: today's 5-year rate for 5 years, then re-fix the same way.
    - tracker: today's Bank Rate + the change in Bank Rate, + TRACKER_MARGIN.
    - keep: the rate you move to (standard variable or your current variable rate) + the change in Bank Rate.
    """

    def d(key: MacroKey, t: int) -> float:
        return _fix(macro, key, start + t) - _fix(macro, key, start)

    def db(t: int) -> float:
        return _bank(macro, start + t) - _bank(macro, start)

    return {
        "fix_2y": [max(0.0, q2 + d(MacroKey.MORTGAGE_2Y_FIX, 2 * (t // 2))) for t in range(horizon)],
        "fix_5y": [max(0.0, q5 + d(MacroKey.MORTGAGE_5Y_FIX, 5 * (t // 5))) for t in range(horizon)],
        "tracker": [max(0.0, bank_now + db(t)) + TRACKER_MARGIN for t in range(horizon)],
        "keep": [max(0.0, keep_now + db(t)) for t in range(horizon)],
    }


@dataclass(frozen=True)
class MortgageResult:
    best: str
    runner_up: str
    impact: dict[str, float]  # mean GBP/year vs keep, user's amounts
    worst: dict[str, float]
    confidence: float  # best beat keep and the runner-up
    pairs: int


def rank_mortgage(
    macro: MacroTable,
    starts: Sequence[int],
    balances: Sequence[float],
    user_balance: float,
    years_left: int,
    q2: float,
    q5: float,
    keep_now: float,
    bank_now: float,
    horizon: int = MORTGAGE_HORIZON,
    options: Sequence[str] = MORTGAGE_OPTIONS,
) -> MortgageResult:
    paths = {s: mortgage_paths(macro, s, q2, q5, keep_now, bank_now, horizon) for s in starts}

    def gains(balance: float) -> dict[str, list[float]]:
        out: dict[str, list[float]] = {o: [] for o in options}
        for s in starts:
            keep_cost = mortgage_interest(balance, years_left, paths[s]["keep"])
            for o in options:
                out[o].append((keep_cost - mortgage_interest(balance, years_left, paths[s][o])) / horizon)
        return out

    user = gains(user_balance)
    impact = {o: float(np.mean(user[o])) if user[o] else 0.0 for o in options}
    worst = {o: float(min(user[o])) if user[o] else 0.0 for o in options}
    order = sorted(options, key=lambda o: (-(impact[o] + 0.5 * min(0.0, worst[o])), options.index(o)))
    best, runner = order[0], order[1] if len(order) > 1 else order[0]
    wins = 0
    total = 0
    for b in balances:
        g = gains(b)
        for i in range(len(starts)):
            total += 1
            others = [g[o][i] for o in options if o != best]
            if g[best][i] > 0 and all(g[best][i] > x for x in others):
                wins += 1
    return MortgageResult(best, runner, impact, worst, wins / total if total else 0.0, total)


def _mortgage(ctx: Context) -> Candidate | None:
    m = ctx.snapshot.mortgage
    if m is None or m.balance <= 0 or m.years_left <= 0:
        return None
    kind: MoveKind
    deadline: str | None = None
    days_left = 0
    bank_now = _bank(ctx.macro, ctx.year)
    svr = bank_now + VARIABLE_MARGIN
    q2 = _fix(ctx.macro, MacroKey.MORTGAGE_2Y_FIX, ctx.year)
    q5 = _fix(ctx.macro, MacroKey.MORTGAGE_5Y_FIX, ctx.year)
    if m.rate_type == "fixed" and m.fixed_until is not None:
        days_left = (dates.parse(m.fixed_until) - ctx.today).days
        if days_left > DEAL_WINDOW_DAYS:
            return None
        if days_left >= 0:
            kind, deadline, keep_now = "fix_mortgage", m.fixed_until, svr
        else:
            kind, keep_now = "remortgage", max(m.rate_pct, svr)
    elif m.rate_type == "fixed":
        return None
    else:
        kind, keep_now = "remortgage", m.rate_pct
        if keep_now < min(q2, q5) + REMORTGAGE_MIN_GAP:
            return None
    starts = ctx.periods(MORTGAGE_HORIZON)
    if not starts:
        return None
    balances = [p.mortgage_balance if p.mortgage_balance > 0 else m.balance for p in ctx.twins] or [m.balance]
    r = rank_mortgage(ctx.macro, starts, balances, m.balance, m.years_left, q2, q5, keep_now, bank_now)
    best = r.best
    impact, worst = r.impact[best], r.worst[best]
    if impact <= 0:
        return None

    action = OPTION_LABEL[best]
    if kind == "fix_mortgage":
        headline = f"Your deal ends in {days_left} days"
        e1 = _ev(
            f"Your fixed rate of {pct(m.rate_pct)} ends in {days_left} days. "
            f"Then you move to the standard rate of about {pct(svr)}.",
            {"current_rate": pct_value(m.rate_pct), "days_left": float(days_left), "svr_rate": pct_value(svr)},
            source_ref(ctx.macro, MacroKey.BANK_RATE, ctx.year),
        )
    else:
        headline = f"You pay {pct(keep_now)} on your mortgage"
        e1 = _ev(
            f"You pay {pct(keep_now)} on a {gbp(m.balance)} mortgage with no fixed deal.",
            {"current_rate": pct_value(keep_now), "balance": money_value(m.balance)},
            _bank_ref(ctx.snapshot),
        )
    e2 = _ev(
        f"Today a 2-year fix is {pct(q2)} and a 5-year fix is {pct(q5)}.",
        {"rate_2y": pct_value(q2), "rate_5y": pct_value(q5), "years_2": 2.0, "years_5": 5.0},
        source_ref(ctx.macro, MacroKey.MORTGAGE_5Y_FIX, ctx.year),
    )
    worst_txt = (
        f"and {gbp(worst)} a year in the worst period" if worst >= 0 else f"but cost {gbp(worst)} a year more in the worst"
        " period"
    )
    e3 = _ev(
        f"We tested {len(ctx.twins) or 1} people like you in {len(starts)} similar past periods. "
        f"“{action}” saved {gbp(impact)} a year on average against doing nothing, {worst_txt}.",
        {
            "twins": float(len(ctx.twins) or 1),
            "periods": float(len(starts)),
            "impact": money_value(impact),
            "worst": money_value(worst),
            **({"years": float(FIX_YEARS[best])} if best in FIX_YEARS else {}),
        },
    )
    sources = [
        *_refs(ctx.macro, ctx.year, [MacroKey.BANK_RATE, MacroKey.MORTGAGE_2Y_FIX, MacroKey.MORTGAGE_5Y_FIX]),
        _bank_ref(ctx.snapshot),
    ]
    return _move(
        ctx,
        kind,
        kind,
        action,
        headline,
        impact,
        worst,
        r.confidence,
        confidence_label(r.confidence),
        [e1, e2, e3],
        sources,
        _options(best, [*MORTGAGE_OPTIONS, "keep"]),
        MORTGAGE_TEST,
        "interest-rates",
        deadline,
    )


# ---------- savings ----------


def savings_gain(macro: MacroTable, start: int, amount: float, user_now: float, best_now: float, year: int,
                 horizon: int = SAVINGS_HORIZON) -> float:
    """GBP per year from moving `amount` to a best-buy account, with the rate changes seen from `start`."""
    total = 0.0
    for t in range(horizon):
        user = max(0.0, user_now + _savings_avg(macro, start + t) - _savings_avg(macro, start))
        best = max(0.0, best_now + _best_savings(macro, start + t) - _best_savings(macro, start))
        total += amount * (best - user) / 100
    return total / horizon


def _savings(ctx: Context) -> Candidate | None:
    amount = savings_total(ctx.snapshot)
    if amount < MIN_SAVINGS:
        return None
    measured = savings_rate_pct(ctx.snapshot, ctx.today)
    user_now = measured if measured is not None else _savings_avg(ctx.macro, ctx.year)
    best_now = _best_savings(ctx.macro, ctx.year)
    if best_now <= user_now:
        return None
    starts = ctx.periods(SAVINGS_HORIZON)
    if not starts:
        return None
    user = [savings_gain(ctx.macro, s, amount, user_now, best_now, ctx.year) for s in starts]
    impact, worst = float(np.mean(user)), float(min(user))
    if impact <= 0:
        return None
    grid = _grid(
        ctx, starts, lambda p: p.savings if p.savings > 0 else amount,
        lambda a, s: savings_gain(ctx.macro, s, a, user_now, best_now, ctx.year),
    )
    conf = float((grid > 0).mean())
    rate_word = "earning about" if measured is not None else "probably earning about"
    e1 = _ev(
        f"You have {gbp(amount)} in savings {rate_word} {pct(user_now)} a year.",
        {"savings": money_value(amount), "rate": pct_value(user_now)},
        _bank_ref(ctx.snapshot),
    )
    e2 = _ev(
        f"Easy-access accounts pay up to about {pct(best_now)} today.",
        {"best_rate": pct_value(best_now)},
        source_ref(ctx.macro, MacroKey.SAVINGS_RATE, ctx.year) or source_ref(ctx.macro, MacroKey.BANK_RATE, ctx.year),
    )
    e3 = _ev(
        f"In {len(starts)} similar past periods, moving earned {gbp(impact)} a year more on average, "
        f"and {gbp(worst)} a year {'more' if worst >= 0 else 'less'} in the worst period.",
        {"periods": float(len(starts)), "impact": money_value(impact), "worst": money_value(worst)},
    )
    return _move(
        ctx, "move_savings", "move_savings", "Move your savings to a better rate",
        f"Your savings could earn {gbp(impact)} more a year",
        impact, worst, conf, confidence_label(conf), [e1, e2, e3],
        [*_refs(ctx.macro, ctx.year, [MacroKey.SAVINGS_RATE, MacroKey.BANK_RATE]), _bank_ref(ctx.snapshot)],
        _options("switch", ["keep"]), SAVINGS_TEST, "compound-interest",
    )


# ---------- energy ----------


def _energy(ctx: Context) -> Candidate | None:
    e = ctx.snapshot.energy
    if e is None or e.monthly_cost <= 0:
        return None
    days: int | None = None
    if e.fixed_until is not None:
        days = (dates.parse(e.fixed_until) - ctx.today).days
        if days > ENERGY_WINDOW_DAYS:
            return None
    annual = e.monthly_cost * 12
    starts = ctx.periods(ONE_YEAR + 1)
    if not starts:
        return None

    def gain(amount: float, s: int) -> float:
        return amount * _v(ctx.macro, MacroKey.ENERGY_PRICE_CHANGE, s + 1, 0.0) / 100

    user = [gain(annual, s) for s in starts]
    impact, worst = float(np.mean(user)), float(min(user))
    if impact <= 0:
        return None
    rose = sum(1 for g in user if g > 0)
    conf = rose / len(user)
    cap = _v(ctx.macro, MacroKey.ENERGY_TARIFF, ctx.year, 0.0)
    if days is not None and days >= 0:
        e1 = _ev(
            f"You pay {gbp(e.monthly_cost)} a month for energy. Your fixed price ends in {days} days.",
            {"monthly": money_value(e.monthly_cost), "days_left": float(days)},
            _bank_ref(ctx.snapshot),
        )
    else:
        e1 = _ev(
            f"You pay {gbp(e.monthly_cost)} a month for energy on a price that can change.",
            {"monthly": money_value(e.monthly_cost)},
            _bank_ref(ctx.snapshot),
        )
    if cap > 0:
        e2 = _ev(
            f"A typical home pays {gbp(cap)} a year under the price cap.",
            {"typical": money_value(cap)},
            source_ref(ctx.macro, MacroKey.ENERGY_TARIFF, ctx.year),
        )
    else:
        e2 = _ev(f"That is about {gbp(annual)} a year.", {"annual": money_value(annual)})
    e3 = _ev(
        f"In {len(starts)} similar past periods, prices rose the next year in {rose} of them. "
        f"Fixing saved {gbp(impact)} a year on average.",
        {"periods": float(len(starts)), "rose": float(rose), "impact": money_value(impact)},
        source_ref(ctx.macro, MacroKey.ENERGY_PRICE_CHANGE, ctx.year),
    )
    deadline = e.fixed_until if days is not None and days >= 0 else None
    return _move(
        ctx, "switch_energy", "switch_energy", "Fix your energy price",
        "Your energy price can go up" if deadline is None else f"Your energy deal ends in {days} days",
        impact, worst, conf, confidence_label(conf), [e1, e2, e3],
        [*_refs(ctx.macro, ctx.year, [MacroKey.ENERGY_TARIFF, MacroKey.ENERGY_PRICE_CHANGE]), _bank_ref(ctx.snapshot)],
        _options("fix", ["keep"]), ENERGY_TEST, "inflation", deadline,
    )


# ---------- debt ----------


def card_rate_pct(snapshot: FinanceSnapshot, today: dates.date) -> float | None:
    """Rate on cards and loans from interest charged in the last year. None without charges."""
    ids = {a.id for a in snapshot.accounts if a.kind in ("credit", "loan")}
    debt = debt_total(snapshot)
    start = dates.add_days(today, -365)
    charged = -sum(
        t.amount
        for t in snapshot.transactions
        if t.account_id in ids and t.amount < 0 and "interest" in t.description.lower()
        and start < dates.parse(t.date) <= today
    )
    if debt <= 0 or charged <= 0:
        return None
    return round(charged / debt * 100, 2)


def monthly_surplus(snapshot: FinanceSnapshot, today: dates.date) -> float:
    inc = detect_salary(snapshot.transactions)
    return round((inc.monthly_net if inc else 0.0) - monthly_spend(snapshot, today), 2)


def _debt(ctx: Context) -> Candidate | None:
    debt = debt_total(ctx.snapshot)
    if debt < MIN_DEBT:
        return None
    spend = monthly_spend(ctx.snapshot, ctx.today)
    spare = savings_total(ctx.snapshot) - SAFETY_MONTHS * spend
    surplus = monthly_surplus(ctx.snapshot, ctx.today)
    from_savings = spare > 0
    if from_savings:
        amount = min(debt, spare)  # capped at the debt
        share = 1.0
    else:
        monthly = surplus if surplus > 0 else PAYDOWN_MONTHLY
        amount = min(debt, 12 * monthly)
        share = 0.5  # paid down over the year: about half the amount is cleared on average
    measured = card_rate_pct(ctx.snapshot, ctx.today)
    card_now = measured if measured is not None else _card(ctx.macro, ctx.year)
    sav_now = savings_rate_pct(ctx.snapshot, ctx.today) or _savings_avg(ctx.macro, ctx.year)
    starts = ctx.periods(ONE_YEAR + 1)
    if not starts:
        return None

    def gain(a: float, s: int) -> float:
        card = max(0.0, card_now + _card(ctx.macro, s + 1) - _card(ctx.macro, s))
        sav = max(0.0, sav_now + _savings_avg(ctx.macro, s + 1) - _savings_avg(ctx.macro, s)) if from_savings else 0.0
        return a * share * (card - sav) / 100

    user = [gain(amount, s) for s in starts]
    impact, worst = float(np.mean(user)), float(min(user))
    if impact <= 0:
        return None
    grid = _grid(ctx, starts, lambda p: min(p.debt, amount) if p.debt > 0 else amount, gain)
    conf = float((grid > 0).mean())
    e1 = _ev(
        f"You owe {gbp(debt)} on cards and loans at about {pct(card_now)} a year.",
        {"debt": money_value(debt), "card_rate": pct_value(card_now)},
        _bank_ref(ctx.snapshot) if measured is not None else source_ref(ctx.macro, MacroKey.CARD_RATE, ctx.year),
    )
    if from_savings:
        e2 = _ev(
            f"Your savings earn about {pct(sav_now)}. Paying {gbp(amount)} from savings still leaves "
            f"{gbp(savings_total(ctx.snapshot) - amount)} for emergencies.",
            {"savings_rate": pct_value(sav_now), "amount": money_value(amount),
             "left": money_value(savings_total(ctx.snapshot) - amount)},
            _bank_ref(ctx.snapshot),
        )
        action = f"Pay off {gbp(amount)} of card debt from savings"
    elif surplus > 0:
        e2 = _ev(
            f"You have about {gbp(surplus)} a month left after spending. That clears {gbp(amount)} in a year.",
            {"surplus": money_value(surplus), "amount": money_value(amount)},
            _bank_ref(ctx.snapshot),
        )
        action = f"Put {gbp(surplus)} a month towards your card"
    else:
        e2 = _ev(
            f"You spend about {gbp(surplus)} a month more than you earn. Cutting {gbp(PAYDOWN_MONTHLY)} a month "
            f"and paying it to the card clears {gbp(amount)} in a year.",
            {"over": money_value(surplus), "cut": money_value(PAYDOWN_MONTHLY), "amount": money_value(amount)},
            _bank_ref(ctx.snapshot),
        )
        action = f"Cut {gbp(PAYDOWN_MONTHLY)} a month and pay it to your card"
    e3 = _ev(
        f"This saves about {gbp(impact)} a year in interest, and {gbp(worst)} a year in the worst of "
        f"{len(starts)} similar past periods.",
        {"impact": money_value(impact), "worst": money_value(worst), "periods": float(len(starts))},
        source_ref(ctx.macro, MacroKey.CARD_RATE, ctx.year),
    )
    return _move(
        ctx, "pay_off_debt", "pay_off_debt", action, f"Your card costs you {gbp(impact)} a year",
        impact, worst, conf, confidence_label(conf), [e1, e2, e3],
        [*_refs(ctx.macro, ctx.year, [MacroKey.CARD_RATE, MacroKey.SAVINGS_RATE]), _bank_ref(ctx.snapshot)],
        _options("pay_off", ["keep"]), ctx.matched_test_period(), "debt",
    )


# ---------- emergency fund ----------


def _emergency(ctx: Context) -> Candidate | None:
    spend = monthly_spend(ctx.snapshot, ctx.today)
    if spend <= 0:
        return None
    cash = max(0.0, liquid(ctx.snapshot))
    target = EMERGENCY_MONTHS * spend
    gap = target - cash
    if gap <= 0:
        return None
    starts = ctx.periods(ONE_YEAR + 1)
    if not starts:
        return None
    rng = np.random.default_rng(ctx.seed)
    shock = min(gap, SHOCK_COST)

    def prob(s: int) -> float:
        return min(1.0, SHOCK_BASE_PROB + _v(ctx.macro, MacroKey.UNEMPLOYMENT, s, 5.0) / 100)

    def cost(s: int) -> float:
        return shock * _card(ctx.macro, s) / 100

    user = [prob(s) * cost(s) for s in starts]
    impact = float(np.mean(user))
    hits = rng.random((ctx.n_twins, len(starts))) < np.array([prob(s) for s in starts])[None, :]
    conf = float(hits.mean())
    months = round(cash / spend, 1)
    card_now = _card(ctx.macro, ctx.year)
    e1 = _ev(
        f"Your cash and savings cover {months:g} months of spending.",
        {"months": months, "cash": money_value(cash)},
        _bank_ref(ctx.snapshot),
    )
    e2 = _ev(
        f"You spend about {gbp(spend)} a month, so {EMERGENCY_MONTHS} months is {gbp(target)}.",
        {"spend": money_value(spend), "months_target": float(EMERGENCY_MONTHS), "target": money_value(target)},
        _bank_ref(ctx.snapshot),
    )
    e3 = _ev(
        f"A surprise bill of {gbp(shock)} on a card at {pct(card_now)} costs about "
        f"{gbp(shock * card_now / 100)} a year in interest.",
        {"shock": money_value(shock), "card_rate": pct_value(card_now), "cost": money_value(shock * card_now / 100)},
        source_ref(ctx.macro, MacroKey.CARD_RATE, ctx.year),
    )
    return _move(
        ctx, "build_emergency_fund", "build_emergency_fund", f"Build a safety net of {gbp(target)}",
        f"Your safety net covers {months:g} months",
        impact, 0.0, conf, confidence_label(conf), [e1, e2, e3],
        [*_refs(ctx.macro, ctx.year, [MacroKey.CARD_RATE, MacroKey.UNEMPLOYMENT]), _bank_ref(ctx.snapshot)],
        _options("save", ["keep"]), ctx.matched_test_period(), "emergency-fund",
    )


# ---------- subscriptions ----------


_PER = {"weekly": "a week", "monthly": "a month", "quarterly": "a quarter", "yearly": "a year"}


def _subscription(ctx: Context) -> Candidate | None:
    subs = detect_subscriptions(ctx.snapshot.transactions, ctx.today)
    risen = [s for s in subs if s.price_rise is not None]
    if not risen:
        return None
    s = max(risen, key=lambda x: (x.monthly_cost, x.id))
    assert s.price_rise is not None
    impact = s.monthly_cost * 12
    total = sum(x.monthly_cost for x in subs)
    names = digit_facts(s.merchant)
    e1 = _ev(
        f"{s.merchant} went up from {gbp(s.price_rise.from_amount, True)} to "
        f"{gbp(s.price_rise.to_amount, True)} {_PER[s.cadence]}.",
        {"from": money_value(s.price_rise.from_amount, True), "to": money_value(s.price_rise.to_amount, True), **names},
        _bank_ref(ctx.snapshot),
    )
    e2 = _ev(
        f"You pay {gbp(total)} a month for {len(subs)} subscriptions.",
        {"monthly_total": money_value(total), "count": float(len(subs))},
        _bank_ref(ctx.snapshot),
    )
    e3 = _ev(
        f"Cancelling {s.merchant} saves {gbp(impact)} a year.",
        {"impact": money_value(impact), **names},
    )
    return _move(
        ctx, "cancel_subscription", f"cancel_subscription-{_slug(s.merchant)}", f"Cancel {s.merchant}",
        f"{s.merchant} put its price up", impact, impact, 1.0, SURE_LABEL, [e1, e2, e3],
        [_bank_ref(ctx.snapshot)], _options("cancel", ["keep"]), ctx.matched_test_period(), "budgeting",
    )


# ---------- budget ----------


def _budget(ctx: Context) -> Candidate | None:
    months = full_months_before(ctx.today, 7)
    by_month = {m: by_category(ctx.snapshot.transactions, m) for m in months}
    if not by_month[months[-1]]:
        return None
    last, before, history = months[-1], months[-4:-1], months[:-1]
    best: tuple[float, str, float, float] | None = None
    for c in CUT_CATEGORIES:
        spent = by_month[last].get(c, (0.0, 0))[0]  # type: ignore[call-overload]
        avg = float(np.mean([by_month[m].get(c, (0.0, 0))[0] for m in before]))  # type: ignore[call-overload]
        excess = spent - avg
        if avg >= CUT_MIN_AVERAGE and excess >= max(CUT_MIN_GBP, CUT_MIN_SHARE * avg) and (best is None or excess > best[0]):
            best = (excess, c, spent, avg)
    if best is None:
        return None
    excess, cat, spent, avg = best
    impact = excess * 12
    under = sum(1 for m in history if by_month[m].get(cat, (0.0, 0))[0] <= avg)  # type: ignore[call-overload]
    conf = under / len(history)
    name = category_label(cat).lower()  # type: ignore[arg-type]
    e1 = _ev(f"You spent {gbp(spent)} on {name} last month.", {"spent": money_value(spent)}, _bank_ref(ctx.snapshot))
    e2 = _ev(
        f"In the 3 months before, you spent {gbp(avg)} a month on average.",
        {"months": 3.0, "average": money_value(avg)},
        _bank_ref(ctx.snapshot),
    )
    e3 = _ev(
        f"Going back to {gbp(avg)} a month saves {gbp(impact)} a year. "
        f"You spent that or less in {under} of the last {len(history)} months.",
        {"average": money_value(avg), "impact": money_value(impact), "under": float(under),
         "history": float(len(history))},
    )
    return _move(
        ctx, "cut_budget", f"cut_budget-{cat}", f"Cut {name} to {gbp(avg)} a month",
        f"You spent {gbp(excess)} more than usual on {name}", impact, 0.0, conf,
        f"You spent this little in {under} of the last {len(history)} months",
        [e1, e2, e3], [_bank_ref(ctx.snapshot)], _options("cut", ["keep"]), ctx.matched_test_period(), "budgeting",
    )


# ---------- fallback ----------


def _fallback(ctx: Context) -> Candidate:
    spend = monthly_spend(ctx.snapshot, ctx.today)
    cash = max(0.0, liquid(ctx.snapshot))
    months = round(cash / spend, 1) if spend > 0 else 0.0
    sav = savings_total(ctx.snapshot)
    evidence = [
        _ev(f"Your cash and savings cover {months:g} months of spending.", {"months": months}, _bank_ref(ctx.snapshot)),
        _ev(f"You have {gbp(sav)} in savings.", {"savings": money_value(sav)}, _bank_ref(ctx.snapshot)),
        _ev("We found no bill, rate or debt that needs action now.", {}),
    ]
    return _move(
        ctx, "build_emergency_fund", "build_emergency_fund", "Keep your safety net topped up",
        "Nothing urgent this month", 0.0, 0.0, 0.0, "Nothing urgent. Your money looks on track",
        evidence, [_bank_ref(ctx.snapshot)], _options("save", ["keep"]), None, "emergency-fund",
    )


BUILDERS: tuple[Callable[[Context], Candidate | None], ...] = (
    _mortgage,
    _debt,
    _savings,
    _energy,
    _emergency,
    _subscription,
    _budget,
)


def candidates(ctx: Context) -> list[Candidate]:
    out = [c for c in (b(ctx) for b in BUILDERS) if c is not None and c.move.impact_per_year > 0]

    def key(c: Candidate) -> tuple[float, int, int]:
        days = c.move.days_left if c.move.days_left is not None else 10**6
        return (-round(c.score, 6), days, KIND_ORDER.index(c.move.kind))

    return sorted(out, key=key)


def build_context(snapshot: FinanceSnapshot, macro: MacroTable, today: dates.date, seed: int = 0) -> Context:
    year = min(today.year, latest_year(macro))
    prof, _ = profile(snapshot, today)
    twins = nearest_twins(prof, macro, year)[:K_TWINS]
    return Context(snapshot=snapshot, macro=macro, today=today, year=year, profile=prof, seed=seed, twins=twins)


def next_move(snapshot: FinanceSnapshot, macro: MacroTable, today: dates.date, seed: int = 0) -> NextMoveResponse:
    """ONE top move and up to 2 runners-up. `generated_at` is a placeholder: the API sets server time."""
    ctx = build_context(snapshot, macro, today, seed)
    ranked = candidates(ctx)
    if not ranked:
        ranked = [_fallback(ctx)]
    top = ranked[0].move
    backtest = mortgage_backtest(macro, ctx.year) if top.kind in ("fix_mortgage", "remortgage") else None
    return NextMoveResponse(
        meta=finance_meta(snapshot),
        top=top,
        runners_up=[c.move for c in ranked[1:3]],
        backtest=backtest,
        generated_at=f"{dates.iso(today)}T00:00:00Z",
    )


# ---------- Test it ----------


def option_policy(move: Move, option_id: str) -> dict[str, str]:
    """Sim policy for one option of `move` (lifeline_sim play_scenario). Every option of a move uses the same
    tag key, so the event sets match across options. Mortgage moves also set the deal end year."""
    if option_id not in {o.id for o in move.options}:
        raise ValueError(f"unknown option {option_id} for move {move.id}")
    policy = {MOVE_TAG[move.kind]: option_id}
    if move.kind in ("fix_mortgage", "remortgage") and move.test_period is not None:
        policy[POLICY_DEAL_END] = str(move.test_period.start + 1)
    return policy


# ---------- backtest ----------

BACKTEST_PROFILE_BALANCE = 180_000.0
BACKTEST_YEARS_LEFT = 25
BACKTEST_FIRST_YEAR = 1995
BACKTEST_BASELINE = "fix_2y"


@dataclass(frozen=True)
class BacktestRow:
    year: int
    recommended: str
    realised_best: str


def mortgage_backtest_rows(macro: MacroTable, upto: int) -> list[BacktestRow]:
    """Walk-forward: for each past deal-end year Y with a full 5-year window of data, recommend with only the
    periods that ended before Y, then compare with the option that was cheapest on the real path from Y."""
    years = sorted(macro.years(MacroKey.BANK_RATE))
    if not years:
        return []
    last = min(years[-1], upto)
    rows: list[BacktestRow] = []
    for y in range(max(BACKTEST_FIRST_YEAR, years[0]), last - MORTGAGE_HORIZON + 2):
        pool = candidate_starts(macro, before=y, horizon=MORTGAGE_HORIZON)
        starts = [m.year for m in similar_years(macro, y, K_PERIODS, candidates=pool)]
        if not starts:
            continue
        bank = _bank(macro, y)
        q2, q5 = _fix(macro, MacroKey.MORTGAGE_2Y_FIX, y), _fix(macro, MacroKey.MORTGAGE_5Y_FIX, y)
        bal = [BACKTEST_PROFILE_BALANCE]
        rec = rank_mortgage(macro, starts, bal, bal[0], BACKTEST_YEARS_LEFT, q2, q5, bank + VARIABLE_MARGIN, bank)
        real = rank_mortgage(macro, [y], bal, bal[0], BACKTEST_YEARS_LEFT, q2, q5, bank + VARIABLE_MARGIN, bank)
        realised = max(MORTGAGE_OPTIONS, key=lambda o: (real.impact[o], -MORTGAGE_OPTIONS.index(o)))
        rows.append(BacktestRow(year=y, recommended=rec.best, realised_best=realised))
    return rows


def mortgage_backtest(macro: MacroTable, upto: int) -> NextMoveBacktest:
    rows = mortgage_backtest_rows(macro, upto)
    n = len(rows)
    first = rows[0].year if rows else BACKTEST_FIRST_YEAR
    lastrow = rows[-1].year if rows else BACKTEST_FIRST_YEAR
    return NextMoveBacktest(
        method=(
            f"Walk-forward backtest over past deal-end years {first}-{lastrow}: the engine picks fix 2 years, "
            "fix 5 years or tracker using only earlier periods, then we check which was cheapest over the next "
            "5 years on the real rate path."
        ),
        n=n,
        hit_rate=round(sum(r.recommended == r.realised_best for r in rows) / n, 4) if n else 0.0,
        baseline="Always fix for 2 years",
        baseline_hit_rate=round(sum(r.realised_best == BACKTEST_BASELINE for r in rows) / n, 4) if n else 0.0,
    )
