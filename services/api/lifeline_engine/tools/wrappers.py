"""Engine tools for Ask Penny (ADR 0031, 0033, 0034). Pure functions: no I/O, no clock, no global RNG.

Every tool returns ToolResult = {result, facts, sources}:
- result: structured JSON for the model (no free text from untrusted sources is added here).
- facts: every number the model may say, as ChatFact (id, value, unit, label, source_id). Ids are stable for the
  same inputs, so highlights can point at them.
- sources: SourceRef list. A fact's source_id is `source_id(ref)` of one of them.
Inputs are Pydantic models with bounds (ADR 0034). Callers validate the model's tool arguments with them.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lifeline_contracts.chat import ChatFact
from lifeline_contracts.domain import CharacterSpec, IsoDate, Life, ShortId, SourceRef
from lifeline_contracts.finance import FinanceSnapshot
from lifeline_contracts.macro import MacroKey, MacroTable
from lifeline_contracts.next_move import Move, NextMoveResponse
from lifeline_engine.macro_access import source_ref
from lifeline_engine.money import dates, overview, subscriptions_response, upcoming_bills
from lifeline_engine.money.predict import WeatherDays, backtest, predict_day
from lifeline_engine.money.profile import debt_total, liquid, monthly_spend, profile, savings_total
from lifeline_engine.money.recurring import detect_salary
from lifeline_engine.next_move import next_move, option_policy, scenario_years
from lifeline_engine.tools import facts_table
from lifeline_engine.tools.cashflow import MAX_MONTHS, WhatIf, cash_flow_projection, months_of_cover

Unit = Literal["gbp", "gbp_per_month", "gbp_per_year", "percent", "months", "years", "count", "date_year"]
ToolName = Literal[
    "next_move",
    "test_move",
    "finance_summary",
    "spend_prediction",
    "cash_flow_projection",
    "life_replay",
    "facts_table",
]

MIN_REPLAY_YEAR = 1990
MAX_REPLAY_YEAR = 2026
MAX_REPLAY_SPAN = 20


# ---------- result model ----------


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: dict[str, Any]
    facts: list[ChatFact]
    sources: list[SourceRef]
    lives: list[Life] = Field(default_factory=list, exclude=True, description="Lives to store (not sent to the model)")


def source_id(ref: SourceRef) -> str:
    return f"{ref.source}:{ref.series_id}"


class _Facts:
    """Collects facts and sources. Rounds values to what a sentence may show."""

    def __init__(self) -> None:
        self.facts: list[ChatFact] = []
        self.sources: dict[str, SourceRef] = {}

    def src(self, ref: SourceRef | None) -> str | None:
        if ref is None:
            return None
        sid = source_id(ref)
        self.sources.setdefault(sid, ref)
        return sid

    def add(self, fid: str, value: float, unit: Unit, label: str, ref: SourceRef | None = None) -> float:
        v = _round(value, unit)
        self.facts.append(ChatFact(id=fid, value=v, unit=unit, label=label[:120], source_id=self.src(ref)))
        return v

    def done(self, result: dict[str, Any], lives: Sequence[Life] = (), prefix: str = "tool") -> ToolResult:
        """Every number inside a text field of `result` also becomes a fact (id `<prefix>.text.<path>.n<i>`),
        so the verifier needs no exception for engine-written text (actions, headlines, labels)."""
        for path, text in _texts(result):
            for i, (value, unit) in enumerate(_numbers_with_units(text), 1):
                self.add(f"{prefix}.text.{path}.n{i}", value, unit, f"Number in {path.replace('.', ' ')}")
        return ToolResult(result=result, facts=self.facts, sources=list(self.sources.values()), lives=list(lives))


_SKIP_KEYS = frozenset({"id", "kind", "concept_id", "fact_prefix", "life_id", "move_id", "option_id", "date",
                        "due_date", "as_of", "data_status", "status", "feature", "fact_id", "question"})
# Untrusted text (ADR 0034, V6 T2-F1): never a source of facts. Engine text that embeds a payee name uses
# money.text.clean_name, so it carries no number from the name.
UNTRUSTED_KEYS = frozenset({"merchant", "name", "names", "description", "payee", "headline_news", "standfirst",
                            "subscriptions", "bills"})
_NUM = re.compile(r"(£)?(\d[\d,]*(?:\.\d+)?)(%)?")


def _texts(obj: Any, path: str = "") -> list[tuple[str, str]]:
    """(dotted path, text) for every string in `obj`, skipping ids, enums and ISO dates."""
    out: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _SKIP_KEYS or k in UNTRUSTED_KEYS:
                continue
            out += _texts(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += _texts(v, f"{path}.{i}")
    elif isinstance(obj, str) and _NUM.search(obj):
        out.append((path, obj))
    return out


def _numbers_with_units(text: str) -> list[tuple[float, Unit]]:
    out: list[tuple[float, Unit]] = []
    for pound, num, percent in _NUM.findall(text):
        value = float(num.replace(",", ""))
        unit: Unit
        if pound:
            unit = "gbp"
        elif percent:
            unit = "percent"
        elif value.is_integer() and 1900 <= value <= 2100:
            unit = "date_year"
        else:
            unit = "count"
        out.append((value, unit))
    return out


def _round(value: float, unit: Unit) -> float:
    if unit in ("count", "date_year", "years"):
        return float(round(value))
    if unit in ("percent", "months"):
        return round(value, 2) if unit == "percent" else round(value, 1)
    return float(round(value)) if abs(value) >= 100 else round(value, 2)


def bank_source(snapshot: FinanceSnapshot) -> SourceRef:
    return SourceRef(
        source=f"bank:{snapshot.source}",
        series_id=snapshot.persona or "transactions",
        status=snapshot.status,
        note="Sample data" if snapshot.status == "mock" else None,
    )


def unit_for(key: str) -> Unit:
    """Unit of an evidence fact from its key (next_move evidence facts carry no unit)."""
    k = key.lower()
    if k.endswith(("_start", "_end")) and ("period" in k or "stress" in k):
        return "date_year"
    if "rate" in k or "pct" in k or "percent" in k:
        return "percent"
    if "regret_weight" in k or "ratio" in k:
        return "count"
    if "years" in k:
        return "years"
    if "months" in k:
        return "months"
    if k in ("twins", "periods", "count", "rose", "under", "history", "days_left") or "days" in k:
        return "count"
    if k.startswith("name_") or k.startswith("alt_fix") or k == "fix_years":
        return "count"
    return "gbp"


# ---------- inputs (ADR 0034: typed and bounded) ----------


class _I(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NextMoveInput(_I):
    pass


class TestMoveInput(_I):
    move_id: ShortId = Field(description="A move id from next_move, or 'top'")
    option_ids: list[ShortId] | None = Field(default=None, max_length=4)


class FinanceSummaryInput(_I):
    pass


class SpendPredictionInput(_I):
    date: IsoDate | None = Field(default=None, description="Default: the snapshot day")


class CashFlowInput(_I):
    months: int = Field(default=6, ge=1, le=MAX_MONTHS)
    what_if: list[WhatIf] = Field(default_factory=list, max_length=5)


class LifeReplayInput(_I):
    start_year: int = Field(ge=MIN_REPLAY_YEAR, le=MAX_REPLAY_YEAR - 1)
    end_year: int = Field(ge=MIN_REPLAY_YEAR + 1, le=MAX_REPLAY_YEAR)

    @model_validator(mode="after")
    def _span(self) -> LifeReplayInput:
        if not 1 <= self.end_year - self.start_year <= MAX_REPLAY_SPAN:
            raise ValueError(f"end_year must be 1 to {MAX_REPLAY_SPAN} years after start_year")
        return self


class FactsTableInput(_I):
    ids: list[ShortId] | None = Field(default=None, max_length=40)
    topic: facts_table.Topic | None = None


# ---------- next_move ----------


def _move_facts(fx: _Facts, prefix: str, mv: Move) -> dict[str, Any]:
    fx.add(f"{prefix}.impact_per_year", mv.impact_per_year, "gbp_per_year", f"{mv.action}: expected gain a year")
    fx.add(f"{prefix}.worst_case_per_year", mv.worst_case_per_year, "gbp_per_year",
           f"{mv.action}: worst case a year")
    fx.add(f"{prefix}.confidence", mv.confidence * 100, "percent", f"{mv.action}: confidence")
    if mv.days_left is not None:
        fx.add(f"{prefix}.days_left", mv.days_left, "count", "Days until the deadline")
    if mv.test_period is not None:
        fx.add(f"{prefix}.test_period.start", mv.test_period.start, "date_year", "Test period start")
        fx.add(f"{prefix}.test_period.end", mv.test_period.end, "date_year", "Test period end")
    for o in mv.options:
        years = {"fix_5y": 5, "fix_3y": 3, "fix_2y": 2}.get(o.id)
        if years is not None:
            fx.add(f"{prefix}.option.{o.id}.years", years, "years", f"{o.label}: fixed years")
    for j, e in enumerate(mv.evidence, 1):
        for key, val in e.facts.items():
            fx.add(f"{prefix}.e{j}.{key}", val, unit_for(key), f"{mv.action}: {key.replace('_', ' ')}", e.source)
    for ref in mv.sources:
        fx.src(ref)
    return {
        "id": mv.id,
        "kind": mv.kind,
        "action": mv.action,
        "headline": mv.headline,
        "confidence_label": mv.confidence_label,
        "evidence": [e.text for e in mv.evidence],
        "options": [{"id": o.id, "label": o.label, "recommended": o.is_recommended} for o in mv.options],
        "testable": mv.testable,
        "test_period": mv.test_period.model_dump() if mv.test_period else None,
        "concept_id": mv.concept_id,
        "fact_prefix": prefix,
    }


def tool_next_move(snapshot: FinanceSnapshot, macro: MacroTable, today: dates.date, seed: int = 0,
                   response: NextMoveResponse | None = None) -> ToolResult:
    """Pass `response` to reuse a stored NextMoveResponse (same numbers as the card)."""
    r = response if response is not None else next_move(snapshot, macro, today, seed)
    fx = _Facts()
    top = _move_facts(fx, "next_move.top", r.top)
    runners = [_move_facts(fx, f"next_move.runner_{i}", m) for i, m in enumerate(r.runners_up, 1)]
    if r.backtest is not None:
        fx.add("next_move.backtest.hit_rate", r.backtest.hit_rate * 100, "percent", "Backtest: engine right")
        fx.add("next_move.backtest.baseline_hit_rate", r.backtest.baseline_hit_rate * 100, "percent",
               "Backtest: always fix for 2 years right")
        fx.add("next_move.backtest.n", r.backtest.n, "count", "Backtest: years tested")
    fx.add("next_move.decision_source_count", r.decision_source_count, "count", "Decision sources")
    for ref in r.decision_sources:
        fx.src(ref)
    return fx.done(prefix="next_move", result={
        "question": r.question,
        "top": top,
        "runners_up": runners,
        "backtest": r.backtest.model_dump() if r.backtest else None,
        "decision_source_count": r.decision_source_count,
    })


# ---------- test_move ----------


def shift_character(character: CharacterSpec, this_year: int, start_year: int) -> CharacterSpec:
    """Today's you, placed in a past period: same age at start_year as now, same money figures."""
    birth = character.birth_year - (this_year - start_year)
    return character.model_copy(update={"birth_year": max(1930, min(2026, birth))})


