"""Penny's `forecast` tool (PENNY_V3_BUILD.md B3.7, D4, ADR 0072).

The tool returns the user's forecast exactly as GET /v1/forecast computes it (same engine call, same stored
buffer %), so every number Penny says about the weekly budget is the number on the card and on "The maths".
This module turns a `Forecast` (lifeline_contracts.forecast) into a ToolOutput: a short result for the model and
one fact per number. Every fact is the user's own money data (source: their statement).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from lifeline_contracts.chat import ChatFact
from lifeline_contracts.domain import SourceRef
from lifeline_contracts.forecast import Forecast, WhatIfResult
from lifeline_explain.chat_tools import ToolOutput, ToolSourceLink, source_key

TOOL = "forecast"
DESCRIPTION = (
    "The user's forecast, the app's Next Move: will their money last until their next money arrives, and how much "
    "they can spend each week and each day. Returns money now (current accounts), bills before the next money, the "
    "buffer they chose, days to cover, per week and per day, usual weekly spending (last 4 weeks), on track or "
    "running short, spare or the run-out date, the next money and one suggestion. Set stress_2022 to true for "
    "'what if prices rose like in 2022'. Use it for any weekly budget, 'can I afford' or 'will my money last' question."
)
STEP_LABEL = "Checking your forecast…"

WHAT_IF_TOOL = "forecast_what_if"
WHAT_IF_DESCRIPTION = (
    "Rerun the user's forecast with changes and compare before and after. Map the question to changes: "
    "'Can I afford a £60 concert on the 30th?' -> one_off_cost, amount 60, that date, label. 'What if my loan is a "
    "week late?' -> move_payment, target the next money's label, date = its date + 7 days. 'What if I work 2 extra "
    "shifts?' -> two extra_income changes, each amount = usual_pay from the forecast tool, date of that pay. "
    "'What if my phone bill goes up to £20?' -> recurring_cost_change, target the bill, amount = new monthly amount. "
    "Dates are YYYY-MM-DD. If you cannot infer an amount or a date, ask the user once instead of calling this tool."
)
WHAT_IF_STEP_LABEL = "Trying your what-if…"

Unit = Literal["gbp", "gbp_per_month", "gbp_per_year", "percent", "months", "years", "count", "date_year"]


def short_window(fc: Forecast) -> bool:
    """Under 14 days to the next money the card shows the total until that date, never a weekly figure."""
    return fc.budget_period == "until_next_money"


def until_text(fc: Forecast) -> str:
    if fc.next_money is None:
        return "the next money"
    d = date.fromisoformat(fc.next_money.date[:10])
    return f"{d.day} {d.strftime('%B')}"


def statement_ref(fc: Forecast) -> SourceRef:
    return SourceRef(source="statement", series_id="forecast", status=fc.meta.data_status, note="Your statement")


def forecast_output(fc: Forecast, prefix: str = "forecast", label_prefix: str = "") -> ToolOutput:
    """Facts (ids `<prefix>.*`, default `forecast.*`) for every number on the card, The maths and the breakdown."""
    ref = statement_ref(fc)
    sid = source_key(ref)
    sources = [ref]
    links: list[ToolSourceLink | None] = [None]
    facts: list[ChatFact] = []

    def add(key: str, value: float, unit: Unit, label: str, source_id: str = sid) -> None:
        facts.append(ChatFact(id=f"{prefix}.{key}", value=round(float(value), 2), unit=unit,
                              label=f"{label_prefix}{label}"[:120], source_id=source_id))  # fmt: skip

    def add_date(key: str, iso: str, what: str, source_id: str = sid) -> None:
        d = date.fromisoformat(iso[:10])
        add(f"{key}.day", d.day, "count", f"Day of the month: {what} ({d.strftime('%B')})", source_id)
        add(f"{key}.year", d.year, "date_year", f"Year: {what}", source_id)

    add("money_now", fc.money_now, "gbp", "Money now in current accounts (savings not counted)")
    add("bills_total", fc.bills_total, "gbp", "Bills due before the next money")
    add("buffer_pct", fc.buffer_pct, "percent", "Buffer you chose")
    add("buffer_amount", fc.buffer_amount, "gbp", "Buffer kept aside")
    add("days", fc.days, "count", "Days to cover until the next money")
    add("weeks", round(fc.days / 7, 1), "count", "Weeks to cover until the next money")
    if short_window(fc):
        add("to_spend", fc.to_spend, "gbp", f"You can spend in total until {until_text(fc)}")
    else:
        add("per_week", fc.per_week, "gbp", "You can spend a week")
    add("per_day", fc.per_day, "gbp", "You can spend a day")
    add("usual_weekly", fc.usual_weekly, "gbp", "Usual spending a week (last 4 weeks, no rent or bills)")
    add("usual_daily", fc.usual_daily, "gbp", "Usual spending a day")
    if fc.spare is not None:
        add("spare", fc.spare, "gbp", "Spare by the next money at the usual pace")
    if fc.run_out_date:
        add_date("run_out", fc.run_out_date, "the day the money runs out at this pace")
    if fc.next_money is not None:
        nm = fc.next_money
        nsid = sid
        if nm.source.url and nm.source.url.startswith("https://"):
            nref = SourceRef(source="official", series_id=nm.source.url[:500], status="cached", note=nm.source.label)
            nsid = source_key(nref)
            sources.append(nref)
            links.append(ToolSourceLink(url=nm.source.url[:500]))
        add("next_money.amount", nm.amount, "gbp", f"Next money: {nm.label}", nsid)
        add_date("next_money", nm.date, "the next money arrives", nsid)
    for i, b in enumerate(fc.bills[:12]):
        add(f"bill.{i}.amount", b.amount, "gbp", f"Bill before the next money, due {b.due_date}")
    for i, a in enumerate(fc.accounts[:8]):
        add(f"account.{i}.balance", a.balance, "gbp", "Account balance" + (" (counted)" if a.counted else ""))
    for i, w in enumerate(fc.usual_weeks):
        add(f"usual_week.{i}", w.amount, "gbp", f"Spending in the week from {w.start}")
    if fc.suggestion is not None:
        add("suggestion.amount", fc.suggestion.amount, "gbp", "Amount in the suggestion")
        if fc.suggestion.rate_pct is not None:
            add("suggestion.rate_pct", fc.suggestion.rate_pct, "percent", "Bank of England easy-access savings rate")
    if fc.stress is not None:
        st = fc.stress
        add("stress.inflation_pct", st.inflation_pct, "percent", f"Inflation used for the {st.year} test (ONS CPI)")
        add("stress.per_week", st.per_week, "gbp", f"You can spend a week in the {st.year} test")
        add("stress.usual_weekly", st.usual_weekly, "gbp", f"Usual spending a week in the {st.year} test")
        add("stress.year", st.year, "date_year", "Year of the price test")
        if st.run_out_date:
            add_date("stress.run_out", st.run_out_date, f"run-out day in the {st.year} test")

    result: dict[str, Any] = {
        "question": fc.question,
        "status": fc.state,
        "today": fc.today,
        "headline": fc.headline,
        "budget_line": fc.budget_line,
        "habit_line": fc.habit_line,
        "next_money": None if fc.next_money is None else {"label": fc.next_money.label, "date": fc.next_money.date},
        "money_now": fc.money_now,
        "bills_total": fc.bills_total,
        "buffer_pct": fc.buffer_pct,
        "buffer_amount": fc.buffer_amount,
        "days": fc.days,
        **_budget(fc),
        "per_day": fc.per_day,
        "usual_weekly": fc.usual_weekly,
        "spare": fc.spare,
        "run_out_date": fc.run_out_date,
        "cpi_adjusted": fc.cpi_adjusted,
        "cpi_note": fc.cpi_note,
        "steps": [{"id": s.id, "title": s.title, "amount": s.amount, "text": s.text} for s in fc.steps],
        "suggestion": None if fc.suggestion is None else fc.suggestion.text,
        "stress": None if fc.stress is None else {"year": fc.stress.year, "status": fc.stress.state,
                                                   "text": fc.stress.text},
        "how": "per day = (money now - bills - buffer) / days; per week = per day x 7. The card rounds; "
               "the breakdown is exact.",
    }  # fmt: skip
    return ToolOutput(result=result, facts=facts, sources=sources, links=links, raw=fc)


def _budget(fc: Forecast) -> dict[str, Any]:
    if short_window(fc):
        return {"budget_period": "until_next_money", "to_spend": fc.to_spend,
                "say": f"Under 14 days to the next money: give the total until {until_text(fc)} (to_spend) and "
                       "per day, like the app card. Never give a weekly figure."}  # fmt: skip
    return {"budget_period": "week", "per_week": fc.per_week}


def _short(fc: Forecast) -> dict[str, Any]:
    return {"status": fc.state, "headline": fc.headline, "budget_line": fc.budget_line, **_budget(fc),
            "per_day": fc.per_day, "money_now": fc.money_now, "bills_total": fc.bills_total, "days": fc.days,
            "spare": fc.spare, "run_out_date": fc.run_out_date,
            "next_money": None if fc.next_money is None else {"label": fc.next_money.label,
                                                              "date": fc.next_money.date}}  # fmt: skip


def what_if_output(res: WhatIfResult) -> ToolOutput:
    """Before and after facts (`whatif.before.*`, `whatif.after.*`) and the change amounts and dates
    (`whatif.change.N.*`). All are the user's own numbers from the engine."""
    before = forecast_output(res.before, "whatif.before", "Before: ")
    after = forecast_output(res.after, "whatif.after", "After: ")
    sid = source_key(statement_ref(res.after))
    facts = [*before.facts, *after.facts]
    for i, ch in enumerate(res.changes[:5]):
        what = ch.label or ch.kind.replace("_", " ")
        if ch.amount is not None:
            facts.append(ChatFact(id=f"whatif.change.{i}.amount", value=round(ch.amount, 2), unit="gbp",
                                  label=f"What-if amount: {what}"[:120], source_id=sid))  # fmt: skip
        if ch.date:
            d = date.fromisoformat(ch.date[:10])
            facts.append(ChatFact(id=f"whatif.change.{i}.day", value=d.day, unit="count",
                                  label=f"What-if day of the month ({d.strftime('%B')}): {what}"[:120],
                                  source_id=sid))  # fmt: skip
    if short_window(res.after):
        diff = round(res.after.to_spend - res.before.to_spend, 2)
        facts.append(ChatFact(id="whatif.to_spend_change", value=diff, unit="gbp",
                              label=f"Change in what you can spend until {until_text(res.after)}",
                              source_id=sid))  # fmt: skip
    else:
        diff = round(res.after.per_week - res.before.per_week, 2)
        facts.append(ChatFact(id="whatif.per_week_change", value=diff, unit="gbp",
                              label="Change in what you can spend a week", source_id=sid))  # fmt: skip
    seen: set[str] = set()
    sources: list[SourceRef] = []
    links: list[ToolSourceLink | None] = []
    for out in (before, after):
        for i, ref in enumerate(out.sources):
            if source_key(ref) not in seen:
                seen.add(source_key(ref))
                sources.append(ref)
                links.append(out.links[i] if i < len(out.links) else None)
    result: dict[str, Any] = {
        "changes": [c.model_dump(exclude_none=True) for c in res.changes],
        "before": _short(res.before),
        "after": _short(res.after),
        "summary": res.summary,
    }
    return ToolOutput(result=result, facts=facts, sources=sources, links=links, raw=res)


def with_usual_pay(out: ToolOutput, pay: float | None) -> ToolOutput:
    """Adds the usual job pay per payment (`forecast.usual_pay`), so Penny can price "2 extra shifts"."""
    if pay is None or pay <= 0:
        return out
    sid = out.facts[0].source_id if out.facts else None
    fact = ChatFact(id="forecast.usual_pay", value=round(pay, 2), unit="gbp",
                    label="Usual pay from the job, per payment", source_id=sid)
    result = dict(out.result) if isinstance(out.result, dict) else {"result": out.result}
    result["usual_pay"] = round(pay, 2)
    return out.model_copy(update={"facts": [*out.facts, fact], "result": result})
