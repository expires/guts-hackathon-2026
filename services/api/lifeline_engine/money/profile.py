"""Overview series, the DecisionProfile + CharacterSpec bridge, and personal facts (ADR 0016). Pure.

Assumptions (labelled, used when the snapshot has no value):
- `FinanceSnapshot` has no age, region or name. `ProfileHints` carries them. Without hints the
  region comes from the town in the fixture persona id (e.g. 'homeowner-leeds'), else DEFAULT_REGION,
  and the age is DEFAULT_AGE.
- Gross pay is solved from net salary credits with 2026/27 UK income tax and employee National
  Insurance (England bands). Pension and student loan deductions are ignored.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from lifeline_contracts.domain import CharacterSpec, DecisionProfile, Housing
from lifeline_contracts.finance import (
    Account,
    FinanceSnapshot,
    PersonalFact,
    Point,
    Transaction,
)
from lifeline_engine.money import dates
from lifeline_engine.money.categorise import categorise
from lifeline_engine.money.categorise import label as category_label
from lifeline_engine.money.recurring import detect_recurring, detect_salary, detect_subscriptions
from lifeline_engine.money.spending import by_category, monthly_totals
from lifeline_engine.money.text import clean_name, gbp, money_value

DEFAULT_AGE = 35
DEFAULT_REGION = "north-west"
LIQUID_KINDS = ("current", "savings", "isa")
SAVINGS_KINDS = ("savings", "isa")
DEBT_KINDS = ("credit", "loan")
HISTORY_WEEKS = 52
EMERGENCY_MONTHS = 3
MIN_KNOWN_COSTS = 50.0  # GBP a month; below this, costs are not entered (ADR 0053 bug 5)

TOWN_REGION: dict[str, tuple[str, str]] = {
    "leeds": ("yorkshire-and-the-humber", "Leeds"),
    "sheffield": ("yorkshire-and-the-humber", "Sheffield"),
    "york": ("yorkshire-and-the-humber", "York"),
    "london": ("london", "London"),
    "manchester": ("north-west", "Manchester"),
    "liverpool": ("north-west", "Liverpool"),
    "bolton": ("north-west", "Bolton"),
    "coventry": ("west-midlands", "Coventry"),
    "exeter": ("south-west", "Exeter"),
    "bristol": ("south-west", "Bristol"),
    "plymouth": ("south-west", "Plymouth"),
    "birmingham": ("west-midlands", "Birmingham"),
    "nottingham": ("east-midlands", "Nottingham"),
    "leicester": ("east-midlands", "Leicester"),
    "newcastle": ("north-east", "Newcastle"),
    "cambridge": ("east-of-england", "Cambridge"),
    "norwich": ("east-of-england", "Norwich"),
    "brighton": ("south-east", "Brighton"),
    "reading": ("south-east", "Reading"),
    "cardiff": ("wales", "Cardiff"),
    "edinburgh": ("scotland", "Edinburgh"),
    "glasgow": ("scotland", "Glasgow"),
    "belfast": ("northern-ireland", "Belfast"),
}


@dataclass(frozen=True)
class ProfileHints:
    """Facts about the account holder that bank data does not carry."""

    name: str = "You"
    age: int | None = None
    region: str | None = None
    town: str | None = None
    postcode: str | None = None
    occupation: str = "office worker"


def hints_from_snapshot(snapshot: FinanceSnapshot, today: dates.date) -> ProfileHints:
    """Holder details from the snapshot (ADR 0023), else the snapshot's region and postcode, else defaults."""
    holder = snapshot.holder
    if holder is None:
        return ProfileHints(region=snapshot.region, postcode=snapshot.postcode)
    return ProfileHints(
        name=holder.name or "You",
        age=today.year - holder.birth_year,
        region=holder.region or snapshot.region,
        town=holder.town,
        postcode=holder.postcode or snapshot.postcode,
        occupation=holder.occupation or ProfileHints.occupation,
    )