def tool_test_move(snapshot: FinanceSnapshot, macro: MacroTable, today: dates.date, inp: TestMoveInput,
                   seed: int, life_id_prefix: str = "chat", response: NextMoveResponse | None = None) -> ToolResult:
    """Replay each option of a move through its test period with the same seed (lifeline_sim.play_scenario)."""
    from lifeline_sim import api as sim

    r = response if response is not None else next_move(snapshot, macro, today, seed)
    moves = {m.id: m for m in [r.top, *r.runners_up]}
    move = r.top if inp.move_id == "top" else moves.get(inp.move_id)
    if move is None:
        raise ValueError(f"unknown move {inp.move_id}")
    if not move.testable or move.test_period is None:
        raise ValueError(f"move {move.id} cannot be tested")
    options = [o for o in move.options if inp.option_ids is None or o.id in inp.option_ids]
    if not options:
        raise ValueError("no matching options")
    start, end = scenario_years(move)
    _, char = profile(snapshot, today)
    char = shift_character(char, today.year, start)
    fx = _Facts()
    for ref in move.sources:
        fx.src(ref)
    out: list[dict[str, Any]] = []
    lives: list[Life] = []
    for o in options:
        life = sim.play_scenario(f"{life_id_prefix}-{move.id}-{o.id}"[:64], char, start, end,
                                 option_policy(move, o.id), seed, macro)
        lives.append(life)
        cost = sim.scenario_cost(life, macro)
        p = f"test_move.{move.id}.{o.id}"
        fx.add(f"{p}.end_net_worth", life.finances.net_worth, "gbp", f"{o.label}: net worth at the end")
        fx.add(f"{p}.total_cost", cost, "gbp", f"{o.label}: total paid")
        fx.add(f"{p}.missed_payments", life.index.missed_payments, "count", f"{o.label}: missed payments")
        out.append({"option_id": o.id, "label": o.label, "recommended": o.is_recommended, "life_id": life.id,
                    "fact_prefix": p})
    fx.add(f"test_move.{move.id}.period_start", move.test_period.start, "date_year", "Test period start")
    fx.add(f"test_move.{move.id}.period_end", move.test_period.end, "date_year", "Test period end")
    return fx.done({"move_id": move.id, "period": move.test_period.model_dump(), "outcomes": out}, lives,
                   prefix="test_move")


