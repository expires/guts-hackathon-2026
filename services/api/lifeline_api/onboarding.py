"""Money data the user gives us (ADR 0029): manual entry, logged payments and health signals.

Manual entry becomes a FinanceSnapshot with `source="manual"` and `status="live"` (it is the user's own data).
Every synthesised transaction carries `provider_category="user_entered"` and says "(entered by you)" in its
description, so it is never mistaken for bank data. It feeds the same lifeline_engine.money pipeline.
"""

from __future__ import annotations

import secrets
from datetime import date, timedelta
from typing import Literal

from lifeline_api.errors import ApiError
from lifeline_contracts.account import FinanceInput, HealthSignal, LogPaymentRequest, ManualFinanceInput
from lifeline_contracts.finance import Account, AccountHolder, FinanceSnapshot, MortgageDetails, Transaction
from lifeline_engine.finance import monthly_payment

USER_ENTERED = "user_entered"
LOGGED_BY_APP = "app_intent"
MANUAL_HISTORY_MONTHS = 6
UNENTERED_CURRENT = "Current account (balance not entered)"
DEBT_ACCOUNTS: dict[str, tuple[Literal["current", "credit", "loan"], str]] = {
    "card": ("credit", "Credit card (entered by you)"),
    "overdraft": ("current", "Overdraft (entered by you)"),
    "bnpl": ("credit", "Buy now, pay later (entered by you)"),
    "loan": ("loan", "Loan (entered by you)"),
}
CURRENT_ACCOUNT_ID = "acc_current"


def _month_days(today: date, months: int, day: int) -> list[date]:
    """The `day` of each of the last `months` months, oldest first, never after `today`."""
    out: list[date] = []
    y, m = today.year, today.month
    for _ in range(months + 1):
        d = date(y, m, min(day, 28))
        if d <= today:
            out.append(d)
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return sorted(out)[-months:]


def _tx(d: date, amount: float, name: str, merchant: str, account: str = CURRENT_ACCOUNT_ID) -> Transaction:
    return Transaction(
        id=f"man_{d.isoformat()}_{secrets.token_hex(4)}",
        account_id=account,
        date=d.isoformat(),
        amount=round(amount, 2),
        description=f"{name} (entered by you)"[:200],
        merchant=merchant[:80],
        provider_category=USER_ENTERED,
    )


def _require(value: object, field: str) -> None:
    if value is None:
        raise ApiError(422, "validation_error", f"{field}: required when housing is mortgage")