# ---------- balances ----------


def _sum(accounts: Sequence[Account], kinds: Sequence[str]) -> float:
    return round(sum(a.balance for a in accounts if a.kind in kinds), 2)


def is_cash(account: Account) -> bool:
    """Current accounts and cash savings (savings accounts, cash ISAs). Not stocks and shares ISAs (ADR 0033)."""
    return account.kind == "current" or is_cash_savings(account)


def liquid(snapshot: FinanceSnapshot) -> float:
    """Cash: current accounts plus cash savings. A stocks and shares ISA is an investment, not cash."""
    return round(sum(a.balance for a in snapshot.accounts if is_cash(a)), 2)


def is_cash_savings(account: Account) -> bool:
    """Savings accounts and cash ISAs. A stocks and shares ISA is an investment, not cash."""
    if account.kind == "savings":
        return True
    if account.kind != "isa":
        return False
    name = account.name.lower()
    return not any(w in name for w in ("stocks", "shares", "invest", "s&s"))


def savings_total(snapshot: FinanceSnapshot) -> float:
    """Cash savings: savings accounts and cash ISAs."""
    return max(0.0, round(sum(a.balance for a in snapshot.accounts if is_cash_savings(a)), 2))


def debt_total(snapshot: FinanceSnapshot) -> float:
    """Money owed on cards and loans (positive)."""
    return round(-sum(min(0.0, a.balance) for a in snapshot.accounts if a.kind in DEBT_KINDS), 2)


def _has_mortgage_account(snapshot: FinanceSnapshot) -> bool:
    return any(a.kind == "mortgage" for a in snapshot.accounts)


def balance(snapshot: FinanceSnapshot) -> float:
    """Cash: current accounts, savings accounts and cash ISAs."""
    return liquid(snapshot)


def net_worth(snapshot: FinanceSnapshot) -> float:
    """All account balances, plus the property value, minus the mortgage when no mortgage account holds it."""
    total = sum(a.balance for a in snapshot.accounts)
    m = snapshot.mortgage
    if m is not None:
        total += m.property_value
        if not _has_mortgage_account(snapshot):
            total -= m.balance
    return round(total, 2)


def _history(snapshot: FinanceSnapshot, cash_only: bool) -> list[Point]:
    """Weekly balances going back from as_of. Balance at the end of day d = today's balance minus every
    transaction after d. Property value is held constant (no history in the data)."""
    as_of = dates.parse(snapshot.as_of)
    accounts = [a for a in snapshot.accounts if not cash_only or is_cash(a)]
    ids = {a.id for a in accounts}
    current = sum(a.balance for a in accounts)
    if not cash_only and snapshot.mortgage is not None:
        current += snapshot.mortgage.property_value
        if not _has_mortgage_account(snapshot):
            current -= snapshot.mortgage.balance
    txs = sorted((t for t in snapshot.transactions if t.account_id in ids), key=lambda t: t.date, reverse=True)
    earliest = min((dates.parse(t.date) for t in txs), default=as_of)
    points: list[Point] = []
    running = current
    i = 0
    for w in range(HISTORY_WEEKS + 1):
        d = dates.add_days(as_of, -7 * w)
        while i < len(txs) and dates.parse(txs[i].date) > d:
            running -= txs[i].amount
            i += 1
        points.append(Point(date=dates.iso(d), value=round(running, 2)))
        if d <= earliest:
            break
    points.reverse()
    return points


def balance_history(snapshot: FinanceSnapshot) -> list[Point]:
    return _history(snapshot, True)


def net_worth_history(snapshot: FinanceSnapshot) -> list[Point]:
    return _history(snapshot, False)


# ---------- spending averages ----------


def full_months_before(today: dates.date, n: int) -> list[str]:
    """The n complete months before today's month, oldest first."""
    cur = dates.month_of(today)
    return [dates.prev_month(cur, k) for k in range(n, 0, -1)]


