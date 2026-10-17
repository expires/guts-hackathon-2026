"""Next Move engine (ADR 0018, ADR 0020): "What is my next money move?" Pure: no I/O, no clock, no global RNG.

Inputs: the user's FinanceSnapshot, the MacroTable, `today`, and a seed (used only by the emergency
fund shock draw).

Method for each candidate move:
1. The move is a candidate only when the data supports it (see the `_<kind>` builders).
2. Twins: the K_TWINS nearest people to the user's profile in the synthetic population (twins.py).
   Matched periods: the K_PERIODS past start years whose macro state is most like today (periods.py),
   with a full horizon of data that ended before today (no look-ahead).
3. Each (twin, period) pair is simulated: gain = GBP per year vs doing nothing. Today's quoted rates
   are known; the past period supplies how rates and prices then CHANGED (delta method).
4. impact_per_year = mean gain for the user's own amounts over the matched periods.
   worst_case_per_year = the minimum over the matched periods AND the kind's stress period (ADR 0020).
   confidence = share of (twin, matched period) pairs where the move beat doing nothing. For a move with
   several options (mortgage), confidence = share of (twin, period) pairs, stress period included, where the
   recommended option was the best of the options (ADR 0023). Options are chosen by regret (ADR 0020).
5. Rank: score = (impact + 0.5 * min(0, worst)) * confidence. Ties: nearer deadline, then kind order.
6. Evidence (exactly 3): the user's situation, the matched periods, the stress period. Every number in
   a text is a value in its facts.

Labelled assumptions (no data source): VARIABLE_MARGIN (same as lifeline_sim.params), TRACKER_MARGIN,
BEST_SAVINGS_*, SAFETY_MONTHS, PAYDOWN_MONTHLY, SHOCK_*, CUT_* thresholds.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from lifeline_contracts.domain import DecisionProfile, SourceRef
from lifeline_contracts.finance import Category, FinanceSnapshot
from lifeline_contracts.investing import IsaBacktestRequest, ReturnSeries
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
from lifeline_engine.decision import _twins as nearest_twins
from lifeline_engine.decision import candidate_starts, mortgage_interest
from lifeline_engine.finance import monthly_payment
from lifeline_engine.macro_access import latest_year, source_ref, value_or
from lifeline_engine.money import dates, finance_meta
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
from lifeline_engine.wording import best_choice_label, confidence_label
from lifeline_eval.isa_backtest import (
    NAMED_PERIODS,
    PERIOD_LABELS,
    PERIODS,
    isa_backtest,
    period_drawdowns,
    weights_from_holdings,
)

FloatArray = NDArray[np.float64]

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
PAYDOWN_MONTHLY = 100.0  # extra card payment per month when there is no spare money (cut spending to fund it)
EMERGENCY_MONTHS = 3
SHOCK_COST = 1_500.0  # a typical unexpected bill (boiler, car)
SHOCK_BASE_PROB = 0.2  # yearly chance of such a bill, plus the unemployment rate of the period
CUT_MIN_GBP = 30.0
CUT_MIN_SHARE = 0.2
CUT_MIN_AVERAGE = 50.0  # ignore categories with a usual spend under £50 a month
CUT_CATEGORIES: tuple[Category, ...] = (
    "eating_out",
    "shopping",
    "entertainment",
    "travel",
    "personal_care",
    "transport",
    "groceries",
)


@dataclass(frozen=True)
class StressPeriod:
    start: int
    end: int
    name: str

    @property
    def test_period(self) -> TestPeriod:
        return TestPeriod(start=self.start, end=self.end, label=f"{self.start}-{self.end} {self.name} (stress test)")

    def facts(self) -> dict[str, float]:
        return {"stress_start": float(self.start), "stress_end": float(self.end)}

    @property
    def years(self) -> int:
        return self.end - self.start + 1

    @property
    def text(self) -> str:
        return f"the {self.start}-{self.end} {self.name}"


# Standard stress period per move kind (ADR 0020).
STRESS: dict[MoveKind, StressPeriod] = {
    "fix_mortgage": StressPeriod(2021, 2023, "rate shock"),
    "remortgage": StressPeriod(2021, 2023, "rate shock"),
    "move_savings": StressPeriod(2009, 2011, "low-rate years"),
    "switch_energy": StressPeriod(2021, 2023, "energy price shock"),
    "pay_off_debt": StressPeriod(2008, 2010, "recession"),
    "build_emergency_fund": StressPeriod(2008, 2010, "recession"),
}

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
    "spread_isa",
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
    "spread_isa": "isa_mix",  # not testable in the sim: spread_isa moves carry no test_period
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
    "spread": "Spread your investments",
}
OPTION_NUMBERS: dict[str, dict[str, float]] = {"fix_5y": {"fix_years": 5.0}, "fix_2y": {"fix_years": 2.0}}


# ---------- small helpers ----------


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


def _svr(macro: MacroTable, year: int) -> float:
    """Standard variable (revert-to) rate: BoE series, else Bank Rate + VARIABLE_MARGIN."""
    return _v(macro, MacroKey.MORTGAGE_SVR, year, _bank(macro, year) + VARIABLE_MARGIN)


def _tracker(macro: MacroTable, year: int) -> float:
    """2-year tracker rate: BoE series, else Bank Rate + TRACKER_MARGIN."""
    return _v(macro, MacroKey.MORTGAGE_TRACKER, year, _bank(macro, year) + TRACKER_MARGIN)


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


def period_spans(starts: Sequence[int], horizon: int) -> list[tuple[int, int]]:
    """Windows [s, s + horizon - 1], merged when they overlap or touch. Sorted."""
    spans: list[tuple[int, int]] = []
    for s in sorted(starts):
        e = s + horizon - 1
        if spans and s <= spans[-1][1] + 1:
            spans[-1] = (spans[-1][0], max(spans[-1][1], e))
        else:
            spans.append((s, e))
    return spans


def spans_text(starts: Sequence[int], horizon: int) -> tuple[str, dict[str, float]]:
    """'2005-2011, 2017-2022' and the facts for those years."""
    spans = period_spans(starts, horizon)
    facts: dict[str, float] = {}
    parts: list[str] = []
    for i, (a, b) in enumerate(spans, 1):
        facts[f"period_{i}_start"] = float(a)
        facts[f"period_{i}_end"] = float(b)
        parts.append(f"{a}-{b}" if b != a else f"{a}")
    return ", ".join(parts), facts


def _better(x: float, unit: str = "a year") -> str:
    return f"saved {gbp(x)} {unit}" if x >= 0 else f"cost {gbp(x)} {unit} more"


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
    returns: ReturnSeries | None = None
    _periods: dict[int, list[int]] = field(default_factory=dict)

    def periods(self, horizon: int) -> list[int]:
        """K_PERIODS past start years most like `year`, whose `horizon`-year window ended before `year`."""
        if horizon not in self._periods:
            pool = candidate_starts(self.macro, before=self.year, horizon=horizon)
            self._periods[horizon] = [m.year for m in similar_years(self.macro, self.year, K_PERIODS, candidates=pool)]
        return self._periods[horizon]

    def matched_test_period(self) -> TestPeriod:
        starts = self.periods(3)
        s = starts[0] if starts else 2021
        return TestPeriod(start=s, end=s + 2, label=f"{s}-{s + 2}, the past period most like today")

    def grid(self, starts: Sequence[int], amount_of: Callable[[Person], float], default: float,
             gain: Callable[[float, int], float]) -> FloatArray:
        """gain(amount, start) for every (twin, period) pair. Shape (twins, periods)."""
        amounts = [amount_of(p) for p in self.twins] or [default]
        return np.array([[gain(a, s) for s in starts] for a in amounts], dtype=np.float64)


@dataclass(frozen=True)
class Candidate:
    move: Move
    score: float


def score(impact: float, worst: float, confidence: float) -> float:
    return (impact + 0.5 * min(0.0, worst)) * confidence


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
    # The recommended option's label is the action, word for word (V5).
    options = [o.model_copy(update={"label": action}) if o.is_recommended else o for o in options]
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
    return Candidate(move=move, score=score(impact, worst, confidence))


def _options(recommended: str, others: Sequence[str]) -> list[MoveOption]:
    ids = [recommended, *[o for o in others if o != recommended]][:4]
    return [MoveOption(id=o, label=OPTION_LABEL[o], is_recommended=o == recommended) for o in ids]


# ---------- mortgage ----------


def mortgage_paths(
    macro: MacroTable, start: int, q2: float, q5: float, keep_now: float, tracker_now: float, horizon: int
) -> dict[str, list[float]]:
    """Rate path (percent per year) for each option, from today's quotes plus the changes seen from `start`.

    - fix_2y: today's 2-year rate, then re-fix every 2 years at today's rate + the change in 2-year rates.
    - fix_5y: today's 5-year rate for 5 years, then re-fix the same way.
    - tracker: today's tracker rate + the change in tracker rates (BoE series, else Bank Rate + TRACKER_MARGIN).
    - keep: the rate you move to (standard variable or your current variable rate) + the change in the
      standard variable rate (BoE series, else Bank Rate + VARIABLE_MARGIN).
    """

    def d(key: MacroKey, t: int) -> float:
        return _fix(macro, key, start + t) - _fix(macro, key, start)

    def dt(t: int) -> float:
        return _tracker(macro, start + t) - _tracker(macro, start)

    def dv(t: int) -> float:
        return _svr(macro, start + t) - _svr(macro, start)

    return {
        "fix_2y": [max(0.0, q2 + d(MacroKey.MORTGAGE_2Y_FIX, 2 * (t // 2))) for t in range(horizon)],
        "fix_5y": [max(0.0, q5 + d(MacroKey.MORTGAGE_5Y_FIX, 5 * (t // 5))) for t in range(horizon)],
        "tracker": [max(0.0, tracker_now + dt(t)) for t in range(horizon)],
        "keep": [max(0.0, keep_now + dv(t)) for t in range(horizon)],
    }


def choose_by_regret(
    options: Sequence[str],
    matched: Mapping[str, Sequence[float]],
    stress: Mapping[str, float] | None = None,
    weight: float = 0.5,
) -> tuple[str, dict[str, float]]:
    """ADR 0020 amendment. `matched[o]` = GBP/year vs doing nothing in each matched period; `stress[o]` = the same
    in the stress period. regret(o, p) = best option's gain in p - o's gain in p.
    score(o) = mean(matched[o]) - weight * max_p regret(o, p) over matched periods and the stress period.
    `weight` is the regret weight lambda (0.5 by default; ADR 0020 Amendment 2 sets it from affordability).
    Returns the highest-scoring option (ties: option order) and every score."""
    columns: list[dict[str, float]] = [
        {o: matched[o][i] for o in options} for i in range(min((len(matched[o]) for o in options), default=0))
    ]
    if stress:
        columns.append({o: stress[o] for o in options})
    scores: dict[str, float] = {}
    for o in options:
        expected = float(np.mean(matched[o])) if len(matched[o]) else 0.0
        regret = max((max(col.values()) - col[o] for col in columns), default=0.0)
        scores[o] = expected - weight * regret
    best = sorted(options, key=lambda o: (-scores[o], options.index(o)))[0]
    return best, scores


@dataclass(frozen=True)
class MortgageResult:
    best: str
    impact: dict[str, float]  # mean GBP/year vs keep over the matched periods, user's amounts
    worst: dict[str, float]  # min over matched periods and stress
    stress: dict[str, float]  # GBP/year vs keep in the stress period (empty when not given)
    confidence: float  # share of (twin, period) pairs, stress included, where best was the best option
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
    tracker_now: float,
    stress_start: int | None = None,
    horizon: int = MORTGAGE_HORIZON,
    options: Sequence[str] = MORTGAGE_OPTIONS,
    stress_horizon: int | None = None,
    regret_weight: float = 0.5,
) -> MortgageResult:
    """Matched periods use `horizon` years. The stress period uses `stress_horizon` years (default `horizon`),
    so the card's stress figure covers the same years that Test it replays."""
    s_h = stress_horizon or horizon
    paths = {("m", s): mortgage_paths(macro, s, q2, q5, keep_now, tracker_now, horizon) for s in starts}
    if stress_start is not None:
        paths[("s", stress_start)] = mortgage_paths(macro, stress_start, q2, q5, keep_now, tracker_now, s_h)
    years = {k: (horizon if k[0] == "m" else s_h) for k in paths}

    def gain_at(balance: float, key: tuple[str, int], o: str) -> float:
        keep_cost = mortgage_interest(balance, years_left, paths[key]["keep"])
        return (keep_cost - mortgage_interest(balance, years_left, paths[key][o])) / years[key]

    def gain(balance: float, s: int, o: str) -> float:
        return gain_at(balance, ("m", s), o)

    user = {o: [gain(user_balance, s, o) for s in starts] for o in options}
    stress = {o: gain_at(user_balance, ("s", stress_start), o) for o in options} if stress_start is not None else {}
    impact = {o: float(np.mean(user[o])) if user[o] else 0.0 for o in options}
    worst = {o: float(min([*user[o], *([stress[o]] if stress else [])], default=0.0)) for o in options}
    best, _ = choose_by_regret(options, user, stress, regret_weight)
    # ADR 0023: share of (twin, period) pairs, stress period included, where `best` was the best option.
    wins = total = 0
    for b in balances:
        for key in paths:
            total += 1
            g = {o: gain_at(b, key, o) for o in options}
            if all(g[best] >= g[o] for o in options):
                wins += 1
    return MortgageResult(best, impact, worst, stress, wins / total if total else 0.0, total)


