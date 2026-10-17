"""Turn a fixture `Persona` into a `FinanceSnapshot` with 12 months of realistic UK transactions.

Deterministic: the same persona and `as_of` always give the same snapshot (seeded RNG, no clock).

Daily discretionary spend responds to the same features as the ADR 0017 model, so the prediction has
signal to find: weekday, payday cycle, bank holidays (recorded gov.uk data), weather (the labelled
mock weather for the persona's region), a slow monthly trend, December and January.
"""

from __future__ import annotations

import calendar
import hashlib
import math
import random
from dataclasses import dataclass
from datetime import date, timedelta

from lifeline_contracts.finance import Account, FinanceSnapshot, Transaction
from lifeline_data.finance.personas import Persona, Shop
from lifeline_data.prediction_inputs import fixture_holidays_for, is_working_day, mock_weather_day

FIXTURE_AS_OF = date(2026, 10, 17)
HISTORY_DAYS = 365

WEEKDAY_MULT = (0.82, 0.85, 0.9, 1.0, 1.4, 1.55, 1.1)  # Monday..Sunday
PAYDAY_MULT = 1.35  # first 3 days after payday
LEAN_MULT = 0.85  # last 5 days before payday
BANK_HOLIDAY_MULT = 1.4
RAIN_MM = 5.0
RAIN_MULT = 0.9
WARM_C = 21.0
WARM_MULT = 1.12


@dataclass
class _Tx:
    day: date
    account: str
    amount: float
    description: str
    merchant: str | None
    kind: str


def _rng(*parts: object) -> random.Random:
    seed = int.from_bytes(hashlib.sha256("|".join(map(str, parts)).encode()).digest()[:8], "big")
    return random.Random(seed)  # noqa: S311 - simulation, not crypto


def _poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def _months(start: date, end: date) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _clamp_day(y: int, m: int, day: int) -> date:
    return date(y, m, min(max(day, 1), calendar.monthrange(y, m)[1]))


def _next_working(day: date, holidays: set[date]) -> date:
    while not is_working_day(day, holidays):
        day += timedelta(days=1)
    return day


def _payday(y: int, m: int, holidays: set[date]) -> date:
    """Last working day of the month."""
    day = _clamp_day(y, m, 31)
    while not is_working_day(day, holidays):
        day -= timedelta(days=1)
    return day


def _sub_amount(base: float, rise: tuple[date, float] | None, day: date) -> float:
    if rise is not None and day >= rise[0]:
        return rise[1]
    return base


def _pick(rng: random.Random, shops: list[tuple[Shop, float]]) -> Shop:
    total = sum(w for _, w in shops)
    x = rng.random() * total
    for shop, w in shops:
        x -= w
        if x <= 0:
            return shop
    return shops[-1][0]


def _ticket(rng: random.Random, shop: Shop) -> float:
    # Lognormal with mean `shop.mean`.
    sigma = shop.spread
    mu = math.log(shop.mean) - sigma * sigma / 2
    return max(0.5, round(math.exp(rng.gauss(mu, sigma)), 2))


