"""Your profile: per-source connection rows and the stats sections (GET /v1/profile/stats).

Pure functions of the user's snapshots and the provider connection list. Every number comes from the engine
(habits, spending, subscriptions, net worth) or from the connected data (Trading 212 positions); a section the data
cannot support is unavailable with a hint, never filled in.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from lifeline_api import money, onboarding
from lifeline_contracts.accounts import AssetClass, Holding, ProviderConnection
from lifeline_contracts.finance import FinanceSnapshot, HabitScore
from lifeline_contracts.profile import (
    InvestmentSummary,
    MixSlice,
    NetWorthSummary,
    ProfileConnection,
    ProfileSection,
    ProfileStats,
    SourceId,
    SpendingSummary,
)
from lifeline_engine import money as money_engine
from lifeline_engine.habits import habit_score, monthly_income
from lifeline_engine.money import dates
from lifeline_engine.money.profile import full_data_months, full_months_before, is_cash, monthly_spend
from lifeline_engine.money.spending import by_category, spending

MIN_HABIT_MONTHS = 2
T212 = "trading212"
TITLES: dict[SourceId, str] = {
    "monzo": "Monzo",
    "trading212": "Trading 212",
    "statement": "Statement",
    "manual": "Your numbers",
    "sample": "Sample student",
}
ASSET_LABELS: dict[AssetClass, str] = {
    "equity": "Shares",
    "bond": "Bonds",
    "cash": "Cash",
    "property": "Property",
    "commodity": "Commodities",
    "other": "Other",
}
HINT_TRANSACTIONS = "Connect Monzo, upload a statement or use a sample student to see your {what}."


def _day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b %Y')}"


def _real(snap: FinanceSnapshot | None) -> list[str]:
    """Dates of the transactions that came from a bank, statement or sample (not typed in, not logged)."""
    return [] if snap is None else [t.date for t in snap.transactions if onboarding._is_bank(t)]


def transaction_source(snap: FinanceSnapshot) -> SourceId:
    if "monzo" in snap.source:
        return "monzo"
    if snap.source == "sample":
        return "sample"
    if snap.source == "manual":
        return "manual"
    return "statement"


def _holdings_text(n: int) -> str:
    return f"{n} holding" if n == 1 else f"{n} holdings"


def connections(
    snap: FinanceSnapshot | None, stored: FinanceSnapshot | None, providers: list[ProviderConnection]
) -> list[ProfileConnection]:
    by = {p.provider: p for p in providers}
    live_status = "cached" if snap is not None and snap.status == "cached" else "live"
    out: list[ProfileConnection] = []

    monzo = by.get("monzo")
    if monzo is not None and monzo.connected:
        dates_ = _real(snap) if snap is not None and "monzo" in snap.source else []
        if dates_:
            provides = f"Transactions since {_day(min(dates_))} ({len(dates_)})"
        else:
            provides = "Approve access in the Monzo app to bring in your history"
        out.append(
            ProfileConnection(
                id="monzo",
                title=TITLES["monzo"],
                connected=True,
                data_status=live_status,
                last_synced=snap.as_of if snap is not None and dates_ else None,
                provides=provides,
            )
        )
    else:
        out.append(ProfileConnection(id="monzo", title=TITLES["monzo"], connected=False))

    t212 = by.get(T212)
    if t212 is not None and t212.connected:
        has = snap is not None and any(a.provider == T212 for a in snap.accounts)
        if has and snap is not None:
            n = len(snap.holdings)
            provides = _holdings_text(n) if n else "Total value only, positions not available"
        else:
            provides = "Connected, waiting for data"
        out.append(
            ProfileConnection(
                id="trading212",
                title=TITLES["trading212"],
                connected=True,
                data_status=live_status,
                provides=provides,
                last_synced=snap.as_of if has and snap is not None else None,
            )
        )
    else:
        out.append(ProfileConnection(id="trading212", title=TITLES["trading212"], connected=False))

    inputs = onboarding.inputs_of(stored)
    if stored is not None and "statement" in inputs:
        ds = _real(stored)
        provides = f"Transactions from {_day(min(ds))} to {_day(max(ds))} ({len(ds)})" if ds else "Statement uploaded"
        out.append(
            ProfileConnection(
                id="statement",
                title=TITLES["statement"],
                connected=True,
                data_status="live",
                last_synced=stored.as_of,
                provides=provides,
            )
        )
    else:
        out.append(ProfileConnection(id="statement", title=TITLES["statement"], connected=False))

    if stored is not None and "manual" in inputs:
        n_inc, n_debt = len(stored.income_sources), len(stored.debts)
        parts = [f"{n_inc} income {'source' if n_inc == 1 else 'sources'}"] if n_inc else []
        if n_debt:
            parts.append(f"{n_debt} {'debt' if n_debt == 1 else 'debts'}")
        out.append(
            ProfileConnection(
                id="manual",
                title=TITLES["manual"],
                connected=True,
                data_status="live",
                last_synced=stored.as_of,
                provides=", ".join(parts) if parts else "Accounts and costs you typed in",
            )
        )
    else:
        out.append(ProfileConnection(id="manual", title=TITLES["manual"], connected=False))

    if stored is not None and "sample" in inputs:
        who = stored.holder.name if stored.holder is not None else "student"
        ds = _real(stored)
        out.append(
            ProfileConnection(
                id="sample",
                title=TITLES["sample"],
                connected=True,
                data_status="mock",
                label=money_engine.SAMPLE_LABEL,
                last_synced=stored.as_of,
                sample_id=stored.persona,
                provides=f"{who}, {len(ds)} transactions since {_day(min(ds))}" if ds else who,
            )
        )
    else:
        out.append(ProfileConnection(id="sample", title=TITLES["sample"], connected=False))
    return out


# ---------- sections ----------


def _habits(snap: FinanceSnapshot | None, today: date | None) -> ProfileSection:
    title = "Your habits"
    if snap is None or today is None or not _real(snap):
        return ProfileSection(
            id="habits", title=title, available=False, missing_hint=HINT_TRANSACTIONS.format(what="habits")
        )
    have = [
        m
        for m in full_data_months(snap, full_months_before(today, 3))
        if any(t.date[:7] == m for t in snap.transactions)
    ]
    if len(have) < MIN_HABIT_MONTHS:
        return ProfileSection(
            id="habits",
            title=title,
            available=False,
            missing_hint=f"Habits need at least {MIN_HABIT_MONTHS} full months of transactions. "
            f"You have {len(have)}. Upload a longer statement or keep Monzo connected.",
        )
    score: HabitScore = habit_score(snap, today)
    return ProfileSection(id="habits", title=title, available=True, sources=[transaction_source(snap)], habits=score)


def _spending(snap: FinanceSnapshot | None, today: date | None) -> ProfileSection:
    title = "Your spending"
    if snap is None or today is None or not _real(snap):
        return ProfileSection(
            id="spending", title=title, available=False, missing_hint=HINT_TRANSACTIONS.format(what="spending")
        )
    used = [
        m
        for m in full_data_months(snap, full_months_before(today, 3))
        if any(t.date[:7] == m for t in snap.transactions)
    ]
    partial = not used
    month = used[-1] if used else dates.month_of(today)
    cats = spending(snap.transactions, month)[:3]
    so_far = round(sum(v for v, _ in by_category(snap.transactions, month).values()), 2)
    out_ = monthly_spend(snap, today) if used else so_far
    income = monthly_income(snap, today)
    subs = money_engine.subscriptions_response(snap, today)
    return ProfileSection(
        id="spending",
        title=title,
        available=True,
        sources=[transaction_source(snap)],
        spending=SpendingSummary(
            month=month,
            partial=partial,
            months_used=len(used),
            monthly_in=None if income is None else round(income, 2),
            monthly_out=out_,
            top_categories=cats,
            subscriptions_monthly=subs.monthly_total,
            subscriptions_count=subs.count,
        ),
    )


def _account_source(provider: str, snap: FinanceSnapshot) -> SourceId:
    if provider == "monzo":
        return "monzo"
    if provider == T212:
        return "trading212"
    return transaction_source(snap)


def _net_worth(snap: FinanceSnapshot | None) -> ProfileSection:
    title = "Net worth"
    hint = "Connect Monzo or Trading 212, upload a statement or enter your numbers to see your net worth."
    if snap is None:
        return ProfileSection(id="net_worth", title=title, available=False, missing_hint=hint)
    ov = money.overview(snap)
    if not ov.net_worth_parts:
        return ProfileSection(id="net_worth", title=title, available=False, missing_hint=hint)
    invested = round(sum(a.balance for a in snap.accounts if a.kind in ("isa", "pension") and not is_cash(a)), 2)
    cash = ov.balance
    other = round(ov.net_worth - cash - invested, 2)
    shown = [a for a in snap.accounts if money._shown(a)]
    sources: list[SourceId] = []
    for a in shown or snap.accounts:
        s = _account_source(a.provider, snap)
        if s not in sources:
            sources.append(s)
    return ProfileSection(
        id="net_worth",
        title=title,
        available=True,
        sources=sources,
        net_worth=NetWorthSummary(
            net_worth=ov.net_worth, cash=cash, investments=max(0.0, invested), other=other, parts=ov.net_worth_parts
        ),
    )


def _mix(holdings: list[Holding]) -> list[MixSlice]:
    totals: dict[AssetClass, float] = defaultdict(float)
    for h in holdings:
        totals[h.asset_class] += h.value
    whole = sum(totals.values())
    if whole <= 0:
        return []
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        MixSlice(asset_class=c, label=ASSET_LABELS[c], value=round(v, 2), share_pct=round(v / whole * 100, 1))
        for c, v in ranked
    ]


def _investments(snap: FinanceSnapshot | None) -> ProfileSection:
    title = "Investments"
    accounts = [] if snap is None else [a for a in snap.accounts if a.provider == T212]
    if snap is None or not accounts:
        return ProfileSection(
            id="investments", title=title, available=False, missing_hint="Connect Trading 212 to see your investments."
        )
    total = round(sum(a.balance for a in accounts), 2)
    held = sorted(snap.holdings, key=lambda h: (-h.value, h.instrument_id))
    invested = round(sum(h.value for h in held), 2) if held else None
    note = None if held else "We could only read the total value of your account, not the individual holdings."
    return ProfileSection(
        id="investments",
        title=title,
        available=True,
        sources=["trading212"],
        investments=InvestmentSummary(
            total_value=total,
            invested_value=invested,
            holdings_count=len(held),
            mix=_mix(held),
            top_holdings=held,
            note=note,
        ),
    )


def build(
    snap: FinanceSnapshot | None, stored: FinanceSnapshot | None, providers: list[ProviderConnection]
) -> ProfileStats:
    today = None if snap is None else money.today(snap)
    return ProfileStats(
        connections=connections(snap, stored, providers),
        sections=[_habits(snap, today), _spending(snap, today), _net_worth(snap), _investments(snap)],
    )