AFFORD_STRESS_PP = 3.0  # ADR 0020 Amendment 2: lenders' affordability stress above the reversion rate
AFFORD_COMFORTABLE = 0.30  # ratio at or below: regret weight 0.5
AFFORD_STRETCHED = 0.45  # ratio at or above: regret weight 1.5
WEIGHT_COMFORTABLE = 0.5
WEIGHT_STRETCHED = 1.5


def regret_weight(ratio: float | None) -> float:
    """lambda = 0.5 at ratio <= 0.30, 1.5 at ratio >= 0.45, linear between. No detected income: 1.5 (cautious)."""
    if ratio is None:
        return WEIGHT_STRETCHED
    if ratio <= AFFORD_COMFORTABLE:
        return WEIGHT_COMFORTABLE
    if ratio >= AFFORD_STRETCHED:
        return WEIGHT_STRETCHED
    share = (ratio - AFFORD_COMFORTABLE) / (AFFORD_STRETCHED - AFFORD_COMFORTABLE)
    return WEIGHT_COMFORTABLE + share * (WEIGHT_STRETCHED - WEIGHT_COMFORTABLE)


@dataclass(frozen=True)
class Affordability:
    stressed_payment: float  # GBP per month at reversion rate + 3.0 points
    net_monthly_income: float | None
    ratio: float | None
    weight: float
    text: str
    facts: dict[str, float]