def manual_snapshot(body: ManualFinanceInput, today: date) -> FinanceSnapshot:
    txs: list[Transaction] = []
    if body.monthly_take_home > 0:
        label = "Monthly income" if body.is_student else "Salary"
        for d in _month_days(today, MANUAL_HISTORY_MONTHS, 25):
            txs.append(_tx(d, body.monthly_take_home, label, label))
    if body.housing == "rent" and body.monthly_rent:
        for d in _month_days(today, MANUAL_HISTORY_MONTHS, 1):
            txs.append(_tx(d, -body.monthly_rent, "Rent", "Rent"))
    for i, cost in enumerate(body.regular_costs):
        if cost.monthly_amount <= 0:
            continue
        for d in _month_days(today, MANUAL_HISTORY_MONTHS, 2 + i % 26):
            txs.append(_tx(d, -cost.monthly_amount, cost.name, cost.name))

    # The balance of the current account is not asked for: it stays 0 and is never shown as a part (ADR 0053).
    accounts = [
        Account(id=CURRENT_ACCOUNT_ID, name=UNENTERED_CURRENT, kind="current", provider="manual", balance=0.0),
    ]
    if body.savings:
        accounts.append(Account(id="acc_savings", name="Savings (entered by you)", kind="savings", provider="manual",
                                balance=round(body.savings, 2)))

    mortgage: MortgageDetails | None = None
    if body.housing == "mortgage":
        _require(body.mortgage_balance, "mortgage_balance")
        _require(body.mortgage_rate_pct, "mortgage_rate_pct")
        _require(body.mortgage_years_left, "mortgage_years_left")
        _require(body.property_value, "property_value")
        assert body.mortgage_balance is not None and body.mortgage_rate_pct is not None
        assert body.mortgage_years_left is not None and body.property_value is not None
        payment = monthly_payment(body.mortgage_balance, body.mortgage_rate_pct, max(1, body.mortgage_years_left))
        mortgage = MortgageDetails(
            balance=body.mortgage_balance,
            rate_pct=body.mortgage_rate_pct,
            rate_type="fixed" if body.deal_end else "variable",
            fixed_until=body.deal_end,
            years_left=body.mortgage_years_left,
            property_value=body.property_value,
            monthly_payment=round(payment, 2),
        )
        accounts.append(Account(id="acc_mortgage", name="Mortgage (entered by you)", kind="mortgage",
                                provider="manual", balance=-round(body.mortgage_balance, 2)))
        for d in _month_days(today, MANUAL_HISTORY_MONTHS, 1):
            txs.append(_tx(d, -payment, "Mortgage payment", "Mortgage"))

    for debt in body.debts:
        if debt.balance <= 0:
            continue
        kind, name = DEBT_ACCOUNTS[debt.kind]
        accounts.append(Account(id=f"acc_debt_{debt.id}"[:40], name=name, kind=kind, provider="manual",
                                balance=-round(debt.balance, 2)))

    monthly_costs = sum(c.monthly_amount for c in body.regular_costs)
    if body.housing == "rent" and body.monthly_rent:
        monthly_costs += body.monthly_rent
    txs.sort(key=lambda t: (t.date, t.id))
    return FinanceSnapshot(
        status="live", source="manual", as_of=today.isoformat(), accounts=accounts, transactions=txs,
        mortgage=mortgage, housing=body.housing, is_student=body.is_student, age=body.age,
        student_loan_plan=body.student_loan_plan,
        income_sources=list(body.income_sources), debts=list(body.debts),
        monthly_costs=round(monthly_costs, 2) if (body.regular_costs or body.monthly_rent) else None,
    )


def with_holder(snap: FinanceSnapshot, body: ManualFinanceInput, place: dict[str, str] | None,
                name: str | None) -> FinanceSnapshot:
    """Attach who and where (the engine reads these for the profile). Place comes from the postcode lookup."""
    region = None if place is None else place.get("region")
    postcode = ((place or {}).get("postcode") or body.postcode.upper().strip())[:10]
    holder = None
    birth_year = body.birth_year
    if birth_year is None and body.age is not None:
        birth_year = date.fromisoformat(snap.as_of).year - body.age
    if birth_year is not None:
        holder = AccountHolder(name=(name or "You")[:40], birth_year=birth_year, region=region,
                               occupation="student" if body.is_student else None,
                               town=None if place is None else place.get("town"), postcode=postcode)
    return snap.model_copy(update={"region": region, "postcode": postcode, "holder": holder})


def logged_transaction(body: LogPaymentRequest, today: date) -> Transaction:
    d = date.fromisoformat(body.date) if body.date else today
    if d > today + timedelta(days=1):
        raise ApiError(422, "validation_error", "date: a payment cannot be in the future")
    return Transaction(
        id=f"log_{d.isoformat()}_{secrets.token_hex(4)}",
        account_id=CURRENT_ACCOUNT_ID,
        date=d.isoformat(),
        amount=-round(body.amount, 2),
        description=f"{body.merchant} (logged by you)"[:200],
        merchant=body.merchant,
        provider_category=body.category or LOGGED_BY_APP,
    )


def empty_snapshot(today: date) -> FinanceSnapshot:
    """Start of a user's own data when the first thing they give us is a logged payment."""
    return FinanceSnapshot(
        status="live", source="manual", as_of=today.isoformat(), transactions=[],
        accounts=[Account(id=CURRENT_ACCOUNT_ID, name="Current account (payments you logged)", kind="current",
                          provider="app", balance=0.0)],
    )


# ---------- health (ADR 0029) ----------

STEPS_TARGET = 8000
SLEEP_LOW, SLEEP_HIGH = 7.0, 9.0