def build_snapshot(p: Persona, as_of: date = FIXTURE_AS_OF) -> FinanceSnapshot:
    rng = _rng("finance", p.id, as_of.isoformat())
    start = as_of - timedelta(days=HISTORY_DAYS - 1)
    holidays = fixture_holidays_for(p.region)
    txs: list[_Tx] = []

    def add(day: date, account: str, amount: float, desc: str, merchant: str | None, kind: str) -> None:
        if start <= day <= as_of and amount != 0:
            txs.append(_Tx(day, account, round(amount, 2), desc, merchant, kind))

    months = _months(start - timedelta(days=31), as_of)
    paydays = [_payday(y, m, holidays) for y, m in months]

    for (y, m), payday in zip(months, paydays, strict=True):
        # Pay rise of 3% from April 2026.
        pay = p.net_pay if payday >= date(2026, 4, 1) else round(p.net_pay / 1.03, 2)
        add(payday, "acc_current", pay, f"{p.employer} SALARY", p.employer.title(), "CREDIT")

        if p.mortgage is not None:
            assert p.mortgage.lender is not None
            day = _next_working(_clamp_day(y, m, p.mortgage_day), holidays)
            add(day, "acc_current", -p.mortgage.monthly_payment, f"{p.mortgage.lender.upper()} MORTGAGE",
                p.mortgage.lender, "DIRECT_DEBIT")
        if p.rent is not None and p.landlord is not None:
            add(_clamp_day(y, m, p.rent_day), "acc_current", -p.rent, f"{p.landlord} RENT", p.landlord.title(),
                "STANDING_ORDER")

        energy_day = _next_working(_clamp_day(y, m, 6), holidays)
        add(energy_day, "acc_current", -p.energy.monthly_cost, p.energy.supplier.upper(), p.energy.supplier,
            "DIRECT_DEBIT")

        for bill in p.bills:
            if bill.months is not None and m not in bill.months:
                continue
            day = _clamp_day(y, m, bill.day)
            if bill.kind == "DIRECT_DEBIT":
                day = _next_working(day, holidays)
            add(day, "acc_current", -bill.amount, bill.description, bill.merchant, bill.kind)

        for sub in p.subs:
            if sub.cadence == "yearly" and sub.month != m:
                continue
            day = _clamp_day(y, m, sub.day)
            if sub.starts is not None and day < sub.starts:
                continue
            account = "acc_card" if sub.card and p.card is not None else "acc_current"
            add(day, account, -_sub_amount(sub.amount, sub.rise, day), sub.description, sub.merchant, "PURCHASE")

        if p.savings_transfer > 0:
            day = payday + timedelta(days=1)
            add(day, "acc_current", -p.savings_transfer, f"TO {p.savings_name.upper()}", None, "TRANSFER")
            add(day, "acc_savings", p.savings_transfer, "FROM CURRENT ACCOUNT", None, "TRANSFER")
        interest = round(p.savings_balance * p.savings_rate_pct / 100 / 12, 2)
        add(_clamp_day(y, m, 1), "acc_savings", interest, "INTEREST PAID", None, "INTEREST")

        if p.card is not None:
            c = p.card
            charge = abs(c.balance) * c.apr_pct / 100 / 12 * rng.uniform(0.96, 1.04)
            add(_clamp_day(y, m, 3), "acc_card", -charge, "INTEREST CHARGED", None, "INTEREST")
            day = _next_working(_clamp_day(y, m, c.payment_day), holidays)
            add(day, "acc_current", -c.payment, f"{c.provider.upper()} PAYMENT", c.provider, "DIRECT_DEBIT")
            add(day, "acc_card", c.payment, "PAYMENT RECEIVED - THANK YOU", None, "CREDIT")

        if p.overdraft_fee > 0:
            add(_clamp_day(y, m, 28), "acc_current", -p.overdraft_fee, "ARRANGED OVERDRAFT FEE", p.bank, "FEE")

    # Discretionary spend, one day at a time.
    month_mood: dict[tuple[int, int], float] = {}
    mood = 1.0
    for ym in months:
        mood = min(1.3, max(0.75, mood * math.exp(rng.gauss(0, 0.08))))
        month_mood[ym] = mood
    pay_set = sorted(paydays)
    day = start
    while day <= as_of:
        last_pay = max((d for d in pay_set if d <= day), default=None)
        next_pay = min((d for d in pay_set if d > day), default=None)
        weather = mock_weather_day(p.region, day)
        rainy = weather["rain_mm"] >= RAIN_MM
        warm = weather["temp_max_c"] >= WARM_C

        mult = WEEKDAY_MULT[day.weekday()] * month_mood[(day.year, day.month)]
        if last_pay is not None and (day - last_pay).days < 3:
            mult *= PAYDAY_MULT
        elif next_pay is not None and (next_pay - day).days <= 5:
            mult *= LEAN_MULT
        if day in holidays:
            mult *= BANK_HOLIDAY_MULT
        if rainy:
            mult *= RAIN_MULT
        if warm:
            mult *= WARM_MULT
        if day.month == 12 and day.day <= 24:
            mult *= 1.3
        elif day.month == 1:
            mult *= 0.85

        weighted = [
            (s, s.weight * (s.rainy if rainy else 1.0) * (s.warm if warm else 1.0)) for s in p.shops
        ]
        total_w = sum(w for _, w in weighted)
        avg_ticket = sum(s.mean * w for s, w in weighted) / total_w
        for _ in range(_poisson(rng, p.daily_spend * mult / avg_ticket)):
            shop = _pick(rng, weighted)
            amount = _ticket(rng, shop)
            if shop.merchant == "Cash":
                amount = float(rng.choice((10, 20, 20, 30, 40, 50)))
                add(day, "acc_current", -amount, "CASH WITHDRAWAL LINK ATM", None, "ATM")
                continue
            on_card = p.card is not None and rng.random() < p.card.purchase_share
            add(day, "acc_card" if on_card else "acc_current", -amount, shop.description, shop.merchant, "PURCHASE")
        day += timedelta(days=1)

    txs.sort(key=lambda t: (t.day, t.account, t.description, t.amount))
    transactions = [
        Transaction(
            id=f"tx_{p.id.split('-')[0][:4]}_{i:05d}",
            account_id=t.account,
            date=t.day.isoformat(),
            amount=t.amount,
            description=t.description[:200],
            merchant=t.merchant[:80] if t.merchant else None,
            provider_category=t.kind,
        )
        for i, t in enumerate(txs, start=1)
    ]
    return FinanceSnapshot(
        status="mock",
        source="fixtures",
        persona=p.id,
        as_of=as_of.isoformat(),
        accounts=_accounts(p),
        transactions=transactions,
        mortgage=p.mortgage,
        energy=p.energy,
    )


def _accounts(p: Persona) -> list[Account]:
    accounts = [
        Account(id="acc_current", name=f"{p.bank} Current Account", kind="current", provider=p.bank,
                balance=p.current_balance),
        Account(id="acc_savings", name=f"{p.savings_provider} {p.savings_name}", kind="savings",
                provider=p.savings_provider, balance=p.savings_balance),
    ]
    if p.card is not None:
        accounts.append(Account(id="acc_card", name=p.card.name, kind="credit", provider=p.card.provider,
                                balance=p.card.balance))
    if p.isa_balance > 0:
        accounts.append(Account(id="acc_isa", name="Vanguard Stocks and Shares ISA", kind="isa", provider="Vanguard",
                                balance=p.isa_balance))
    if p.pension_balance > 0:
        accounts.append(Account(id="acc_pension", name="Workplace pension", kind="pension", provider="Nest",
                                balance=p.pension_balance))
    if p.mortgage is not None:
        accounts.append(Account(id="acc_mortgage", name=f"{p.mortgage.lender} Mortgage", kind="mortgage",
                                provider=p.mortgage.lender or "Lender", balance=-p.mortgage.balance))
    return accounts