def affordability(balance: float, years_left: int, reversion_rate: float, snapshot: FinanceSnapshot) -> Affordability:
    """ADR 0020 Amendment 2. stressed_payment = monthly_payment(balance, reversion + 3.0, term);
    ratio = stressed_payment / net monthly income from detected salary credits; lambda from regret_weight."""
    stressed_rate = reversion_rate + AFFORD_STRESS_PP
    pay = monthly_payment(balance, stressed_rate, years_left)
    inc = detect_salary(snapshot.transactions)
    net = inc.monthly_net if inc is not None and inc.monthly_net > 0 else None
    ratio = pay / net if net is not None else None
    weight = regret_weight(ratio)
    facts: dict[str, float] = {
        "stressed_rate": pct_value(stressed_rate),
        "stressed_payment": money_value(pay),
        "regret_weight": round(weight, 4),
    }
    text = ""
    if ratio is not None and net is not None:
        ratio_pct = float(round(ratio * 100))
        facts |= {
            "net_monthly_income": money_value(net),
            "stressed_ratio_pct": ratio_pct,
            "stressed_ratio": round(ratio, 4),
        }
        text = (
            f" At {pct(stressed_rate)} your payment would be {gbp(pay)} a month, "
            f"{ratio_pct:.0f}% of your take-home pay."
        )
    return Affordability(pay, net, ratio, weight, text, facts)


