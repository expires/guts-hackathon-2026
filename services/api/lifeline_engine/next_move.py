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
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from lifeline_contracts.domain import DecisionProfile, SourceRef
from lifeline_contracts.finance import Category, FinanceSnapshot
from lifeline_contracts.macro import MacroKey, MacroTable
from lifeline_contracts.next_move import (
    EvidencePoint,
    Move,
    MoveKind,
    MoveOption,
    NextMoveBacktest,
    NextMoveResponse,
    TestPeriod,
    TradeOff,
)
from lifeline_engine import preconditions as pre
from lifeline_engine import rules as facts_table
from lifeline_engine import student as stu
from lifeline_engine import trade_offs
from lifeline_engine.decision import _twins as nearest_twins
from lifeline_engine.decision import candidate_starts, mortgage_interest
from lifeline_engine.finance import monthly_payment
from lifeline_engine.macro_access import latest_year, source_ref, value_or
from lifeline_engine.money import dates, finance_meta
from lifeline_engine.money.categorise import label as category_label
from lifeline_engine.money.profile import (
    cash_savings_total,
    costs_word,
    debt_total,
    full_data_months,
    full_months_before,
    is_cash_savings,
    known_monthly_costs,
    liquid,
    monthly_spend,
    profile,
    savings_rate_pct,
    savings_total,
)
from lifeline_engine.money.recurring import detect_salary, detect_subscriptions
from lifeline_engine.money.spending import by_category
from lifeline_engine.money.text import clean_name, gbp, money_value, pct, pct_value, unsupported_numbers
from lifeline_engine.periods import similar_years
from lifeline_engine.population import Person
from lifeline_engine.wording import best_choice_label, confidence_label, confidence_sentence, with_sample
from lifeline_engine.wording import confidence_level as level_of

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
    def span(self) -> str:
        """'2021-2023', or '2023' for a one-year period."""
        return f"{self.start}" if self.start == self.end else f"{self.start}-{self.end}"

    @property
    def test_period(self) -> TestPeriod:
        return TestPeriod(start=self.start, end=self.end, label=f"{self.span} {self.name} (stress test)")

    def facts(self) -> dict[str, float]:
        return {"stress_start": float(self.start), "stress_end": float(self.end)}

    @property
    def years(self) -> int:
        return self.end - self.start + 1

    @property
    def text(self) -> str:
        return f"the {self.span} {self.name}"


# Standard stress period per move kind (ADR 0020).
STRESS: dict[MoveKind, StressPeriod] = {
    "fix_mortgage": StressPeriod(2021, 2023, "rate shock"),
    "remortgage": StressPeriod(2021, 2023, "rate shock"),
    "move_savings": StressPeriod(2009, 2011, "low-rate years"),
    "switch_energy": StressPeriod(2021, 2023, "energy price shock"),
    # ADR 0065: student periods, as in the user's example.
    "pay_off_debt": StressPeriod(2023, 2023, "rate rises"),
    "build_emergency_fund": StressPeriod(2022, 2023, "cost-of-living spike"),
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
    "weekly_budget",
    "lifetime_isa",
    "keep_cash",
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
    # ADR 0065: student moves. The key is the template id (lifeline_sim policy_choice checks it first).
    "weekly_budget": "study.term_budget",
    "lifetime_isa": "money.lifetime_isa",
}
# Tags the sim focuses so the move's event fires in the test period (W3 adds them to the templates).
MOVE_FOCUS: dict[MoveKind, str] = {"weekly_budget": "weekly_budget", "lifetime_isa": "lifetime_isa"}
POLICY_FOCUS = "__focus"
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
    "weekly": "Keep to a weekly budget",
    "freestyle": "Keep spending as now",
    "open": "Open a Lifetime ISA",
    "not_now": "Not now",
    "hold": "Keep it as cash",
}
OPTION_NUMBERS: dict[str, dict[str, float]] = {"fix_5y": {"fix_years": 5.0}, "fix_2y": {"fix_years": 2.0}}


# ---------- small helpers ----------


