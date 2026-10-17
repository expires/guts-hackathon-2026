"""Student challenges (ADR 0052), scored on the user's own money data, not on a game life.

These challenges have scope "you": they are not tied to a game life, so their progress has no life_id.
Details carry no £ amounts.
"""

from __future__ import annotations

from datetime import date, timedelta

from lifeline_contracts.domain import Challenge
from lifeline_contracts.finance import FinanceSnapshot
from lifeline_engine.money.predict import daily_spend
from lifeline_engine.money.profile import liquid, savings_total

YOU = "you"


def challenges(today: date) -> list[Challenge]:
    year = today.year
    return [
        Challenge(
            id="last-the-term",
            title="Make your money last the term",
            emoji="🗓️",
            character_id=YOU,
            scope="you",
            start_year=year,
            description="Keep enough money to reach the day your next money arrives.",
            goal={"type": "money_lasts_until_next_income"},
        ),
        Challenge(
            id="safety-fund-1m",
            title="1 month safety fund",
            emoji="🛟",
            character_id=YOU,
            scope="you",
            start_year=year,
            description="Save one month of your regular costs.",
            goal={"type": "safety_fund_months", "months": 1.0},
        ),
        Challenge(
            id="clear-klarna",
            title="Clear Klarna",
            emoji="🧾",
            character_id=YOU,
            scope="you",
            start_year=year,
            description="Pay off every buy now, pay later plan.",
            goal={"type": "clear_bnpl"},
        ),
        Challenge(
            id="lisa-by-25",
            title="Lifetime ISA by 25",
            emoji="🏠",
            character_id=YOU,
            scope="you",
            start_year=year,
            description="Open a Lifetime ISA before you turn 25 and get the 25% bonus.",
            goal={"type": "lifetime_isa_by_age", "age": 25.0},
        ),
    ]


def _age(snap: FinanceSnapshot, today: date) -> int | None:
    if snap.age is not None:
        return snap.age
    if snap.holder is not None:
        return today.year - snap.holder.birth_year
    return None


def evaluate(challenge: Challenge, snap: FinanceSnapshot, today: date) -> tuple[str, str]:
    kind = str(challenge.goal.get("type"))
    if kind == "safety_fund_months":
        if not snap.monthly_costs:
            return "in_progress", "Add your monthly costs to see this."
        months = savings_total(snap) / snap.monthly_costs
        if months >= float(challenge.goal["months"]):
            return "won", "You have a month of costs saved."
        return "in_progress", f"{int(months * 100)}% of a month saved."
    if kind == "clear_bnpl":
        plans = [d for d in snap.debts if d.kind == "bnpl" and d.balance > 0]
        if not plans:
            return "won", "No buy now, pay later plans left."
        return "in_progress", f"{len(plans)} plan{'s' if len(plans) > 1 else ''} left to clear."
    if kind == "lifetime_isa_by_age":
        age, limit = _age(snap, today), int(float(challenge.goal["age"]))
        has_lisa = any(a.kind == "isa" and "lifetime" in a.name.lower() for a in snap.accounts)
        if has_lisa and (age is None or age <= limit):
            return "won", "You have a Lifetime ISA."
        if age is not None and age > limit:
            return "lost", f"A Lifetime ISA must be opened before {limit}."
        if age is None:
            return "in_progress", "Open one before you turn 25."
        return "in_progress", f"{limit - age} years left to open one."
    if kind == "money_lasts_until_next_income":
        now = today.isoformat()
        upcoming = sorted(d for s in snap.income_sources for d in [s.next_date, *s.dates] if d and d >= now)
        if not upcoming:
            return "in_progress", "Add when your next money arrives to see this."
        days_left = (date.fromisoformat(upcoming[0]) - today).days
        spend = daily_spend(snap.transactions, today - timedelta(days=30), today - timedelta(days=1))
        per_day = sum(spend.values()) / max(1, len(spend))
        if per_day <= 0:
            return "won", f"Next money in {days_left} days."
        lasts = int(max(0.0, liquid(snap)) / per_day)
        if lasts >= days_left:
            return "won", f"Your money lasts {lasts} days; next money in {days_left} days."
        return "in_progress", f"Your money lasts {lasts} days; next money in {days_left} days."
    return "in_progress", "This goal is not scored yet."