# ---------- finance_summary ----------


def tool_finance_summary(snapshot: FinanceSnapshot, today: dates.date | None = None) -> ToolResult:
    day = today or dates.parse(snapshot.as_of)
    ref = bank_source(snapshot)
    fx = _Facts()
    ov = overview(snapshot)
    subs = subscriptions_response(snapshot, day)
    bills = upcoming_bills(snapshot.transactions, day)
    inc = detect_salary(snapshot.transactions)
    spend = monthly_spend(snapshot, day)
    cash = liquid(snapshot)
    fx.add("finance.balance", ov.balance, "gbp", "Cash in current and savings accounts", ref)
    fx.add("finance.net_worth", ov.net_worth, "gbp", "Net worth", ref)
    fx.add("finance.monthly_income", inc.monthly_net if inc else 0.0, "gbp_per_month", "Take-home pay a month", ref)
    fx.add("finance.monthly_spend", spend, "gbp_per_month", "Average spending a month (last 3 months)", ref)
    fx.add("finance.subscriptions_total", subs.monthly_total, "gbp_per_month", "Subscriptions a month", ref)
    fx.add("finance.subscriptions_count", subs.count, "count", "Number of subscriptions", ref)
    fx.add("finance.bills_next_30_days", sum(b.amount for b in bills), "gbp", "Bills due in the next 30 days", ref)
    fx.add("finance.debt", debt_total(snapshot), "gbp", "Owed on cards and loans", ref)
    fx.add("finance.savings", savings_total(snapshot), "gbp", "Cash savings", ref)
    cover = months_of_cover(cash, spend)
    if cover is not None:
        fx.add("finance.months_of_cover", cover, "months", "Months of spending that cash covers", ref)
    return fx.done(prefix="finance", result={
        "as_of": snapshot.as_of,
        "data_status": snapshot.status,
        "subscriptions": [{"id": s.id, "merchant": s.merchant, "price_rise": s.price_rise is not None}
                          for s in subs.items],
        "bills": [{"id": b.id, "name": b.name, "due_date": b.due_date, "status": b.status} for b in bills],
    })