def todays_rates_comparison(
    balance: float, years_left: int, q2: float, q5: float, tracker: float
) -> tuple[str, dict[str, float]]:
    """Engine-computed comparison of TODAY's quoted rates (BoE IUMBV42 5-year, IUMBV34 2-year, IUMBV48 tracker):
    yearly repayments from finance.monthly_payment on the user's balance and term. Not a forecast."""
    pay = {k: monthly_payment(balance, r, years_left) * 12 for k, r in (("2y", q2), ("5y", q5), ("tr", tracker))}
    d5 = pay["2y"] - pay["5y"]
    dt = pay["2y"] - pay["tr"]

    def rel(x: float) -> str:
        return f"{gbp(x)} a year less than" if x >= 0 else f"{gbp(x)} a year more than"

    text = (
        f"At today's rates on {gbp(balance)} over {years_left} years, a 5-year fix ({pct(q5)}) costs {rel(d5)} "
        f"a 2-year fix ({pct(q2)}), and a tracker ({pct(tracker)}) starts at {rel(dt)} the 2-year fix."
    )
    facts = {
        "balance": money_value(balance),
        "term_years": float(years_left),
        "rate_5y": pct_value(q5),
        "rate_2y": pct_value(q2),
        "rate_tracker": pct_value(tracker),
        "gap_5y_vs_2y": money_value(d5),
        "gap_tracker_vs_2y": money_value(dt),
        "years_5": 5.0,
        "years_2": 2.0,
    }
    return text, facts


def _mortgage(ctx: Context) -> Candidate | None:
    m = ctx.snapshot.mortgage
    if m is None or m.balance <= 0 or m.years_left <= 0:
        return None
    kind: MoveKind
    deadline: str | None = None
    days_left = 0
    tracker_now = _tracker(ctx.macro, ctx.year)
    svr = _svr(ctx.macro, ctx.year)
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
    stress = STRESS[kind]
    balances = [p.mortgage_balance if p.mortgage_balance > 0 else m.balance for p in ctx.twins] or [m.balance]
    aff = affordability(m.balance, m.years_left, svr, ctx.snapshot)
    r = rank_mortgage(
        ctx.macro, starts, balances, m.balance, m.years_left, q2, q5, keep_now, tracker_now, stress_start=stress.start,
        stress_horizon=stress.years, regret_weight=aff.weight,
    )
    best = r.best
    impact, worst, stressed = r.impact[best], r.worst[best], r.stress[best]
    if impact <= 0:
        return None

    action = OPTION_LABEL[best]
    cmp_text, cmp_facts = todays_rates_comparison(m.balance, m.years_left, q2, q5, tracker_now)
    if kind == "fix_mortgage":
        headline = f"Your deal ends in {days_left} days"
        e1 = _ev(
            f"Your fixed rate of {pct(m.rate_pct)} ends in {days_left} days. Then you move to about {pct(svr)}. "
            f"{cmp_text}{aff.text}",
            {"current_rate": pct_value(m.rate_pct), "days_left": float(days_left), "svr_rate": pct_value(svr),
             **cmp_facts, **aff.facts},
            source_ref(ctx.macro, MacroKey.MORTGAGE_5Y_FIX, ctx.year),
        )
    else:
        headline = f"You pay {pct(keep_now)} on your mortgage"
        e1 = _ev(
            f"You pay {pct(keep_now)} on your mortgage with no fixed deal. {cmp_text}{aff.text}",
            {"current_rate": pct_value(keep_now), **cmp_facts, **aff.facts},
            source_ref(ctx.macro, MacroKey.MORTGAGE_5Y_FIX, ctx.year),
        )
    spans, span_facts = spans_text(starts, MORTGAGE_HORIZON)
    names = OPTION_NUMBERS.get(best, {})
    e2 = _ev(
        f"We tested {len(ctx.twins) or 1} people like you in similar past periods ({spans}). "
        f"“{action}” {_better(impact)} on average against doing nothing.",
        {"twins": float(len(ctx.twins) or 1), "impact": money_value(impact), **span_facts, **names},
        source_ref(ctx.macro, MacroKey.BANK_RATE, ctx.year),
    )
    alt = max((o for o in MORTGAGE_OPTIONS if o != best), key=lambda o: (r.stress[o], o))
    alt_names = {f"alt_{k}": v for k, v in OPTION_NUMBERS.get(alt, {}).items()}
    s3 = (
        f"In {stress.text}, “{action}” {_better(stressed)} against doing nothing for a mortgage like yours; "
        f"“{OPTION_LABEL[alt]}” {_better(r.stress[alt])}. "
        "Test it replays your whole life in those years, so its totals can differ"
    )
    f3 = {
        "stress": money_value(stressed),
        "stress_alt": money_value(r.stress[alt]),
        **stress.facts(),
        **names,
        **alt_names,
    }
    e3 = _ev(f"{s3}.", f3, source_ref(ctx.macro, MacroKey.BANK_RATE, stress.start))
    sources = [
        *_refs(
            ctx.macro,
            ctx.year,
            [MacroKey.BANK_RATE, MacroKey.MORTGAGE_2Y_FIX, MacroKey.MORTGAGE_5Y_FIX, MacroKey.MORTGAGE_SVR,
             MacroKey.MORTGAGE_TRACKER],
        ),
        _bank_ref(ctx.snapshot),
    ]
    return _move(
        ctx, kind, kind, action, headline, impact, worst, r.confidence, best_choice_label(r.confidence),
        [e1, e2, e3], sources, _options(best, [*MORTGAGE_OPTIONS, "keep"]), stress.test_period, "interest-rates",
        deadline,
    )