def health_effect(signal: HealthSignal) -> int:
    """Points for the Life Health stat at the next AGE, bounded -10..10. Deterministic.

    Steps: +1 per 1,000 steps a day above 8,000, -1 per 1,000 below, capped at +-6.
    Sleep: +4 for 7 to 9 hours, 0 within 1 hour of that band, else -4.
    Fewer than 7 measured days halves the effect (rounded toward zero).
    """
    steps = max(-6, min(6, int((signal.steps_per_day - STEPS_TARGET) / 1000)))
    if SLEEP_LOW <= signal.sleep_hours <= SLEEP_HIGH:
        sleep = 4
    elif SLEEP_LOW - 1 <= signal.sleep_hours <= SLEEP_HIGH + 1:
        sleep = 0
    else:
        sleep = -4
    effect = steps + sleep
    if signal.measured_days < 7:
        effect = int(effect / 2)
    return max(-10, min(10, effect))


# ---------- merging the user's inputs into one snapshot ----------
#
# One FinanceSnapshot per user. Inputs merge like this:
# - Statement: its transactions and accounts replace earlier statement data and the transactions
#   synthesised from manual entry. Logged payments after the statement's last day stay. Mortgage,
#   energy, holder, region, postcode and manual savings/mortgage accounts from earlier input stay.
# - Manual entry: sets holder, region, postcode, mortgage and the savings/mortgage accounts. Its
#   synthesised transactions are used only when there is no statement data. Logged payments stay.
# - Logged payment: appended.

MANUAL_ACCOUNT_IDS = ("acc_savings", "acc_mortgage")


def _is_synthetic(t: Transaction) -> bool:
    return t.provider_category == USER_ENTERED


def _is_logged(t: Transaction) -> bool:
    return t.id.startswith("log_")


def _is_bank(t: Transaction) -> bool:
    return not _is_synthetic(t) and not _is_logged(t)


T212 = "trading212"


def investment_only(snap: FinanceSnapshot) -> bool:
    """Live data from Trading 212 alone: one investment account, no transactions."""
    return not snap.transactions and bool(snap.accounts) and all(a.provider == T212 for a in snap.accounts)


def without_trading212(snap: FinanceSnapshot) -> FinanceSnapshot:
    return snap.model_copy(update={"accounts": [a for a in snap.accounts if a.provider != T212], "holdings": []})


def merge_statement(prev: FinanceSnapshot | None, stmt: FinanceSnapshot) -> FinanceSnapshot:
    if prev is None:
        return stmt
    if investment_only(stmt) and prev.source in ("statement", "manual"):
        # Trading 212 on top of a statement or entered numbers: the user's own rows stay (bank rows would be
        # replaced by their own live rows, but Trading 212 has no transactions).
        return prev.model_copy(update={
            "accounts": [*(a for a in prev.accounts if a.provider != T212), *stmt.accounts],
            "holdings": stmt.holdings,
            "status": stmt.status if stmt.status == "cached" else prev.status,
        })
    if stmt.source == "statement" and not stmt.holdings:
        # a new statement keeps the Trading 212 account and positions already connected
        t212_accounts = [a for a in prev.accounts if a.provider == T212 and a.id not in {x.id for x in stmt.accounts}]
        if t212_accounts or prev.holdings:
            stmt = stmt.model_copy(update={"accounts": [*stmt.accounts, *t212_accounts], "holdings": prev.holdings})
    last = max((t.date for t in stmt.transactions), default=stmt.as_of)
    kept_logs = [t for t in prev.transactions if _is_logged(t) and t.date > last]
    ids = {a.id for a in stmt.accounts}
    kept_accounts = [a for a in prev.accounts if a.id in MANUAL_ACCOUNT_IDS and a.id not in ids]
    return stmt.model_copy(update={
        "transactions": sorted([*stmt.transactions, *kept_logs], key=lambda t: (t.date, t.id)),
        "accounts": [*stmt.accounts, *kept_accounts],
        "as_of": max(stmt.as_of, *(t.date for t in kept_logs)) if kept_logs else stmt.as_of,
        "mortgage": prev.mortgage, "energy": prev.energy,
        "holder": stmt.holder or prev.holder, "region": stmt.region or prev.region,
        "postcode": stmt.postcode or prev.postcode,
        **_kept_entered_fields(prev, stmt),
    })