# ---------- spend_prediction ----------


def tool_spend_prediction(snapshot: FinanceSnapshot, inp: SpendPredictionInput,
                          holidays: Collection[dates.date] = (), weather: WeatherDays | None = None) -> ToolResult:
    day = dates.parse(inp.date) if inp.date else dates.parse(snapshot.as_of)
    p = predict_day(snapshot, day, holidays, weather)
    bt = backtest(snapshot, holidays, weather)
    ref = bank_source(snapshot)
    fx = _Facts()
    fx.add("spend.predicted", p.predicted, "gbp", "Predicted spend for the day", ref)
    fx.add("spend.low", p.low, "gbp", "Low end of the range (10%)", ref)
    fx.add("spend.high", p.high, "gbp", "High end of the range (90%)", ref)
    fx.add("spend.baseline", p.baseline, "gbp", "A typical day", ref)
    for i, rs in enumerate(p.reasons, 1):
        fx.add(f"spend.reason_{i}", rs.effect, "gbp", rs.label, ref)
    fx.add("spend.model_mae", bt.mae, "gbp", "Model average error in the backtest", ref)
    fx.add("spend.baseline_mae", bt.baseline_mae, "gbp", "Weekday-average error in the backtest", ref)
    if p.actual is not None:
        fx.add("spend.actual", p.actual, "gbp", "Actual spend that day", ref)
    return fx.done(prefix="spend", result={
        "date": dates.iso(day),
        "reasons": [{"feature": r.feature, "label": r.label, "fact_id": f"spend.reason_{i}"}
                    for i, r in enumerate(p.reasons, 1)],
        "is_bank_holiday": p.is_bank_holiday,
    })