SURE_LABEL = "Based on your own numbers"  # arithmetic moves: level "high", no sample (ADR 0053)


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

    def grid(
        self,
        starts: Sequence[int],
        amount_of: Callable[[Person], float],
        default: float,
        gain: Callable[[float, int], float],
    ) -> FloatArray:
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
    trade_off: TradeOff,
    deadline: str | None = None,
    cover_months: float | None = None,
    sample_size: int | None = None,
    sample_unit: str = "",
    deterministic: bool = False,
    weeks: tuple[float, float] | None = None,
    shortfall: float | None = None,
    level: Literal["low", "medium", "high"] | None = None,
    no_level: bool = False,
    reason: str | None = None,
    basis: str | None = None,
) -> Candidate:
    """`sample_size`: matched cases behind `confidence` (ADR 0053 bug 4). `deterministic`: the gain is arithmetic
    on the user's own data, not a sampled outcome. `weeks`: (weeks until the next money, safe weekly spend) for a
    weekly budget, shown as weeks of cover. `reason`: one plain line on why the move helps (ADR 0069).
    `basis`: what a deterministic confidence rests on, for `confidence_text`."""
    if not pre.met(kind, ctx.snapshot, ctx.today) and impact > 0:
        raise ValueError(f"precondition for {kind} does not hold")
    # The recommended option's label is the action, word for word (V5).
    options = [o.model_copy(update={"label": action}) if o.is_recommended else o for o in options]
    days_left = None
    if deadline is not None:
        days_left = max(0, (dates.parse(deadline) - ctx.today).days)
    confidence_level = None if no_level else level or level_of(confidence, sample_size, deterministic)
    move = Move(
        id=move_id,
        kind=kind,
        action=action,
        headline=headline,
        impact_per_year=round(impact, 2),
        worst_case_per_year=round(worst, 2),
        confidence=round(min(1.0, max(0.0, confidence)), 4),
        sample_size=sample_size,
        confidence_level=confidence_level,
        confidence_label=with_sample(confidence_text, sample_size, sample_unit),
        confidence_text=confidence_sentence(confidence_level, sample_size, sample_unit, basis),
        reason=reason,
        evidence=evidence,
        sources=sources,
        options=options,
        deadline=deadline,
        days_left=days_left,
        testable=test_period is not None,
        test_period=test_period,
        concept_id=concept_id,
        gain_kind=(
            "weeks_of_cover" if weeks is not None else "gbp_per_year" if cover_months is None else "months_of_cover"
        ),
        cover_weeks=None if weeks is None else round(weeks[0], 1),
        safe_weekly_spend=None if weeks is None else round(weeks[1], 2),
        shortfall=None if shortfall is None else round(shortfall, 2),
        cover_months=None if cover_months is None else round(cover_months, 1),
        trade_off=trade_off,
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
    if m is None or not (pre.fix_mortgage(ctx.snapshot, ctx.today) or pre.remortgage(ctx.snapshot, ctx.today)):
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
        ctx.macro,
        starts,
        balances,
        m.balance,
        m.years_left,
        q2,
        q5,
        keep_now,
        tracker_now,
        stress_start=stress.start,
        stress_horizon=stress.years,
        regret_weight=aff.weight,
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
            {
                "current_rate": pct_value(m.rate_pct),
                "days_left": float(days_left),
                "svr_rate": pct_value(svr),
                **cmp_facts,
                **aff.facts,
            },
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
    fix_years = int(OPTION_NUMBERS[best]["fix_years"]) if best in OPTION_NUMBERS else None
    deal_start = dates.parse(deadline).year if deadline is not None else ctx.today.year
    new_rate = {"fix_5y": q5, "fix_2y": q2}.get(best, tracker_now)
    one_point = monthly_payment(m.balance, tracker_now + 1.0, m.years_left) - monthly_payment(
        m.balance, tracker_now, m.years_left
    )
    trade = trade_offs.mortgage(
        best,
        m.balance,
        new_rate,
        deal_start,
        fix_years,
        one_point,
        stress.text,
        stress.facts(),
        _bank(ctx.macro, stress.start),
        _bank(ctx.macro, stress.end),
    )
    sources = [
        *_refs(
            ctx.macro,
            ctx.year,
            [
                MacroKey.BANK_RATE,
                MacroKey.MORTGAGE_2Y_FIX,
                MacroKey.MORTGAGE_5Y_FIX,
                MacroKey.MORTGAGE_SVR,
                MacroKey.MORTGAGE_TRACKER,
            ],
        ),
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
        best_choice_label(r.confidence),
        [e1, e2, e3],
        sources,
        _options(best, [*MORTGAGE_OPTIONS, "keep"]),
        stress.test_period,
        "interest-rates",
        trade,
        deadline,
        sample_size=len(starts) + 1,
        sample_unit="past periods",
        reason=(
            f"Your deal ends in {days_left} days, and this choice did best in similar past periods"
            if kind == "fix_mortgage"
            else "You pay more than today's deals, and this choice did best in similar past periods"
        ),
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
    if not pre.move_savings(ctx.snapshot, ctx.today):
        return None
    amount = cash_savings_total(ctx.snapshot)
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
    g_sav = ctx.grid(starts, lambda p: p.savings if p.savings > 0 else amount, amount, gain)
    conf = float((g_sav > 0).mean())
    if measured is not None:
        s1 = (
            f"You have {gbp(amount)} in savings earning about {pct(user_now)} a year. "
            f"Easy-access accounts pay up to about {pct(best_now)} today."
        )
    else:  # ADR 0053 bug 6: the user's rate is unknown, so compare with the UK average and say so
        s1 = (
            f"You have {gbp(amount)} in savings. We do not know their rate, so we use the UK average of "
            f"{pct(user_now)}. Easy-access accounts pay up to about {pct(best_now)} today."
        )
    e1 = _ev(
        s1,
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
        ctx,
        "move_savings",
        "move_savings",
        "Move your savings to a better rate",
        f"Your savings could earn {gbp(impact)} more a year",
        impact,
        worst,
        conf,
        confidence_label(conf),
        [e1, e2, e3],
        [*_refs(ctx.macro, ctx.year, [MacroKey.SAVINGS_RATE, MacroKey.BANK_RATE]), _bank_ref(ctx.snapshot)],
        _options("switch", ["keep"]),
        stress.test_period,
        "compound-interest",
        trade_offs.move_savings(best_now, biggest_savings_fall(ctx.macro, ctx.year)),
        sample_size=len(starts),
        sample_unit="past periods",
        reason="Other easy-access accounts pay more interest than yours",
    )


SAVINGS_FALL_YEARS = 20  # look back this many years for the largest fall


def biggest_savings_fall(macro: MacroTable, upto: int) -> tuple[int, float, float] | None:
    """(year, rate before, rate after) for the largest one-year fall in the top easy-access rate in the
    SAVINGS_FALL_YEARS years up to `upto`. None when the rate never fell."""
    years = [y for y in macro.years(MacroKey.BANK_RATE) if upto - SAVINGS_FALL_YEARS <= y <= upto]
    falls = [(_best_savings(macro, y - 1) - _best_savings(macro, y), y) for y in years if y - 1 in years]
    drop, year = max(falls, default=(0.0, 0))
    if drop <= 0:
        return None
    return year, _best_savings(macro, year - 1), _best_savings(macro, year)


# ---------- energy ----------


def _energy(ctx: Context) -> Candidate | None:
    e = ctx.snapshot.energy
    if e is None or not pre.switch_energy(ctx.snapshot, ctx.today):
        return None
    days = pre.energy_days_left(ctx.snapshot, ctx.today)
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
        ctx,
        "switch_energy",
        "switch_energy",
        "Fix your energy price",
        "Your energy price can go up" if deadline is None else f"Your energy deal ends in {days} days",
        impact,
        worst,
        conf,
        f"Prices rose in {rose} of {len(user)} similar past years",
        [e1, e2, e3],
        [*_refs(ctx.macro, ctx.year, [MacroKey.ENERGY_TARIFF, MacroKey.ENERGY_PRICE_CHANGE]), _bank_ref(ctx.snapshot)],
        _options("fix", ["keep"]),
        stress.test_period,
        "inflation",
        trade_offs.switch_energy(e.monthly_cost, sum(1 for g in user if g < 0), len(user)),
        deadline,
        sample_size=len(user),
        sample_unit="past years",
        reason="A fixed price protects your bills if energy prices go up",
    )


# ---------- debt ----------


def card_rate_pct(snapshot: FinanceSnapshot, today: dates.date) -> float | None:
    """Rate on expensive debt: the balance-weighted entered `rate_pct` of entered debts (ADR 0049) when every
    expensive one has a rate, else interest charged in the last year / debt. None without either."""
    entered = [d for d in stu.from_snapshot(snapshot, today).debts if d.expensive > 0] if snapshot.debts else []
    if entered and all(d.rate_pct is not None for d in entered):
        total = sum(d.expensive for d in entered)
        return round(sum(d.expensive * (d.rate_pct or 0.0) for d in entered) / total, 2)
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


DEBT_DEBT = {
    "card": "card debt",
    "overdraft": "your overdraft",
    "bnpl": "your buy now, pay later plan",
    "loan": "your loan",
}
DEBT_NOUN = {"card": "card", "overdraft": "overdraft", "bnpl": "buy now, pay later plan", "loan": "loan"}
DEBT_ORDER = ("card", "overdraft", "bnpl", "loan")


@dataclass(frozen=True)
class DebtWords:
    where: str  # "on your overdraft"
    target: str  # "your overdraft"
    debt: str  # "your overdraft" / "card debt"
    subject: str  # "Your overdraft costs you"


def debt_words(debts: Sequence[stu.Debt]) -> DebtWords:
    """Words from the kinds of expensive debt present, so an overdraft is never called a card (F-V2-3)."""
    kinds = [k for k in DEBT_ORDER if any(d.kind == k and d.expensive > 0 for d in debts)]
    if len(kinds) == 1:
        k = kinds[0]
        noun = DEBT_NOUN[k]
        return DebtWords(f"on your {noun}", f"your {noun}", DEBT_DEBT[k], f"Your {noun} costs you")
    names = " and ".join(f"{DEBT_NOUN[k]}s" if k in ("card", "loan") else DEBT_NOUN[k] for k in kinds) or "debts"
    return DebtWords(f"on your {names}", "your debts", "your debts", "Your debts cost you")


def _debt(ctx: Context) -> Candidate | None:
    if not pre.pay_off_debt(ctx.snapshot, ctx.today):
        return None
    debt = pre.expensive_debt(ctx.snapshot, ctx.today)
    costs = known_monthly_costs(ctx.snapshot, ctx.today)
    spend = costs or 0.0
    sav = savings_total(ctx.snapshot)
    inc = detect_salary(ctx.snapshot.transactions)
    surplus = monthly_surplus(ctx.snapshot, ctx.today) if inc is not None and costs is not None else None
    # Pay from savings only when costs are known, so one month of costs stays in savings.
    from_savings = costs is not None and sav - SAFETY_MONTHS * costs > 0
    if from_savings:
        amount = min(debt, sav - SAFETY_MONTHS * spend)  # capped at the debt
        share = 1.0
    else:
        monthly = surplus if surplus is not None and surplus > 0 else PAYDOWN_MONTHLY
        amount = min(debt, 12 * monthly)
        share = 0.5  # paid down over the year: about half the amount is cleared on average
    measured = card_rate_pct(ctx.snapshot, ctx.today)
    card_now = measured if measured is not None else _card(ctx.macro, ctx.year)
    sav_measured = savings_rate_pct(ctx.snapshot, ctx.today)
    sav_now = sav_measured if sav_measured is not None else _savings_avg(ctx.macro, ctx.year)
    starts = ctx.periods(ONE_YEAR + 1)
    if not starts:
        return None
    stress = STRESS["pay_off_debt"]

    def gain(a: float, s: int) -> float:
        card = max(0.0, card_now + _card(ctx.macro, s + 1) - _card(ctx.macro, s))
        lost = max(0.0, sav_now + _savings_avg(ctx.macro, s + 1) - _savings_avg(ctx.macro, s)) if from_savings else 0.0
        return a * share * (card - lost) / 100

    user = [gain(amount, s) for s in starts]
    stressed = gain(amount, stress.start - 1)  # the year into stress.start: card rates moved 2022 -> 2023
    impact, worst = float(np.mean(user)), float(min(*user, stressed))
    if impact <= 0:
        return None
    g_debt = ctx.grid(starts, lambda p: min(p.debt, amount) if p.debt > 0 else amount, amount, gain)
    conf = float((g_debt > 0).mean())
    # ADR 0053 bugs 3 and 6: a rate we did not measure is called the UK average, never "your" rate.
    words = debt_words(stu.from_snapshot(ctx.snapshot, ctx.today).debts)
    owe = (
        f"You owe {gbp(debt)} {words.where} at about {pct(card_now)} a year."
        if measured is not None
        else f"You owe {gbp(debt)} {words.where}. We do not know the rate, so we use the UK average card rate of "
        f"{pct(card_now)} a year."
    )
    base = {"debt": money_value(debt), "card_rate": pct_value(card_now)}
    if from_savings:
        sav_text = (
            f"Your savings earn about {pct(sav_now)}."
            if sav_measured is not None
            else f"Savings earn about {pct(sav_now)} on average."
        )
        e1 = _ev(
            f"{owe} {sav_text} Paying {gbp(amount)} from savings still leaves {gbp(sav - amount)}.",
            {
                **base,
                "savings_rate": pct_value(sav_now),
                "amount": money_value(amount),
                "left": money_value(sav - amount),
            },
            _bank_ref(ctx.snapshot),
        )
        action = f"Pay off {gbp(amount)} of {words.debt} from savings"
    elif surplus is not None and surplus > 0:
        e1 = _ev(
            f"{owe} You have about {gbp(surplus)} a month left after spending. That clears {gbp(amount)} in a year.",
            {**base, "surplus": money_value(surplus), "amount": money_value(amount)},
            _bank_ref(ctx.snapshot),
        )
        action = f"Put {gbp(surplus)} a month towards {words.target}"
    elif surplus is not None:
        e1 = _ev(
            f"{owe} You spend about {gbp(surplus)} a month more than you earn. Cutting {gbp(PAYDOWN_MONTHLY)} a "
            f"month and paying it to {words.target} clears {gbp(amount)} in a year.",
            {**base, "over": money_value(surplus), "cut": money_value(PAYDOWN_MONTHLY), "amount": money_value(amount)},
            _bank_ref(ctx.snapshot),
        )
        action = f"Cut {gbp(PAYDOWN_MONTHLY)} a month and pay it to {words.target}"
    else:  # income or costs unknown: no claim about what is left over
        e1 = _ev(
            f"{owe} Paying {gbp(PAYDOWN_MONTHLY)} a month extra to {words.target} clears {gbp(amount)} in a year.",
            {**base, "cut": money_value(PAYDOWN_MONTHLY), "amount": money_value(amount)},
            _bank_ref(ctx.snapshot),
        )
        action = f"Pay {gbp(PAYDOWN_MONTHLY)} a month extra to {words.target}"
    spans, span_facts = spans_text([s + 1 for s in starts], 1)
    e2 = _ev(
        f"In similar past years ({spans}), this {_better(impact)} in interest on average.",
        {"impact": money_value(impact), **span_facts},
        source_ref(ctx.macro, MacroKey.CARD_RATE, ctx.year),
    )
    b0, b1 = _bank(ctx.macro, stress.start - 1), _bank(ctx.macro, stress.start)
    c0, c1 = _card(ctx.macro, stress.start - 1), _card(ctx.macro, stress.start)
    e3 = _ev(
        f"In {stress.text}, Bank Rate went from {pct(b0)} to {pct(b1)} and card rates from {pct(c0)} to "
        f"{pct(c1)}. Paying it off {_better(stressed)}.",
        {
            "bank_from": pct_value(b0),
            "bank_to": pct_value(b1),
            "card_from": pct_value(c0),
            "card_to": pct_value(c1),
            "stress": money_value(stressed),
            **stress.facts(),
        },
        source_ref(ctx.macro, MacroKey.BANK_RATE, stress.start),
    )
    return _move(
        ctx,
        "pay_off_debt",
        "pay_off_debt",
        action,
        f"{words.subject} {gbp(impact)} a year",
        impact,
        worst,
        conf,
        confidence_label(conf),
        [e1, e2, e3],
        [*_refs(ctx.macro, ctx.year, [MacroKey.CARD_RATE, MacroKey.SAVINGS_RATE]), _bank_ref(ctx.snapshot)],
        _options("pay_off", ["keep"]),
        stress.test_period,
        "debt",
        _debt_trade_off(ctx, from_savings, surplus or 0.0, amount, sav, spend, sav_now, card_now, words.target),
        sample_size=len(starts),
        sample_unit="past years",
        reason=(
            f"Your debt costs more in interest than your savings earn, so clearing it saves {gbp(impact)} a year"
            if from_savings
            else f"Paying down {words.target} cuts the interest you pay"
        ),
    )


def _debt_trade_off(
    ctx: Context,
    from_savings: bool,
    surplus: float,
    amount: float,
    sav: float,
    spend: float,
    sav_now: float,
    card_now: float,
    target: str,
) -> TradeOff:
    cash = max(0.0, liquid(ctx.snapshot))
    word = costs_word(ctx.snapshot, ctx.today)
    known = savings_rate_pct(ctx.snapshot, ctx.today) is not None
    if from_savings:
        left = sav - amount
        months = round(max(0.0, cash - amount) / spend, 1) if spend > 0 else None
        return trade_offs.pay_off_debt("savings", amount, 0.0, left, months, sav_now, card_now, known, word, target)
    monthly = surplus if surplus > 0 else PAYDOWN_MONTHLY
    months = round(cash / spend, 1) if spend > 0 else None
    return trade_offs.pay_off_debt(
        "surplus" if surplus > 0 else "cut", amount, monthly, sav, months, sav_now, card_now, known, word, target
    )


# ---------- emergency fund ----------


def _emergency(ctx: Context) -> Candidate | None:
    spend = known_monthly_costs(ctx.snapshot, ctx.today)
    if spend is None or not pre.build_emergency_fund(ctx.snapshot, ctx.today):
        return None
    cash = max(0.0, liquid(ctx.snapshot))
    target = EMERGENCY_MONTHS * spend
    gap = target - cash
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
    word = costs_word(ctx.snapshot, ctx.today)
    verb = "You spend about" if word == "spending" else "Your regular costs are"
    e1 = _ev(
        f"Your cash and savings cover {months:g} months of {word}. {verb} {gbp(spend)} a month, "
        f"so {EMERGENCY_MONTHS} months is {gbp(target)}.",
        {
            "months": months,
            "spend": money_value(spend),
            "months_target": float(EMERGENCY_MONTHS),
            "target": money_value(target),
        },
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
    cpi_years = [y for y in range(stress.start, stress.end + 1) if y in ctx.macro.years(MacroKey.CPI_INFLATION)]
    peak_year = max(cpi_years, key=lambda y: (ctx.macro.value(MacroKey.CPI_INFLATION, y), -y), default=stress.start)
    peak = _v(ctx.macro, MacroKey.CPI_INFLATION, peak_year, 0.0)
    e3 = _ev(
        f"In {stress.text}, prices rose {pct(peak)} in {peak_year}. A surprise bill like {gbp(shock)} on a card "
        f"then cost about {gbp(stressed)} a year.",
        {
            "cpi_peak": pct_value(peak),
            "peak_year": float(peak_year),
            "shock": money_value(shock),
            "stress": money_value(stressed),
            **stress.facts(),
        },
        source_ref(ctx.macro, MacroKey.CPI_INFLATION, peak_year),
    )
    return _move(
        ctx,
        "build_emergency_fund",
        "build_emergency_fund",
        f"Build a safety net of {gbp(target)}",
        f"Your safety net covers {months:g} months",
        impact,
        min(0.0, stressed),
        conf,
        confidence_label(conf),
        [e1, e2, e3],
        [*_refs(ctx.macro, ctx.year, [MacroKey.CARD_RATE, MacroKey.UNEMPLOYMENT]), _bank_ref(ctx.snapshot)],
        _options("save", ["keep"]),
        stress.test_period,
        "emergency-fund",
        _emergency_trade_off(ctx, gap),
        cover_months=float(EMERGENCY_MONTHS),
        sample_size=len(starts),
        sample_unit="past years",
        reason=f"With {EMERGENCY_MONTHS} months of costs put aside, a surprise bill does not go on a card",
    )


def stock_history(macro: MacroTable, upto: int) -> tuple[float, int, int] | None:
    """Mean yearly UK share return over every year with data up to `upto`, and the first and last year."""
    years = [y for y in macro.years(MacroKey.STOCK_RETURN) if y <= upto]
    if not years:
        return None
    return float(np.mean([macro.value(MacroKey.STOCK_RETURN, y) for y in years])), years[0], years[-1]


def _emergency_trade_off(ctx: Context, amount: float) -> TradeOff:
    measured = savings_rate_pct(ctx.snapshot, ctx.today)
    sav_now = measured if measured is not None else _savings_avg(ctx.macro, ctx.year)
    hist = stock_history(ctx.macro, ctx.year)
    inv = invests(ctx.snapshot)
    if hist is None:
        return trade_offs.emergency_fund(amount, sav_now, None, None, None, measured is not None, inv)
    return trade_offs.emergency_fund(amount, sav_now, *hist, measured is not None, inv)


def invests(snapshot: FinanceSnapshot) -> bool:
    """The user holds investments: a pension or a stocks and shares ISA. Most students do not (ADR 0070), so their
    trade-offs talk about weekly spending and a savings buffer, not investing."""
    return any(a.kind == "pension" or (a.kind == "isa" and not is_cash_savings(a)) for a in snapshot.accounts)


# ---------- subscriptions ----------


_PER = {"weekly": "a week", "monthly": "a month", "quarterly": "a quarter", "yearly": "a year"}


def _subscription(ctx: Context) -> Candidate | None:
    if not pre.cancel_subscription(ctx.snapshot, ctx.today):
        return None
    subs = detect_subscriptions(ctx.snapshot.transactions, ctx.today)
    risen = [s for s in subs if s.price_rise is not None]
    s = max(risen, key=lambda x: (x.monthly_cost, x.id))
    assert s.price_rise is not None
    impact = s.monthly_cost * 12
    total = sum(x.monthly_cost for x in subs)
    name = clean_name(s.merchant)
    names: dict[str, float] = {}
    e1 = _ev(
        f"{name} went up from {gbp(s.price_rise.from_amount, True)} to "
        f"{gbp(s.price_rise.to_amount, True)} {_PER[s.cadence]}.",
        {"from": money_value(s.price_rise.from_amount, True), "to": money_value(s.price_rise.to_amount, True), **names},
        _bank_ref(ctx.snapshot),
    )
    e2 = _ev(
        f"You pay {gbp(total)} a month for {len(subs)} subscriptions.",
        {"monthly_total": money_value(total), "count": float(len(subs))},
        _bank_ref(ctx.snapshot),
    )
    e3 = _ev(f"Cancelling {name} saves {gbp(impact)} a year.", {"impact": money_value(impact), **names})
    return _move(
        ctx,
        "cancel_subscription",
        f"cancel_subscription-{_slug(name)}",
        f"Cancel {name}",
        f"{name} put its price up",
        impact,
        impact,
        1.0,
        SURE_LABEL,
        [e1, e2, e3],
        [_bank_ref(ctx.snapshot)],
        _options("cancel", ["keep"]),
        ctx.matched_test_period(),
        "budgeting",
        trade_offs.cancel_subscription(name, s.amount, _PER[s.cadence], s.price_rise.to_amount),
        deterministic=True,
        reason=f"{name} put its price up, and cancelling it saves {gbp(impact)} a year",
        basis="the price is on your own statement",
    )


# ---------- budget ----------


def _budget(ctx: Context) -> Candidate | None:
    """W-R-2: one window for every number: the last up to 6 full months with data (last month included).
    The usual amount is the average of the up to 3 months with data before last month."""
    if not pre.cut_budget(ctx.snapshot, ctx.today):
        return None
    months = full_months_before(ctx.today, 6)
    by_month = {m: by_category(ctx.snapshot.transactions, m) for m in months}
    if not by_month[months[-1]]:
        return None
    window = [m for m in full_data_months(ctx.snapshot, months) if by_month[m]]  # whole months only
    if not window or window[-1] != months[-1]:
        return None
    last, before = window[-1], window[:-1][-3:]
    if not before:
        return None

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
    n = len(window)
    mean_excess = float(np.mean([max(0.0, spent_in(m, cat) - avg) for m in window]))
    impact = mean_excess * 12
    under = sum(1 for m in window if spent_in(m, cat) <= avg)
    conf = under / n
    name = category_label(cat).lower()
    e1 = _ev(
        f"You spent {gbp(spent)} on {name} last month, {gbp(excess)} more than usual.",
        {"spent": money_value(spent), "excess": money_value(excess)},
        _bank_ref(ctx.snapshot),
    )
    span = "the month before" if len(before) == 1 else f"the {len(before)} months before"
    e2 = _ev(
        f"In {span}, you spent {gbp(avg)} a month{'' if len(before) == 1 else ' on average'}.",
        {"months": float(len(before)), "average": money_value(avg)},
        _bank_ref(ctx.snapshot),
    )
    e3 = _ev(
        f"Over the last {n} months you went over {gbp(avg)} by {gbp(mean_excess)} a month on average, about "
        f"{gbp(impact)} a year. You spent {gbp(avg)} or less in {under} of those {n} months.",
        {
            "window": float(n),
            "average": money_value(avg),
            "mean_excess": money_value(mean_excess),
            "impact": money_value(impact),
            "under": float(under),
        },
    )
    return _move(
        ctx,
        "cut_budget",
        f"cut_budget-{cat}",
        f"Cut {name} to {gbp(avg)} a month",
        f"You spent {gbp(excess)} more than usual on {name}",
        impact,
        0.0,
        conf,
        f"You spent this little in {under} of the last {n} months",
        [e1, e2, e3],
        [_bank_ref(ctx.snapshot)],
        _options("cut", ["keep"]),
        ctx.matched_test_period(),
        "budgeting",
        trade_offs.cut_budget(name, excess, avg, n - under, n),
        sample_size=n,
        sample_unit="months",
        reason=f"You spent {gbp(excess)} more than usual on {name} last month",
    )


# ---------- student moves (ADR 0046) ----------

PAYMENT_WORDS: dict[str, str] = {
    "maintenance_loan": "student loan payment",
    "scholarship": "scholarship payment",
    "bursary": "bursary payment",
    "grant": "grant payment",
    "family": "money from family",
    "part_time_job": "pay",
    "salary": "pay",
}
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def day_text(d: dates.date) -> tuple[str, dict[str, float]]:
    """'12 November' and its fact. The year is not shown."""
    return f"{d.day} {MONTHS[d.month - 1]}", {"day_of_month": float(d.day)}


MIN_WEEKLY = 1.0  # GBP a week; below this there is no weekly amount to keep to, so the move frames the shortfall


def _weekly_budget(ctx: Context) -> Candidate | None:
    if not pre.weekly_budget(ctx.snapshot, ctx.today):
        return None
    wb = stu.weekly_budget(
        ctx.snapshot, stu.from_snapshot(ctx.snapshot, ctx.today), ctx.today, max(0.0, liquid(ctx.snapshot))
    )
    assert wb is not None
    when, when_facts = day_text(wb.next_date)
    what = PAYMENT_WORDS.get(wb.next_kind, "next payment")
    weeks_left = round(wb.weeks_left, 1)
    covered = round(wb.weeks_covered, 1)
    # F-R-1: the plain shortfall before the next payment, never annualised. It is only a ranking key here;
    # the card shows `shortfall`, `cover_weeks` and `safe_weekly_spend` (gain_kind weeks_of_cover).
    impact = wb.short_by
    balance = liquid(ctx.snapshot)
    have = f"You are {gbp(balance)} overdrawn" if balance < 0 else f"You have {gbp(wb.cash)}"
    e1 = _ev(
        f"{have} until your {what} on {when}, in {wb.days_left} days. "
        f"Regular bills before then: {gbp(wb.bills_before)}.",
        {
            "cash": money_value(balance if balance < 0 else wb.cash),
            "days_left": float(wb.days_left),
            "bills": money_value(wb.bills_before),
            **when_facts,
        },
        _bank_ref(ctx.snapshot),
    )
    need = wb.weekly_pace * wb.weeks_left
    if wb.safe_weekly >= MIN_WEEKLY:
        s2 = (
            f"You usually spend about {gbp(wb.weekly_pace)} a week (middle of the last {wb.weeks_seen} weeks). At that "
            "pace your "
            f"money lasts {covered:g} of the {weeks_left:g} weeks, and you are {gbp(wb.short_by)} short."
        )
    else:
        s2 = (
            f"You usually spend about {gbp(wb.weekly_pace)} a week (middle of the last {wb.weeks_seen} weeks), so the "
            f"{wb.days_left} days until then need about {gbp(need)}. With bills, you are {gbp(wb.short_by)} short."
        )
    e2 = _ev(
        s2,
        {
            "pace": money_value(wb.weekly_pace),
            "weeks_seen": float(wb.weeks_seen),
            "covered": covered,
            "weeks_left": weeks_left,
            "short": money_value(wb.short_by),
            "days_left": float(wb.days_left),
            "need": money_value(need),
        },
        _bank_ref(ctx.snapshot),
    )
    headline = f"You will be {gbp(wb.short_by)} short before {when}"
    if wb.safe_weekly >= MIN_WEEKLY:
        action = f"Spend up to {gbp(wb.safe_weekly)} a week until {when}"
        e3 = _ev(
            f"Spending up to {gbp(wb.safe_weekly)} a week makes it last. You kept to that in {wb.weeks_within} of "
            f"the last {wb.weeks_seen} weeks.",
            {"safe": money_value(wb.safe_weekly), "within": float(wb.weeks_within), "weeks_seen": float(wb.weeks_seen)},
        )
        trade = trade_offs.weekly_budget(wb.safe_weekly, wb.weekly_pace, wb.bills_before, when, when_facts)
    else:  # F-V2-2: bills alone take the cash; say how much is missing and what to do first
        action = f"Plan for {gbp(wb.short_by)} you are missing before {when}"
        e3 = _ev(
            "Pay rent and bills first. Then ask family, or your university's hardship fund or student support, "
            "before you use an overdraft or a card.",
            {},
        )
        trade = trade_offs.shortfall(wb.short_by, wb.bills_before, when, when_facts)
    over = wb.weeks_seen - wb.weeks_within
    conf = over / wb.weeks_seen if wb.weeks_seen else 0.0
    # W-R-1: a projection of usual spending, so "medium", never "high".
    label = (
        f"Your spending was above the safe amount in {over} of the last {wb.weeks_seen} weeks. "
        "A projection of your usual spending"
    )
    return _move(
        ctx,
        "weekly_budget",
        "weekly_budget",
        action,
        headline,
        impact,
        0.0,
        conf,
        label,
        [e1, e2, e3],
        [_bank_ref(ctx.snapshot)],
        _options("weekly", ["freestyle"]),
        TestPeriod(start=ctx.year, end=ctx.year, label=f"This term ({ctx.year})"),
        "budgeting",
        trade,
        dates.iso(wb.next_date),
        weeks=(wb.weeks_left, wb.safe_weekly),
        shortfall=wb.short_by,
        level="medium",
        sample_size=wb.weeks_seen,
        sample_unit="weeks of your spending",
        reason=(
            f"At your usual pace, your money runs out before your {what} on {when}"
            if wb.safe_weekly >= MIN_WEEKLY
            else f"Your bills before your {what} on {when} take all your cash"
        ),
    )


MIN_SPARE = 20.0  # GBP; below this the on-track plan only says what to keep to each week


def _on_track(ctx: Context) -> Candidate | None:
    """ADR 0070: the active move when nothing else applies and the money lasts until the next payment.
    Keep the usual weekly pace and move what is spare into savings. Gain is weeks of cover, never a £ a year."""
    wb = stu.weekly_budget(
        ctx.snapshot, stu.from_snapshot(ctx.snapshot, ctx.today), ctx.today, max(0.0, liquid(ctx.snapshot))
    )
    if wb is None or wb.short_by > 0 or wb.weekly_pace <= 0:
        return None
    when, when_facts = day_text(wb.next_date)
    what = PAYMENT_WORDS.get(wb.next_kind, "next payment")
    weeks_left = round(wb.weeks_left, 1)
    # Only the current account can move: money already in savings is not spare cash.
    current = sum(a.balance for a in ctx.snapshot.accounts if a.kind == "current")
    spare = max(0.0, min(current, wb.cash) - wb.bills_before - wb.weekly_pace * wb.weeks_left)
    e1 = _ev(
        f"You have {gbp(wb.cash)} until your {what} on {when}, in {wb.days_left} days. "
        f"Regular bills before then: {gbp(wb.bills_before)}.",
        {
            "cash": money_value(wb.cash),
            "days_left": float(wb.days_left),
            "bills": money_value(wb.bills_before),
            **when_facts,
        },
        _bank_ref(ctx.snapshot),
    )
    if spare < MIN_SPARE:
        spare = 0.0
    left = f" and {gbp(spare)} in your current account is spare" if spare else ""
    e2 = _ev(
        f"You usually spend about {gbp(wb.weekly_pace)} a week (middle of the last {wb.weeks_seen} weeks). "
        f"At that pace your money lasts the {weeks_left:g} weeks{left}.",
        {
            "pace": money_value(wb.weekly_pace),
            "weeks_seen": float(wb.weeks_seen),
            "weeks_left": weeks_left,
            **({"spare": money_value(spare)} if spare else {}),
        },
        _bank_ref(ctx.snapshot),
    )
    within = sum(1 for w in stu.weekly_spend(ctx.snapshot.transactions, ctx.today) if w <= wb.weekly_pace)
    e3 = _ev(
        f"You kept to that pace in {within} of the last {wb.weeks_seen} weeks.",
        {"within": float(within), "weeks_seen": float(wb.weeks_seen)},
    )
    if spare:
        action = f"Move {gbp(spare)} you will not need into savings"
        reason = f"At your usual pace you have {gbp(spare)} spare before your {what} on {when}"
    else:
        action = f"Keep to about {gbp(wb.weekly_pace)} a week until {when}"
        reason = f"At your usual pace your money lasts until your {what} on {when}"
    conf = within / wb.weeks_seen if wb.weeks_seen else 0.0
    return _move(
        ctx,
        "weekly_budget",
        "weekly_budget",
        action,
        f"You are on track until {when}",
        0.0,
        0.0,
        conf,
        f"You kept to your usual pace in {within} of the last {wb.weeks_seen} weeks",
        [e1, e2, e3],
        [_bank_ref(ctx.snapshot)],
        _options("weekly", ["freestyle"]),
        TestPeriod(start=ctx.year, end=ctx.year, label=f"This term ({ctx.year})"),
        "budgeting",
        trade_offs.on_track(spare, wb.weekly_pace, when, when_facts),
        dates.iso(wb.next_date),
        weeks=(wb.weeks_left, wb.weekly_pace),
        shortfall=0.0,
        level="medium",
        sample_size=wb.weeks_seen,
        sample_unit="weeks of your spending",
        reason=reason,
    )


def _rule(fact_id: str) -> SourceRef:
    f = facts_table.get(fact_id)
    src = "govuk" if f.url.startswith("https://www.gov.uk/") else "official"
    return SourceRef(source=src, series_id=f.url, status="cached", note=f"{f.label} ({f.tax_year})")


def _lifetime_isa(ctx: Context) -> Candidate | None:
    if not pre.lifetime_isa(ctx.snapshot, ctx.today):
        return None
    room = pre.lisa_room(ctx.snapshot, ctx.today)
    costs = known_monthly_costs(ctx.snapshot, ctx.today)
    assert costs is not None
    sav = savings_total(ctx.snapshot)
    bonus = stu.lisa_bonus(room)
    loss = stu.lisa_withdrawal_loss(room)
    rate = facts_table.get("lisa_bonus_rate").value
    cap = facts_table.get("lisa_allowance").value
    max_bonus = facts_table.get("lisa_bonus_max").value
    charge = facts_table.get("lisa_withdrawal_charge").value
    house = facts_table.get("lisa_first_home_price_limit").value
    free_age = facts_table.get("lisa_penalty_free_age").value
    e1 = _ev(
        f"You have {gbp(sav)} in savings. After keeping {EMERGENCY_MONTHS} months of "
        f"{costs_word(ctx.snapshot, ctx.today)} "
        f"({gbp(EMERGENCY_MONTHS * costs)}), {gbp(room)} could go into a Lifetime ISA.",
        {
            "savings": money_value(sav),
            "months": float(EMERGENCY_MONTHS),
            "kept": money_value(EMERGENCY_MONTHS * costs),
            "room": money_value(room),
        },
        _bank_ref(ctx.snapshot),
    )
    e2 = _ev(
        f"The government adds {rate:g}% to what you pay in, up to {gbp(max_bonus)} a year on {gbp(cap)}. "
        f"On {gbp(room)} that is {gbp(bonus)}.",
        {
            "rate": rate,
            "max_bonus": money_value(max_bonus),
            "cap": money_value(cap),
            "room": money_value(room),
            "bonus": money_value(bonus),
        },
        _rule("lisa_bonus_rate"),
    )
    e3 = _ev(
        f"It is for a first home costing up to {gbp(house)}, or for after age {free_age:g}. You must be 18 to 39 to "
        "open one.",
        {"house": money_value(house), "free_age": free_age, "min_age": 18.0, "max_age": 39.0},
        _rule("lisa_first_home_price_limit"),
    )
    return _move(
        ctx,
        "lifetime_isa",
        "lifetime_isa",
        f"Put {gbp(room)} in a Lifetime ISA",
        f"Get a {gbp(bonus)} government bonus",
        bonus,
        -loss,
        1.0,
        SURE_LABEL,
        [e1, e2, e3],
        [_bank_ref(ctx.snapshot), _rule("lisa_bonus_rate"), _rule("lisa_withdrawal_charge")],
        _options("open", ["not_now"]),
        ctx.matched_test_period(),
        "deposit",
        trade_offs.lifetime_isa(room, bonus, loss, charge, house, free_age),
        deterministic=True,
        reason=f"The government adds {rate:g}% to what you pay in, so {gbp(room)} gets a {gbp(bonus)} bonus",
        basis="the bonus is a fixed government rule",
    )


KEEP_CASH_YEARS = 20


def _keep_cash(ctx: Context) -> Candidate | None:
    if not pre.keep_cash(ctx.snapshot, ctx.today):
        return None
    cpi_ref = source_ref(ctx.macro, MacroKey.CPI_INFLATION, ctx.year)
    if cpi_ref is None:
        return None  # inflation is the trade-off: no CPI, no move
    sav = savings_total(ctx.snapshot)
    rate = savings_rate_pct(ctx.snapshot, ctx.today)
    assert rate is not None
    cpi = ctx.macro.value(MacroKey.CPI_INFLATION, ctx.year)
    best_now = _best_savings(ctx.macro, ctx.year)
    interest = sav * rate / 100
    # W-V2-1: keeping cash is the "do nothing" choice; its gain is only the interest ABOVE the best easy-access
    # alternative. When another account pays more, move_savings is the better move and keep_cash is not offered.
    impact = sav * (rate - best_now) / 100
    if impact <= 0:
        return None
    worst = sav * min(0.0, rate - cpi) / 100
    years = [y for y in ctx.macro.years(MacroKey.CPI_INFLATION) if ctx.year - KEEP_CASH_YEARS < y <= ctx.year]
    beat = sum(1 for y in years if _savings_avg(ctx.macro, y) >= ctx.macro.value(MacroKey.CPI_INFLATION, y))
    conf = beat / len(years) if years else 0.0
    e1 = _ev(
        f"Your {gbp(sav)} in savings earns about {pct(rate)} a year: {gbp(interest)}. That is {gbp(impact)} more "
        f"than the best easy-access rate of about {pct(best_now)}.",
        {
            "savings": money_value(sav),
            "rate": pct_value(rate),
            "interest": money_value(interest),
            "impact": money_value(impact),
            "best_rate": pct_value(best_now),
        },
        _bank_ref(ctx.snapshot),
    )
    e2 = _ev(f"Prices rose {pct(cpi)} in {ctx.year}.", {"cpi": pct_value(cpi), "year": float(ctx.year)}, cpi_ref)
    e3 = _ev(
        f"Average savings rates beat price rises in {beat} of the last {len(years)} years.",
        {"beat": float(beat), "years": float(len(years))},
        source_ref(ctx.macro, MacroKey.SAVINGS_RATE, ctx.year),
    )
    return _move(
        ctx,
        "keep_cash",
        "keep_cash",
        "Keep your savings where they are",
        f"Your savings earn {gbp(impact)} a year more than elsewhere",
        impact,
        worst,
        conf,
        f"Cash beat price rises in {beat} of the last {len(years)} years",
        [e1, e2, e3],
        [_bank_ref(ctx.snapshot), cpi_ref],
        _options("hold", []),
        None,
        "inflation",
        trade_offs.keep_cash(sav, rate, cpi, ctx.year, invests(ctx.snapshot)),
        sample_size=len(years),
        sample_unit="years",
        reason="Your savings already earn more than the best easy-access rate",
    )


# ---------- fallback ----------


def _fallback(ctx: Context) -> Candidate:
    """Shown when no move's precondition holds. Months of cover only with known costs (ADR 0053 bug 5)."""
    costs = known_monthly_costs(ctx.snapshot, ctx.today)
    cash = max(0.0, liquid(ctx.snapshot))
    months = round(cash / costs, 1) if costs is not None else None
    sav = savings_total(ctx.snapshot)
    e1 = (
        _ev(
            f"Your cash and savings cover {months:g} months of {costs_word(ctx.snapshot, ctx.today)}.",
            {"months": months},
            _bank_ref(ctx.snapshot),
        )
        if months is not None
        else _ev("Add your monthly costs to see how long your cash would last.", {})
    )
    evidence = [
        e1,
        _ev(f"You have {gbp(sav)} in savings.", {"savings": money_value(sav)}, _bank_ref(ctx.snapshot)),
        _ev("We found no bill, rate or debt that needs action now.", {}),
    ]
    return _move(
        ctx,
        "build_emergency_fund",
        "build_emergency_fund",
        "Keep your safety net topped up",
        "Nothing urgent this month",
        0.0,
        0.0,
        0.0,
        "Nothing urgent. Your money looks on track",
        evidence,
        [_bank_ref(ctx.snapshot)],
        _options("save", ["keep"]),
        None,
        "emergency-fund",
        trade_offs.keep_buffer(cash),
        cover_months=months,
        no_level=True,
        reason="We found no bill, rate or debt that needs action now",
    )


BUILDERS: tuple[Callable[[Context], Candidate | None], ...] = (
    _mortgage,
    _debt,
    _savings,
    _energy,
    _emergency,
    _subscription,
    _budget,
    _weekly_budget,
    _lifetime_isa,
    _keep_cash,
)


def built(ctx: Context) -> list[Candidate]:
    """Every candidate move the engine built and scored for this user (a builder whose precondition fails builds
    nothing). Its length is `options_compared` (ADR 0069)."""
    return [c for c in (b(ctx) for b in BUILDERS) if c is not None]


def candidates(ctx: Context, evaluated: Sequence[Candidate] | None = None) -> list[Candidate]:
    out = [c for c in (built(ctx) if evaluated is None else evaluated) if c.move.impact_per_year > 0]

    def key(c: Candidate) -> tuple[int, bool, float, int, int]:
        """Urgent first (F-V2-2, F-R-1): money running short before the next payment beats every yearly gain.
        Then score, nearer deadline, kind order."""
        urgent = 0 if c.move.kind == "weekly_budget" and (c.move.shortfall or 0) > 0 else 1
        days = c.move.days_left if c.move.days_left is not None else 10**6
        return (urgent, is_no_op(c.move), -round(c.score, 6), days, KIND_ORDER.index(c.move.kind))

    return sorted(out, key=key)


NO_OP_KINDS: frozenset[str] = frozenset({"keep_cash"})


def is_no_op(move: Move) -> bool:
    """'No action needed' moves (keep your savings where they are, the nothing-urgent fallback). ADR 0070: they may
    only be runners-up; an active move always ranks first."""
    fallback = move.kind == "build_emergency_fund" and move.confidence_level is None and move.impact_per_year == 0
    return move.kind in NO_OP_KINDS or fallback


def build_context(snapshot: FinanceSnapshot, macro: MacroTable, today: dates.date, seed: int = 0) -> Context:
    year = min(today.year, latest_year(macro))
    prof, _ = profile(snapshot, today)
    twins = nearest_twins(prof, macro, year)[:K_TWINS]
    return Context(snapshot=snapshot, macro=macro, today=today, year=year, profile=prof, seed=seed, twins=twins)


def next_move(snapshot: FinanceSnapshot, macro: MacroTable, today: dates.date, seed: int = 0) -> NextMoveResponse:
    """ONE top move and up to 2 runners-up. `generated_at` is a placeholder: the API sets server time."""
    ctx = build_context(snapshot, macro, today, seed)
    evaluated = built(ctx)
    ranked = candidates(ctx, evaluated)
    if not any(not is_no_op(c.move) for c in ranked):
        # ADR 0070: no real action applies, so the top move is the on-track weekly plan when the data allows,
        # and "nothing urgent" may follow only as a runner-up.
        plan = _on_track(ctx)
        if plan is not None:
            evaluated = [*evaluated, plan]
        ranked = [*([plan] if plan is not None else []), *ranked] or [_fallback(ctx)]
        if plan is not None and len(ranked) < 3:
            ranked.append(_fallback(ctx))
    top = ranked[0].move
    backtest = mortgage_backtest(macro, ctx.year) if top.kind in ("fix_mortgage", "remortgage") else None
    shown = [top, *[c.move for c in ranked[1:3]]]
    refs = [r for mv in shown for r in [*mv.sources, *(e.source for e in mv.evidence if e.source is not None)]]
    if any(mv.testable or mv.kind in TWIN_KINDS for mv in shown):
        refs += context_inputs(ctx)
    decision = decision_sources(refs)
    return NextMoveResponse(
        meta=finance_meta(snapshot),
        top=top,
        runners_up=[c.move for c in ranked[1:3]],
        options_compared=max(len(evaluated), len(shown)),
        backtest=backtest,
        decision_sources=decision,
        decision_source_count=count_decision_sources(decision),
        generated_at=f"{dates.iso(today)}T00:00:00Z",
    )


# ---------- decision sources (ADR 0032) ----------

DECISION_PROVIDERS: dict[str, str] = {
    "boe": "Bank of England",
    "ons": "ONS",
    "nomis": "Nomis",
    "landregistry": "HM Land Registry",
    "companieshouse": "Companies House",
    "octopus": "Octopus Energy",
    "frankfurter": "Frankfurter (FX)",
    "coingecko": "CoinGecko",
}
TWIN_KINDS: frozenset[str] = frozenset(
    {"fix_mortgage", "remortgage", "move_savings", "switch_energy", "pay_off_debt", "build_emergency_fund"}
)
_STATUS_ORDER = {"live": 0, "cached": 1, "mock": 2, "unavailable": 3}


def context_inputs(ctx: Context) -> list[SourceRef]:
    """Inputs read by twins (synthetic population) and period matching for `ctx.year`."""
    keys = [
        (MacroKey.BANK_RATE, None),
        (MacroKey.CPI_INFLATION, None),
        (MacroKey.HOUSE_PRICE_CHANGE, None),
        (MacroKey.UNEMPLOYMENT, None),
        (MacroKey.STOCK_RETURN, None),
        (MacroKey.MEDIAN_PAY, ctx.profile.region),
        (MacroKey.OWNER_OCCUPIED_SHARE, ctx.profile.region),
        (MacroKey.HOUSE_PRICE, ctx.profile.region),
    ]
    return [r for r in (source_ref(ctx.macro, k, ctx.year, reg) for k, reg in keys) if r is not None]


def count_decision_sources(sources: Sequence[SourceRef]) -> int:
    """ADR 0032: an unavailable source is listed but not counted."""
    return sum(1 for r in sources if r.status != "unavailable")


def decision_sources(refs: Sequence[SourceRef]) -> list[SourceRef]:
    """One SourceRef per decision provider actually read (ADR 0032): the user's bank data and the providers in
    DECISION_PROVIDERS. Game-only and context sources are dropped. series_id lists the series read; status is the
    weakest one (live, then cached, then mock, then unavailable)."""
    groups: dict[str, list[SourceRef]] = {}
    for r in refs:
        key = r.source if r.source.startswith("bank:") or r.source in DECISION_PROVIDERS else None
        if key is not None:
            groups.setdefault(key, []).append(r)
    out: list[SourceRef] = []
    for key in sorted(groups, key=lambda k: (not k.startswith("bank:"), k)):
        items = groups[key]
        series = sorted({r.series_id for r in items})
        status = max((r.status for r in items), key=lambda st: (_STATUS_ORDER.get(st, 3), st))
        label = "Your bank data" if key.startswith("bank:") else DECISION_PROVIDERS[key]
        out.append(SourceRef(source=key, series_id=",".join(series)[:200], status=status, note=label))
    return out


# ---------- Test it ----------


def option_policy(move: Move, option_id: str) -> dict[str, str]:
    """Sim policy for one option of `move` (lifeline_sim play_scenario). Every option of a move uses the same
    tag key, so the event sets match across options. Mortgage moves also set the deal end year."""
    if option_id not in {o.id for o in move.options}:
        raise ValueError(f"unknown option {option_id} for move {move.id}")
    if move.kind not in MOVE_TAG or move.test_period is None:
        raise ValueError(f"move {move.id} cannot be tested")
    policy = {MOVE_TAG[move.kind]: option_id}
    if move.kind in MOVE_FOCUS:
        policy[POLICY_FOCUS] = MOVE_FOCUS[move.kind]
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
            macro,
            starts,
            [bal],
            bal,
            BACKTEST_YEARS_LEFT,
            q2,
            q5,
            svr,
            tracker,
            stress_start,
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