ENTERED_FIELDS = ("age", "is_student", "housing", "student_loan_plan", "monthly_costs", "savings_rate_pct")
ENTERED_LISTS = ("income_sources", "debts")


def _kept_entered_fields(prev: FinanceSnapshot, new: FinanceSnapshot) -> dict[str, object]:
    """What the user entered stays when the statement leaves it empty, and entered income sources and debts of
    a kind the statement did not find are kept."""
    out: dict[str, object] = {}
    for name in ENTERED_FIELDS:
        if getattr(new, name) is None and getattr(prev, name) is not None:
            out[name] = getattr(prev, name)
    for name in ENTERED_LISTS:
        # Keep entered items of a kind the statement did not find (a loan instalment that has not arrived yet).
        found = list(getattr(new, name))
        kinds = {item.kind for item in found}
        kept = [item for item in getattr(prev, name) if item.kind not in kinds]
        if kept:
            out[name] = (found + kept)[:20]
    return out


def merge_manual(prev: FinanceSnapshot | None, manual: FinanceSnapshot) -> FinanceSnapshot:
    if prev is None:
        return manual
    bank = [t for t in prev.transactions if _is_bank(t)]
    logs = [t for t in prev.transactions if _is_logged(t)]
    if bank:
        # Real transactions win; manual entry adds who, where, the mortgage and savings.
        manual_accounts = [a for a in manual.accounts if a.id in MANUAL_ACCOUNT_IDS]
        prev_accounts = [a for a in prev.accounts if a.id not in MANUAL_ACCOUNT_IDS]
        return prev.model_copy(update={
            "transactions": sorted([*bank, *logs], key=lambda t: (t.date, t.id)),
            "accounts": [*prev_accounts, *manual_accounts],
            "mortgage": manual.mortgage, "holder": manual.holder or prev.holder,
            "region": manual.region or prev.region, "postcode": manual.postcode or prev.postcode,
            "as_of": max(prev.as_of, manual.as_of),
            # What the user just entered wins; a field left empty keeps what the statement found.
            **{f: getattr(manual, f) for f in (*ENTERED_FIELDS, *ENTERED_LISTS) if getattr(manual, f)},
        })
    return manual.model_copy(update={
        "transactions": sorted([*manual.transactions, *logs], key=lambda t: (t.date, t.id)),
        "energy": prev.energy,
    })


def inputs_of(snap: FinanceSnapshot | None) -> list[FinanceInput]:
    """How the user gave us this data, read from the stored snapshot itself (one source of truth for /v1/me)."""
    if snap is None:
        return []
    out: list[FinanceInput] = []
    if snap.source == "sample":
        out.append("sample")
    if snap.source == "statement":
        out.append("statement")
    if snap.source in ("truelayer", "bank") or any(p in snap.source for p in ("monzo", "trading212")):
        out.append("bank")
    if snap.source == "manual" and any(_is_synthetic(t) for t in snap.transactions) or any(
            a.provider == "manual" for a in snap.accounts):
        out.append("manual")
    if any(_is_logged(t) for t in snap.transactions):
        out.append("app_intent")
    return out


# ---------- what we know vs what we would be guessing (ADR 0053 bug 3) ----------


def payday_known(snap: FinanceSnapshot) -> bool:
    """True when an income date is known: an entered income source with dates, or real income credits
    (statement or bank). Synthesised manual-entry rows sit on a day we chose, so they do not count."""
    if any(src.next_date or src.dates for src in snap.income_sources):
        return True
    return any(t.amount > 0 and not _is_synthetic(t) and not _is_logged(t) for t in snap.transactions)


def synthetic_merchants(snap: FinanceSnapshot) -> set[str]:
    """Names of costs we spread over days we chose. Their due dates are not known."""
    return {(t.merchant or "").lower() for t in snap.transactions if _is_synthetic(t)}
