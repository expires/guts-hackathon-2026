"""Hand-made FinanceSnapshot builders for engine tests. No lifeline_data needed."""

from __future__ import annotations

from datetime import date, timedelta

from lifeline_contracts.finance import (
    Account,
    EnergyDetails,
    FinanceSnapshot,
    MortgageDetails,
    Transaction,
)
from lifeline_engine.money.dates import add_months

_counter = [0]


def tx(
    d: str | date, amount: float, description: str, merchant: str | None = None, account: str = "cur"
) -> Transaction:
    _counter[0] += 1
    ds = d if isinstance(d, str) else d.isoformat()
    return Transaction(
        id=f"t{_counter[0]}", account_id=account, date=ds, amount=amount, description=description, merchant=merchant
    )


def monthly(start: str, n: int, amount: float | list[float], description: str, merchant: str | None = None,
            account: str = "cur") -> list[Transaction]:
    d0 = date.fromisoformat(start)
    amounts = amount if isinstance(amount, list) else [amount] * n
    return [tx(add_months(d0, i), amounts[i], description, merchant, account) for i in range(n)]


def every(start: str, n: int, days: int, amount: float, description: str, merchant: str | None = None
          ) -> list[Transaction]:
    d0 = date.fromisoformat(start)
    return [tx(d0 + timedelta(days=days * i), amount, description, merchant) for i in range(n)]


def snapshot(
    txs: list[Transaction],
    accounts: list[Account] | None = None,
    as_of: str = "2026-10-17",
    mortgage: MortgageDetails | None = None,
    energy: EnergyDetails | None = None,
    persona: str | None = "test-leeds",
) -> FinanceSnapshot:
    return FinanceSnapshot(
        status="mock",
        source="fixtures",
        persona=persona,
        as_of=as_of,
        accounts=accounts or [Account(id="cur", name="Current", kind="current", provider="Bank", balance=1000.0)],
        transactions=txs,
        mortgage=mortgage,
        energy=energy,
    )


def homeowner() -> FinanceSnapshot:
    """Deal ends 2027-03-31 (165 days after 2026-10-17), card debt, savings, Netflix price rise."""
    txs = [
        *monthly("2025-10-28", 12, 2500.0, "ACME LTD SALARY", "Acme"),
        *monthly("2025-11-01", 12, -822.03, "NATIONWIDE MORTGAGE", "Nationwide"),
        *monthly("2025-11-09", 12, [-12.99] * 7 + [-13.99] * 5, "NETFLIX.COM", "Netflix"),
        *monthly("2025-11-14", 12, -12.99, "SPOTIFY UK", "Spotify"),
        *monthly("2025-11-06", 12, -142.0, "OCTOPUS ENERGY", "Octopus Energy"),
        *monthly("2025-11-21", 12, -360.0, "BARCLAYCARD PAYMENT", "Barclaycard"),
        *monthly("2025-11-30", 12, 7.0, "INTEREST PAID", None, "sav"),
        *monthly("2025-11-25", 12, -70.0, "INTEREST CHARGED", None, "card"),
        *every("2025-10-20", 52, 7, -80.0, "TESCO STORES", "Tesco"),
    ]
    accounts = [
        Account(id="cur", name="Current", kind="current", provider="Lloyds", balance=1200.0),
        Account(id="sav", name="Saver", kind="savings", provider="Halifax", balance=6800.0),
        Account(id="card", name="Card", kind="credit", provider="Barclaycard", balance=-3400.0),
        Account(id="mort", name="Mortgage", kind="mortgage", provider="Nationwide", balance=-180000.0),
    ]
    mortgage = MortgageDetails(
        balance=180000.0, rate_pct=2.09, rate_type="fixed", fixed_until="2027-03-31", years_left=23,
        property_value=240000.0, monthly_payment=822.03, lender="Nationwide",
    )
    energy = EnergyDetails(supplier="Octopus", tariff="Flexible", monthly_cost=142.0, fixed_until=None)
    return snapshot(txs, accounts, mortgage=mortgage, energy=energy, persona="homeowner-leeds")