def full_data_months(s: FinanceSnapshot, months: Sequence[str]) -> list[str]:
    """Months fully covered by the data: after the first transaction's month, or that month when the first
    transaction is on day 1 to 3. A statement that starts on 17 July does not count July (a part month makes
    usual spending look low). One rule for every monthly figure (months of cover, budgets, habits)."""
    if not s.transactions:
        return []
    first = min(t.date for t in s.transactions)
    start_month = first[:7] if int(first[8:10]) <= 3 else None
    return [m for m in months if m > first[:7] or m == start_month]


def monthly_spend(snapshot: FinanceSnapshot, today: dates.date, months: int = 3) -> float:
    """Average spending over the last `months` complete months that the data covers in full (full_data_months)
    and that have transactions."""
    ms = [m for m in full_data_months(snapshot, full_months_before(today, months))
          if any(t.date[:7] == m for t in snapshot.transactions)]
    if not ms:
        return 0.0
    totals = monthly_totals(snapshot.transactions, ms)
    return round(sum(totals.values()) / len(ms), 2)


def known_monthly_costs(snapshot: FinanceSnapshot, today: dates.date) -> float | None:
    """Monthly costs when known (ADR 0057): MEASURED average spending over the last 3 complete months with data,
    when it is at least MIN_KNOWN_COSTS. Else the entered `monthly_costs` (regular costs, ADR 0049) when above 0.
    None otherwise, so months of cover is never computed from missing costs (ADR 0053 bug 5)."""
    spend = monthly_spend(snapshot, today)
    if spend >= MIN_KNOWN_COSTS:
        return spend
    if snapshot.monthly_costs is not None and snapshot.monthly_costs > 0:
        return snapshot.monthly_costs
    return None


def costs_word(snapshot: FinanceSnapshot, today: dates.date) -> str:
    """What known_monthly_costs measures, for the text: 'spending' (measured) or 'regular costs' (entered)."""
    return "spending" if monthly_spend(snapshot, today) >= MIN_KNOWN_COSTS else "regular costs"


def months_of_cover(snapshot: FinanceSnapshot, today: dates.date) -> float | None:
    """Cash / known monthly costs, 1 decimal. None when costs are not known."""
    costs = known_monthly_costs(snapshot, today)
    return None if costs is None else round(max(0.0, liquid(snapshot)) / costs, 1)


def monthly_rent(txs: Sequence[Transaction], today: dates.date) -> float | None:
    rents = [r for r in detect_recurring(txs, today) if r.kind == "rent"]
    return round(sum(r.monthly_cost for r in rents), 2) if rents else None


# ---------- gross pay ----------


def _tax_and_ni(gross: float) -> float:
    pa = 12_570.0
    if gross > 100_000:
        pa = max(0.0, pa - (gross - 100_000) / 2)
    taxable = max(0.0, gross - pa)
    basic = min(taxable, 37_700.0)
    higher = min(max(0.0, taxable - 37_700.0), 125_140.0 - 37_700.0)
    additional = max(0.0, taxable - (125_140.0 - 37_700.0)) if gross > 125_140 else 0.0
    tax = 0.2 * basic + 0.4 * higher + 0.45 * additional
    ni = 0.08 * max(0.0, min(gross, 50_270.0) - 12_570.0) + 0.02 * max(0.0, gross - 50_270.0)
    return tax + ni


def gross_from_net(annual_net: float) -> float:
    """Gross annual pay whose take-home is `annual_net` (bisection, to the nearest pound)."""
    if annual_net <= 0:
        return 0.0
    lo, hi = annual_net, annual_net * 3 + 50_000
    for _ in range(80):
        mid = (lo + hi) / 2
        if mid - _tax_and_ni(mid) < annual_net:
            lo = mid
        else:
            hi = mid
    return float(round((lo + hi) / 2))


def annual_income(snapshot: FinanceSnapshot) -> float:
    inc = detect_salary(snapshot.transactions)
    return gross_from_net(inc.monthly_net * 12) if inc is not None else 0.0