# ---------- cash_flow_projection ----------


def tool_cash_flow_projection(snapshot: FinanceSnapshot, inp: CashFlowInput) -> ToolResult:
    pr = cash_flow_projection(snapshot, min(inp.months, MAX_MONTHS), inp.what_if)
    ref = bank_source(snapshot)
    fx = _Facts()
    fx.add("cashflow.start_balance", pr.start_balance, "gbp", "Cash today", ref)
    fx.add("cashflow.monthly_income", pr.monthly_income, "gbp_per_month", "Take-home pay a month", ref)
    fx.add("cashflow.monthly_outgoings", pr.monthly_outgoings, "gbp_per_month", "Spending a month", ref)
    if pr.months_of_cover is not None:
        fx.add("cashflow.months_of_cover", pr.months_of_cover, "months", "Months cash covers with no income", ref)
    fx.add("cashflow.lowest_balance", pr.lowest_balance, "gbp", "Lowest balance", ref)
    fx.add("cashflow.lowest_month", pr.lowest_month, "count", "Month of the lowest balance", ref)
    fx.add("cashflow.end_balance", pr.end_balance, "gbp", "Balance at the end", ref)
    fx.add("cashflow.months", inp.months, "months", "Months projected", ref)
    if pr.run_out_month is not None:
        fx.add("cashflow.run_out_month", pr.run_out_month, "count", "Month the money runs out", ref)
    if pr.mortgage_extra_per_month:
        fx.add("cashflow.mortgage_extra", pr.mortgage_extra_per_month, "gbp_per_month",
               "Extra mortgage payment a month after the rate rise", ref)
    if pr.cancelled_per_month:
        fx.add("cashflow.cancelled", pr.cancelled_per_month, "gbp_per_month", "Saved a month by cancelling", ref)
    return fx.done(prefix="cashflow", result={
        "what_if": [w.model_dump() for w in inp.what_if],
        "runs_out": pr.run_out_month is not None,
        "unknown_subscription_ids": list(pr.unknown_subscription_ids),
        "path": [{"month": r.month, "date": r.date, "balance": r.balance} for r in pr.rows],
    })


# ---------- life_replay ----------