# ---------- savings ----------


def savings_gain(
    macro: MacroTable, start: int, amount: float, user_now: float, best_now: float, horizon: int = SAVINGS_HORIZON
) -> float:
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
    stress = STRESS["move_savings"]

    def gain(a: float, s: int) -> float:
        return savings_gain(ctx.macro, s, a, user_now, best_now)

    user = [gain(amount, s) for s in starts]
    stressed = gain(amount, stress.start)
    impact, worst = float(np.mean(user)), float(min(*user, stressed))
    if impact <= 0:
        return None
    conf = float((ctx.grid(starts, lambda p: p.savings if p.savings > 0 else amount, amount, gain) > 0).mean())
    rate_word = "earning about" if measured is not None else "probably earning about"
    e1 = _ev(
        f"You have {gbp(amount)} in savings {rate_word} {pct(user_now)} a year. "
        f"Easy-access accounts pay up to about {pct(best_now)} today.",
        {"savings": money_value(amount), "rate": pct_value(user_now), "best_rate": pct_value(best_now)},
        source_ref(ctx.macro, MacroKey.SAVINGS_RATE, ctx.year) or _bank_ref(ctx.snapshot),
    )
    spans, span_facts = spans_text(starts, SAVINGS_HORIZON)
    e2 = _ev(
        f"In similar past periods ({spans}), moving earned {gbp(impact)} a year more on average.",
        {"impact": money_value(impact), **span_facts},
    )
    e3 = _ev(
        f"In {stress.text}, moving earned {gbp(stressed)} a year {'more' if stressed >= 0 else 'less'}.",
        {"stress": money_value(stressed), **stress.facts()},
        source_ref(ctx.macro, MacroKey.SAVINGS_RATE, stress.start),
    )
    return _move(
        ctx, "move_savings", "move_savings", "Move your savings to a better rate",
        f"Your savings could earn {gbp(impact)} more a year",
        impact, worst, conf, confidence_label(conf), [e1, e2, e3],
        [*_refs(ctx.macro, ctx.year, [MacroKey.SAVINGS_RATE, MacroKey.BANK_RATE]), _bank_ref(ctx.snapshot)],
        _options("switch", ["keep"]), stress.test_period, "compound-interest",
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
    stress = STRESS["switch_energy"]

    def gain(amount: float, s: int) -> float:
        """Fixing today's price for a year vs paying the next year's change seen after `s`."""
        return amount * _v(ctx.macro, MacroKey.ENERGY_PRICE_CHANGE, s + 1, 0.0) / 100

    user = [gain(annual, s) for s in starts]
    stressed = gain(annual, stress.start)
    impact, worst = float(np.mean(user)), float(min(*user, stressed))
    if impact <= 0:
        return None
    rose = sum(1 for g in user if g > 0)
    conf = rose / len(user)
    cap = _v(ctx.macro, MacroKey.ENERGY_TARIFF, ctx.year, 0.0)
    if days is not None and days >= 0:
        s1 = f"You pay {gbp(e.monthly_cost)} a month for energy. Your fixed price ends in {days} days."
        f1 = {"monthly": money_value(e.monthly_cost), "days_left": float(days)}
    else:
        s1 = f"You pay {gbp(e.monthly_cost)} a month for energy on a price that can change."
        f1 = {"monthly": money_value(e.monthly_cost)}
    if cap > 0:
        s1 += f" A typical home pays {gbp(cap)} a year under the price cap."
        f1["typical"] = money_value(cap)
    e1 = _ev(s1, f1, source_ref(ctx.macro, MacroKey.ENERGY_TARIFF, ctx.year) or _bank_ref(ctx.snapshot))
    spans, span_facts = spans_text([s + 1 for s in starts], 1)
    e2 = _ev(
        f"In similar past years ({spans}), prices rose in {rose} of {len(starts)}. "
        f"Fixing {_better(impact)} on average.",
        {"rose": float(rose), "periods": float(len(starts)), "impact": money_value(impact), **span_facts},
        source_ref(ctx.macro, MacroKey.ENERGY_PRICE_CHANGE, ctx.year),
    )
    e3 = _ev(
        f"In {stress.text}, fixing {_better(stressed)}.",
        {"stress": money_value(stressed), **stress.facts()},
        source_ref(ctx.macro, MacroKey.ENERGY_PRICE_CHANGE, stress.start + 1),
    )
    deadline = e.fixed_until if days is not None and days >= 0 else None
    return _move(
        ctx, "switch_energy", "switch_energy", "Fix your energy price",
        "Your energy price can go up" if deadline is None else f"Your energy deal ends in {days} days",
        impact, worst, conf, confidence_label(conf), [e1, e2, e3],
        [*_refs(ctx.macro, ctx.year, [MacroKey.ENERGY_TARIFF, MacroKey.ENERGY_PRICE_CHANGE]), _bank_ref(ctx.snapshot)],
        _options("fix", ["keep"]), stress.test_period, "inflation", deadline,
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
        if t.account_id in ids
        and t.amount < 0
        and "interest" in t.description.lower()
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
    sav = savings_total(ctx.snapshot)
    spare = sav - SAFETY_MONTHS * spend
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
    stress = STRESS["pay_off_debt"]

    def gain(a: float, s: int) -> float:
        card = max(0.0, card_now + _card(ctx.macro, s + 1) - _card(ctx.macro, s))
        lost = max(0.0, sav_now + _savings_avg(ctx.macro, s + 1) - _savings_avg(ctx.macro, s)) if from_savings else 0.0
        return a * share * (card - lost) / 100

    user = [gain(amount, s) for s in starts]
    stressed = gain(amount, stress.start)
    impact, worst = float(np.mean(user)), float(min(*user, stressed))
    if impact <= 0:
        return None
    conf = float((ctx.grid(starts, lambda p: min(p.debt, amount) if p.debt > 0 else amount, amount, gain) > 0).mean())
    if from_savings:
        e1 = _ev(
            f"You owe {gbp(debt)} on cards and loans at about {pct(card_now)} a year. Your savings earn about "
            f"{pct(sav_now)}. Paying {gbp(amount)} from savings still leaves {gbp(sav - amount)}.",
            {"debt": money_value(debt), "card_rate": pct_value(card_now), "savings_rate": pct_value(sav_now),
             "amount": money_value(amount), "left": money_value(sav - amount)},
            _bank_ref(ctx.snapshot),
        )
        action = f"Pay off {gbp(amount)} of card debt from savings"
    elif surplus > 0:
        e1 = _ev(
            f"You owe {gbp(debt)} on cards and loans at about {pct(card_now)} a year. You have about "
            f"{gbp(surplus)} a month left after spending. That clears {gbp(amount)} in a year.",
            {"debt": money_value(debt), "card_rate": pct_value(card_now), "surplus": money_value(surplus),
             "amount": money_value(amount)},
            _bank_ref(ctx.snapshot),
        )
        action = f"Put {gbp(surplus)} a month towards your card"
    else:
        e1 = _ev(
            f"You owe {gbp(debt)} on cards and loans at about {pct(card_now)} a year. You spend about "
            f"{gbp(surplus)} a month more than you earn. Cutting {gbp(PAYDOWN_MONTHLY)} a month and paying it "
            f"to the card clears {gbp(amount)} in a year.",
            {"debt": money_value(debt), "card_rate": pct_value(card_now), "over": money_value(surplus),
             "cut": money_value(PAYDOWN_MONTHLY), "amount": money_value(amount)},
            _bank_ref(ctx.snapshot),
        )
        action = f"Cut {gbp(PAYDOWN_MONTHLY)} a month and pay it to your card"
    spans, span_facts = spans_text([s + 1 for s in starts], 1)
    e2 = _ev(
        f"In similar past years ({spans}), this {_better(impact)} in interest on average.",
        {"impact": money_value(impact), **span_facts},
        source_ref(ctx.macro, MacroKey.CARD_RATE, ctx.year),
    )
    e3 = _ev(
        f"In {stress.text}, it {_better(stressed)}.",
        {"stress": money_value(stressed), **stress.facts()},
        source_ref(ctx.macro, MacroKey.CARD_RATE, stress.start),
    )
    return _move(
        ctx, "pay_off_debt", "pay_off_debt", action, f"Your card costs you {gbp(impact)} a year",
        impact, worst, conf, confidence_label(conf), [e1, e2, e3],
        [*_refs(ctx.macro, ctx.year, [MacroKey.CARD_RATE, MacroKey.SAVINGS_RATE]), _bank_ref(ctx.snapshot)],
        _options("pay_off", ["keep"]), stress.test_period, "debt",
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
    stress = STRESS["build_emergency_fund"]
    shock = min(gap, SHOCK_COST)

    def prob(s: int) -> float:
        return min(1.0, SHOCK_BASE_PROB + _v(ctx.macro, MacroKey.UNEMPLOYMENT, s, 5.0) / 100)

    def expected(s: int) -> float:
        """Expected card interest avoided in a year like `s`."""
        return prob(s) * shock * _card(ctx.macro, s) / 100

    impact = float(np.mean([expected(s) for s in starts]))
    stressed = expected(stress.start)
    rng = np.random.default_rng(ctx.seed)
    hits = rng.random((max(1, len(ctx.twins)), len(starts))) < np.array([prob(s) for s in starts])[None, :]
    conf = float(hits.mean())
    months = round(cash / spend, 1)
    e1 = _ev(
        f"Your cash and savings cover {months:g} months of spending. You spend about {gbp(spend)} a month, "
        f"so {EMERGENCY_MONTHS} months is {gbp(target)}.",
        {"months": months, "spend": money_value(spend), "months_target": float(EMERGENCY_MONTHS),
         "target": money_value(target)},
        _bank_ref(ctx.snapshot),
    )
    spans, span_facts = spans_text(starts, 1)
    p_now = round(float(np.mean([prob(s) for s in starts])) * 100)
    e2 = _ev(
        f"In similar past years ({spans}), about {p_now}% of people faced a surprise bill like {gbp(shock)}. "
        f"Putting it on a card cost {gbp(impact)} a year on average.",
        {"chance_pct": float(p_now), "shock": money_value(shock), "impact": money_value(impact), **span_facts},
        source_ref(ctx.macro, MacroKey.CARD_RATE, ctx.year),
    )
    p_stress = round(prob(stress.start) * 100)
    e3 = _ev(
        f"In {stress.text}, the chance rose to {p_stress}% and the expected cost to {gbp(stressed)} a year.",
        {"stress_chance_pct": float(p_stress), "stress": money_value(stressed), **stress.facts()},
        source_ref(ctx.macro, MacroKey.UNEMPLOYMENT, stress.start),
    )
    return _move(
        ctx, "build_emergency_fund", "build_emergency_fund", f"Build a safety net of {gbp(target)}",
        f"Your safety net covers {months:g} months",
        impact, min(0.0, stressed), conf, confidence_label(conf), [e1, e2, e3],
        [*_refs(ctx.macro, ctx.year, [MacroKey.CARD_RATE, MacroKey.UNEMPLOYMENT]), _bank_ref(ctx.snapshot)],
        _options("save", ["keep"]), stress.test_period, "emergency-fund",
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
    e3 = _ev(f"Cancelling {s.merchant} saves {gbp(impact)} a year.", {"impact": money_value(impact), **names})
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

    def spent_in(m: str, c: Category) -> float:
        return by_month[m].get(c, (0.0, 0))[0]

    best: tuple[float, Category, float, float] | None = None
    for c in CUT_CATEGORIES:
        spent = spent_in(last, c)
        avg = float(np.mean([spent_in(m, c) for m in before]))
        excess = spent - avg
        big = avg >= CUT_MIN_AVERAGE and excess >= max(CUT_MIN_GBP, CUT_MIN_SHARE * avg)
        if big and (best is None or excess > best[0]):
            best = (excess, c, spent, avg)
    if best is None:
        return None
    excess, cat, spent, avg = best
    impact = excess * 12
    under = sum(1 for m in history if spent_in(m, cat) <= avg)
    conf = under / len(history)
    name = category_label(cat).lower()
    e1 = _ev(
        f"You spent {gbp(spent)} on {name} last month, {gbp(excess)} more than usual.",
        {"spent": money_value(spent), "excess": money_value(excess)},
        _bank_ref(ctx.snapshot),
    )
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


# ---------- spread the ISA ----------

SPREAD_MIX = {"global_equity": 0.5, "uk_equity": 0.1, "gilts": 0.3, "cash": 0.1}  # labelled assumption
SPREAD_MIN_HHI = 0.35  # holdings this concentrated score 50 or less (habits bands)
SPREAD_MIN_INVESTED = 1_000.0


def _period_years(period: str) -> float:
    start, end = PERIODS[period]
    return ((int(end[:4]) - int(start[:4])) * 12 + int(end[5:]) - int(start[5:]) + 1) / 12


def _buy_and_hold_cagr(weights: dict[str, float], returns: ReturnSeries) -> float:
    req = IsaBacktestRequest(
        weights=weights, technique="lump_sum", rebalance="none", period="full", monthly_contribution=1.0
    )
    return isa_backtest(req, returns).metrics.cagr


def _spread_isa(ctx: Context) -> Candidate | None:
    holdings = ctx.snapshot.holdings
    returns = ctx.returns
    total = sum(h.value for h in holdings)
    if returns is None or total < SPREAD_MIN_INVESTED:
        return None
    weights = weights_from_holdings(holdings)
    conc = sum((h.value / total) ** 2 for h in holdings)
    if weights is None or conc < SPREAD_MIN_HHI:
        return None
    mine = period_drawdowns(weights, returns)
    spread = period_drawdowns(SPREAD_MIX, returns)
    better = [p for p in NAMED_PERIODS if spread[p] < mine[p]]
    if not better:
        return None
    worst = max(NAMED_PERIODS, key=lambda p: (mine[p], p))
    saved = total * (mine[worst] - spread[worst])
    if saved <= 0:
        return None
    impact = saved / _period_years(worst)
    give_up = total * max(0.0, _buy_and_hold_cagr(weights, returns) - _buy_and_hold_cagr(SPREAD_MIX, returns))
    conf = len(better) / len(NAMED_PERIODS)
    top_share = round(max(h.value for h in holdings) / total * 100)
    fell = round(mine[worst] * 100)
    fell_spread = round(spread[worst] * 100)
    when = PERIOD_LABELS[worst]
    e1 = _ev(
        f"Your biggest holding is {top_share}% of your investments.",
        {"top_share": float(top_share)},
        _bank_ref(ctx.snapshot),
    )
    e2 = _ev(
        f"In {when}, your current mix fell {fell}% at its worst. A spread mix fell {fell_spread}%.",
        {"fell": float(fell), "fell_spread": float(fell_spread), **digit_facts(when)},
    )
    e3 = _ev(
        f"On {gbp(total)} invested, that is {gbp(saved)} less lost. Over the long run the spread mix may grow "
        f"{gbp(give_up)} a year less.",
        {"invested": money_value(total), "saved": money_value(saved), "give_up": money_value(give_up)},
    )
    return _move(
        ctx, "spread_isa", "spread_isa", "Spread your investments",
        f"Your investments fell harder than a spread mix in {when}", impact, -give_up, conf,
        f"The spread mix fell less in {len(better)} of {len(NAMED_PERIODS)} past crashes",
        [e1, e2, e3], [_bank_ref(ctx.snapshot)], _options("spread", ["keep"]), None, "diversification",
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
    _spread_isa,
)


def candidates(ctx: Context) -> list[Candidate]:
    out = [c for c in (b(ctx) for b in BUILDERS) if c is not None and c.move.impact_per_year > 0]

    def key(c: Candidate) -> tuple[float, int, int]:
        days = c.move.days_left if c.move.days_left is not None else 10**6
        return (-round(c.score, 6), days, KIND_ORDER.index(c.move.kind))

    return sorted(out, key=key)


def build_context(
    snapshot: FinanceSnapshot,
    macro: MacroTable,
    today: dates.date,
    seed: int = 0,
    returns: ReturnSeries | None = None,
) -> Context:
    year = min(today.year, latest_year(macro))
    prof, _ = profile(snapshot, today)
    twins = nearest_twins(prof, macro, year)[:K_TWINS]
    return Context(
        snapshot=snapshot, macro=macro, today=today, year=year, profile=prof, seed=seed, twins=twins, returns=returns
    )


def next_move(
    snapshot: FinanceSnapshot,
    macro: MacroTable,
    today: dates.date,
    seed: int = 0,
    returns: ReturnSeries | None = None,
) -> NextMoveResponse:
    """ONE top move and up to 2 runners-up. `generated_at` is a placeholder: the API sets server time."""
    ctx = build_context(snapshot, macro, today, seed, returns)
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
        policy[POLICY_DEAL_END] = str(move.test_period.start)
    return policy


def scenario_years(move: Move) -> tuple[int, int]:
    """(start_year, end_year) for lifeline_sim.play_scenario so that events cover the whole test period.
    The sim runs events from start_year + 1 to end_year, so start_year = test_period.start - 1."""
    if move.test_period is None:
        raise ValueError(f"move {move.id} has no test period")
    return move.test_period.start - 1, move.test_period.end


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
    periods that ended before Y (the stress period counts only once it ended before Y), then compare with the
    option that was cheapest on the real path from Y."""
    years = sorted(macro.years(MacroKey.BANK_RATE))
    if not years:
        return []
    last = min(years[-1], upto)
    stress = STRESS["fix_mortgage"]
    rows: list[BacktestRow] = []
    for y in range(max(BACKTEST_FIRST_YEAR, years[0]), last - MORTGAGE_HORIZON + 2):
        pool = candidate_starts(macro, before=y, horizon=MORTGAGE_HORIZON)
        starts = [m.year for m in similar_years(macro, y, K_PERIODS, candidates=pool)]
        if not starts:
            continue
        svr, tracker = _svr(macro, y), _tracker(macro, y)
        q2, q5 = _fix(macro, MacroKey.MORTGAGE_2Y_FIX, y), _fix(macro, MacroKey.MORTGAGE_5Y_FIX, y)
        bal = BACKTEST_PROFILE_BALANCE
        stress_start = stress.start if stress.end < y else None
        rec = rank_mortgage(
            macro, starts, [bal], bal, BACKTEST_YEARS_LEFT, q2, q5, svr, tracker, stress_start,
            stress_horizon=stress.years,
        )
        real = rank_mortgage(macro, [y], [bal], bal, BACKTEST_YEARS_LEFT, q2, q5, svr, tracker)
        realised = max(MORTGAGE_OPTIONS, key=lambda o: (real.impact[o], -MORTGAGE_OPTIONS.index(o)))
        rows.append(BacktestRow(year=y, recommended=rec.best, realised_best=realised))
    return rows


CONSTANT_RULE_TEXT: dict[str, str] = {
    "fix_2y": "always fix for 2 years",
    "fix_3y": "always fix for 3 years",
    "fix_5y": "always fix for 5 years",
    "tracker": "always take a tracker",
}


def best_constant_rule(realised: Sequence[str], options: Sequence[str]) -> tuple[str, float]:
    """ADR 0023: the constant rule ('always take option o') with the highest hit rate. Ties: option order."""
    n = len(realised)
    if n == 0:
        return options[0], 0.0
    rates = {o: sum(r == o for r in realised) / n for o in options}
    best = sorted(options, key=lambda o: (-rates[o], options.index(o)))[0]
    return best, rates[best]


def mortgage_backtest(macro: MacroTable, upto: int) -> NextMoveBacktest:
    rows = mortgage_backtest_rows(macro, upto)
    n = len(rows)
    first = rows[0].year if rows else BACKTEST_FIRST_YEAR
    lastrow = rows[-1].year if rows else BACKTEST_FIRST_YEAR
    rule, rule_rate = best_constant_rule([r.realised_best for r in rows], MORTGAGE_OPTIONS)
    return NextMoveBacktest(
        method=(
            f"Walk-forward backtest over past deal-end years {first}-{lastrow}: the engine picks fix 2 years, "
            "fix 5 years or tracker using only earlier periods, then we check which was cheapest over the next "
            f"5 years on the real rate path. Best constant rule: {CONSTANT_RULE_TEXT[rule]}, right in "
            f"{rule_rate:.1%} of years."
        ),
        n=n,
        hit_rate=round(sum(r.recommended == r.realised_best for r in rows) / n, 4) if n else 0.0,
        baseline=f"Always fix for 2 years (best constant rule: {CONSTANT_RULE_TEXT[rule]}, {rule_rate:.1%})",
        baseline_hit_rate=round(sum(r.realised_best == BACKTEST_BASELINE for r in rows) / n, 4) if n else 0.0,
    )