# ---------- profile ----------


def _place(snapshot: FinanceSnapshot, hints: ProfileHints) -> tuple[str, str]:
    if hints.region:
        return hints.region, hints.town or hints.region.replace("-", " ").title()
    persona = (snapshot.persona or "").lower()
    for town, (region, name) in TOWN_REGION.items():
        if persona.endswith(town) or f"-{town}" in persona:
            return region, hints.town or name
    return DEFAULT_REGION, hints.town or "Manchester"


def housing(snapshot: FinanceSnapshot, today: dates.date) -> Housing:
    m = snapshot.mortgage
    if (m is not None and m.balance > 0) or any(a.kind == "mortgage" and a.balance < 0 for a in snapshot.accounts):
        return "mortgage"
    if m is not None and m.property_value > 0:
        return "own"
    return "rent"


def profile(
    snapshot: FinanceSnapshot, today: dates.date, hints: ProfileHints | None = None
) -> tuple[DecisionProfile, CharacterSpec]:
    """DecisionProfile and CharacterSpec from the snapshot. Both carry the same numbers."""
    h = hints or hints_from_snapshot(snapshot, today)
    age = max(16, min(100, h.age if h.age is not None else DEFAULT_AGE))
    region, town = _place(snapshot, h)
    income = min(10_000_000.0, annual_income(snapshot))
    savings = min(100_000_000.0, savings_total(snapshot))
    debt = min(100_000_000.0, debt_total(snapshot))
    tenure = housing(snapshot, today)
    m = snapshot.mortgage
    mortgage_balance = m.balance if m is not None else 0.0
    if m is None:
        mortgage_balance = -sum(min(0.0, a.balance) for a in snapshot.accounts if a.kind == "mortgage")
    property_value = m.property_value if m is not None else 0.0
    deal_months: int | None = None
    if m is not None and m.fixed_until is not None:
        days = (dates.parse(m.fixed_until) - today).days
        deal_months = max(0, min(120, -(-days // 30))) if days > 0 else 0
    prof = DecisionProfile(
        age=age,
        region=region,
        postcode=h.postcode,
        annual_income=income,
        savings=savings,
        other_debt=debt,
        housing=tenure,
        monthly_rent=monthly_rent(snapshot.transactions, today) if tenure == "rent" else None,
        property_value=property_value or None,
        mortgage_balance=mortgage_balance or None,
        mortgage_years_left=m.years_left if m is not None else None,
        deal_ends_in_months=deal_months,
    )
    char = CharacterSpec(
        id=f"self-{snapshot.persona}" if snapshot.persona else "self",
        name=h.name,
        emoji="🙂",
        occupation=h.occupation,
        region=region,
        town=town,
        postcode=h.postcode,
        birth_year=max(1930, min(2026, today.year - age)),
        annual_income=income,
        savings=savings,
        debt=debt,
        housing=tenure,
        property_value=property_value,
        mortgage_balance=mortgage_balance,
        blurb="Built from your bank data." if snapshot.status != "mock" else "Built from sample bank data.",
    )
    return prof, char


# ---------- personal facts ----------


PERSONAL_FACTS_SHOWN = 3  # "3 things Penny noticed" (ADR 0069)
# Rent and bills are not an everyday habit; money moved, cash and uncategorised rows are not a named habit.
NOT_HABIT_CATEGORIES = ("housing", "bills", "other", "transfers", "savings", "cash", "fees", "income")


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def personal_facts(snapshot: FinanceSnapshot) -> list[PersonalFact]:
    """Sentences with the user's real numbers. Every number in `text` is a value in `facts`.
    Concept ids exist in lifeline_sim concepts. Reference day is the snapshot's as_of.
    The main facts come first; extra facts (biggest spending, next money in, buy now pay later) fill the list up
    to PERSONAL_FACTS_SHOWN when the data allows (ADR 0069)."""
    today = dates.parse(snapshot.as_of)
    out: list[PersonalFact] = []
    subs = detect_subscriptions(snapshot.transactions, today)
    if subs:
        total = sum(s.monthly_cost for s in subs)
        out.append(
            PersonalFact(
                id="subscriptions_total",
                concept_id="budgeting",
                text=f"You spend {gbp(total)} a month on {_plural(len(subs), 'subscription')}.",
                facts={"monthly_total": money_value(total), "count": float(len(subs))},
            )
        )
    risen = [s for s in subs if s.price_rise is not None]
    if risen:
        s = max(risen, key=lambda x: x.monthly_cost)
        assert s.price_rise is not None
        per = {"weekly": "a week", "monthly": "a month", "quarterly": "a quarter", "yearly": "a year"}[s.cadence]
        out.append(
            PersonalFact(
                id=f"price_rise_{s.id}",
                concept_id="inflation",
                text=f"{clean_name(s.merchant)} went up from {gbp(s.price_rise.from_amount, True)} "
                f"to {gbp(s.price_rise.to_amount, True)} {per}.",
                facts={
                    "from_amount": money_value(s.price_rise.from_amount, True),
                    "to_amount": money_value(s.price_rise.to_amount, True),
                },
            )
        )
    spend = known_monthly_costs(snapshot, today)
    cash = liquid(snapshot)
    if spend is not None:
        months = round(max(0.0, cash) / spend, 1)
        # Signed cash: an overdrawn account is negative cash and covers 0 months, never "+£371 liquid".
        signed = {"months": months, "liquid": float(round(cash)), "monthly_spend": money_value(spend)}
        if cash < 0:
            text = (f"You are {gbp(cash)} in your overdraft, so your cash covers 0 months of "
                    f"{costs_word(snapshot, today)}.")
            signed["months"] = 0.0
        else:
            text = f"Your cash and savings cover {months:g} months of {costs_word(snapshot, today)}."
        out.append(PersonalFact(id="emergency_months", concept_id="emergency-fund", text=text, facts=signed))
    debt = debt_total(snapshot)
    if debt > 0:
        out.append(
            PersonalFact(
                id="debt_total",
                concept_id="debt",
                text=f"You owe {gbp(debt)} on cards and loans.",
                facts={"debt": money_value(debt)},
            )
        )
    m = snapshot.mortgage
    if m is not None and m.balance > 0:
        if m.fixed_until is not None and (dates.parse(m.fixed_until) - today).days >= 0:
            days = (dates.parse(m.fixed_until) - today).days
            text = f"Your mortgage rate is {m.rate_pct:.2f}% and your fixed deal ends in {days} days."
            facts = {"rate_pct": round(m.rate_pct, 2), "days_left": float(days)}
        else:
            text = f"You pay {m.rate_pct:.2f}% on a {gbp(m.balance)} mortgage."
            facts = {"rate_pct": round(m.rate_pct, 2), "balance": money_value(m.balance)}
        out.append(PersonalFact(id="mortgage_rate", concept_id="interest-rates", text=text, facts=facts))
    interest = interest_earned(snapshot, today)
    sav = savings_total(snapshot)
    if sav > 0 and interest > 0:  # ADR 0053 bug 6: only with a known (measured) rate
        out.append(
            PersonalFact(
                id="savings_interest",
                concept_id="compound-interest",
                text=f"Your savings of {gbp(sav)} earned {gbp(interest)} in interest in the last year.",
                facts={"savings": money_value(sav), "interest": money_value(interest)},
            )
        )
    for extra in (_top_category_fact, _next_money_fact, _bnpl_fact):
        if len(out) >= PERSONAL_FACTS_SHOWN:
            break
        fact = extra(snapshot, today, debt)
        if fact is not None:
            out.append(fact)
    return out


def _top_category_fact(snapshot: FinanceSnapshot, today: dates.date, _debt: float) -> PersonalFact | None:
    """Biggest everyday spending category in the last full month of data. Rent and bills are left out."""
    months = full_data_months(snapshot, full_months_before(today, 1))
    if not months:
        return None
    month = months[-1]
    spend = {c: v for c, (v, _) in by_category(snapshot.transactions, month).items()
             if c not in NOT_HABIT_CATEGORIES and v > 0}
    if not spend:
        return None
    top = max(spend, key=lambda c: (spend[c], c))
    name = category_label(top).lower()
    return PersonalFact(
        id=f"top_category_{top}",
        concept_id="budgeting",
        text=f"Not counting rent and bills, you spent the most on {name} last month: {gbp(spend[top])}.",
        facts={"amount": money_value(spend[top])},
    )


def _next_money_fact(snapshot: FinanceSnapshot, today: dates.date, _debt: float) -> PersonalFact | None:
    """The next payment in from the income sources (statement dates and known schedules)."""
    upcoming = [(dates.parse(s.next_date), s) for s in snapshot.income_sources
                if s.next_date is not None and dates.parse(s.next_date) > today and s.amount > 0]
    if not upcoming:
        return None
    day, src = min(upcoming, key=lambda x: (x[0], -x[1].amount))
    days = (day - today).days
    return PersonalFact(
        id=f"next_money_{src.id}",
        concept_id="budgeting",
        text=f"Your next money in is {gbp(src.amount)} in {_plural(days, 'day')}.",
        facts={"amount": money_value(src.amount), "days_left": float(days)},
    )


def _bnpl_fact(snapshot: FinanceSnapshot, _today: dates.date, debt: float) -> PersonalFact | None:
    """Buy now, pay later still owed, when no card or loan account already shows it."""
    owed = round(sum(d.balance for d in snapshot.debts if d.kind == "bnpl"), 2)
    if owed <= 0 or debt > 0:
        return None
    return PersonalFact(
        id="bnpl_owed",
        concept_id="debt",
        text=f"You still owe {gbp(owed)} on buy now, pay later plans.",
        facts={"owed": money_value(owed)},
    )


def interest_earned(snapshot: FinanceSnapshot, today: dates.date) -> float:
    """Interest credited to savings accounts in the 365 days before `today`."""
    ids = {a.id for a in snapshot.accounts if is_cash_savings(a)}
    start = dates.add_days(today, -365)
    total = 0.0
    for t in snapshot.transactions:
        if (
            t.account_id in ids
            and t.amount > 0
            and "interest" in t.description.lower()
            and start < dates.parse(t.date) <= today
        ):
            total += t.amount
    return round(total, 2)


def savings_rate_pct(snapshot: FinanceSnapshot, today: dates.date) -> float | None:
    """Rate the user's savings earn: the entered `savings_rate_pct` (ADR 0049), else interest credits over the last
    year / savings. None when neither is known (ADR 0053 bug 6)."""
    if snapshot.savings_rate_pct is not None:
        return snapshot.savings_rate_pct
    sav = savings_total(snapshot)
    earned = interest_earned(snapshot, today)
    if sav <= 0 or earned <= 0:
        return None
    return round(earned / sav * 100, 2)


def category_months(snapshot: FinanceSnapshot, months: Sequence[str]) -> dict[str, dict[str, float]]:
    """Spending per category for each month: {month: {category: amount}}."""
    return {m: {c: v for c, (v, _) in by_category(snapshot.transactions, m).items()} for m in months}


__all__ = [
    "ProfileHints",
    "annual_income",
    "balance",
    "balance_history",
    "categorise",
    "category_months",
    "debt_total",
    "gross_from_net",
    "interest_earned",
    "costs_word",
    "full_data_months",
    "known_monthly_costs",
    "liquid",
    "monthly_spend",
    "months_of_cover",
    "net_worth",
    "net_worth_history",
    "personal_facts",
    "profile",
    "savings_rate_pct",
    "savings_total",
]