def tool_life_replay(snapshot: FinanceSnapshot, macro: MacroTable, today: dates.date, inp: LifeReplayInput,
                     life_id: ShortId, seed: int) -> ToolResult:
    """A Life replay of the user (profile from the snapshot, same age at start_year as today) with default choices.
    Events run start_year + 1 .. end_year. The Life is in `lives` for the caller to store."""
    from lifeline_sim import api as sim

    _, char = profile(snapshot, today)
    char = shift_character(char, today.year, inp.start_year)
    life = sim.play_scenario(life_id, char, inp.start_year, inp.end_year, {}, seed, macro)
    fx = _Facts()
    start_nw = life.history[0].net_worth if life.history else life.finances.net_worth
    worst = min(
        ((h.year, h.net_worth - p.net_worth) for p, h in zip(life.history, life.history[1:], strict=False)),
        key=lambda x: (x[1], x[0]),
        default=(inp.start_year, 0.0),
    )
    user = bank_source(snapshot)
    sim_ref = source_ref(macro, MacroKey.BANK_RATE, inp.start_year) or user
    fx.add("life.start_net_worth", start_nw, "gbp", "Net worth at the start", user)
    fx.add("life.end_net_worth", life.finances.net_worth, "gbp", "Net worth at the end", sim_ref)
    fx.add("life.missed_payments", life.index.missed_payments, "count", "Missed payments", sim_ref)
    fx.add("life.worst_year", worst[0], "date_year", "Worst year", sim_ref)
    fx.add("life.worst_year_change", worst[1], "gbp", "Net worth change in the worst year", sim_ref)
    fx.add("life.start_year", inp.start_year, "date_year", "Replay start", sim_ref)
    fx.add("life.end_year", inp.end_year, "date_year", "Replay end", sim_ref)
    for v in macro.values.values():
        if v.year == inp.start_year and v.region is None and v.key.value in ("bank_rate", "cpi_inflation"):
            fx.src(SourceRef(source=v.source, series_id=v.series_id, status=v.status, note=v.note))
    fx.add("life.age", life.age, "years", "Age at the end of the replay", user)
    return fx.done({"life_id": life.id, "alive": life.alive, "age": life.age}, [life], prefix="life")


# ---------- facts_table ----------


def tool_facts_table(inp: FactsTableInput) -> ToolResult:
    fx = _Facts()
    rows = facts_table.lookup(inp.ids, inp.topic)
    for f in rows:
        ref = SourceRef(source="govuk", series_id=f.url, status="cached", note=f"{f.tax_year}, checked {f.as_of}")
        fx.add(f.id, f.value, f.unit, f"{f.label} ({f.tax_year})", ref)
    return fx.done({"tax_year": facts_table.TAX_YEAR, "ids": [f.id for f in rows]}, prefix="rule")


# ---------- registry for the chat loop (W5) ----------

TOOL_INPUTS: dict[ToolName, type[BaseModel]] = {
    "next_move": NextMoveInput,
    "test_move": TestMoveInput,
    "finance_summary": FinanceSummaryInput,
    "spend_prediction": SpendPredictionInput,
    "cash_flow_projection": CashFlowInput,
    "life_replay": LifeReplayInput,
    "facts_table": FactsTableInput,
}

TOOL_DESCRIPTIONS: dict[ToolName, str] = {
    "next_move": "The user's next money move: top move and up to 2 runners-up, with evidence numbers.",
    "test_move": "Replay each option of a move through its past test period (stress test) with the same seed.",
    "finance_summary": "Balances, income, spending, subscriptions, bills, debt, savings and months of cover.",
    "spend_prediction": "Predicted spend for one day with range and the top 3 reasons in pounds.",
    "cash_flow_projection": "Month-by-month balance with optional what-ifs: job_loss, rate_rise, one_off_cost, "
    "cancel subscriptions. Returns months of cover, lowest balance and the month money runs out.",
    "life_replay": "Replay the user's life through a past period (1990-2026) with default choices.",
    "facts_table": "Official UK rule numbers for 2026/27 (ISA, income tax, National Insurance, student loans).",
}


def tool_schemas() -> list[dict[str, Any]]:
    """Anthropic tool definitions: name, description, input_schema (JSON Schema from the input models)."""
    return [
        {"name": name, "description": TOOL_DESCRIPTIONS[name], "input_schema": model.model_json_schema()}
        for name, model in TOOL_INPUTS.items()
    ]
