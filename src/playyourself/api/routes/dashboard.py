from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from playyourself.api.deps import get_snapshot
from playyourself.api.envelope import Envelope, ok
from playyourself.decision.portfolio import allocation_pct
from playyourself.domain.models import Snapshot, SourceStatus, Transaction

router = APIRouter(tags=["dashboard"])


class MonthSpend(BaseModel):
    month: str  # YYYY-MM
    total_pence: int
    by_category: dict[str, int]


class Dashboard(BaseModel):
    """Local UI only: contains pence amounts. Never share this payload."""

    liquid_cash_pence: int
    isa_value_pence: int
    net_worth_pence: int
    allocation_pct: dict[str, float]
    monthly_spend: list[MonthSpend]
    recent_transactions: list[Transaction]
    sources: dict[str, SourceStatus]
    as_of: datetime


def _month_key(i: int) -> str:
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def monthly_spend(snapshot: Snapshot, months: int = 6) -> list[MonthSpend]:
    end = snapshot.as_of.year * 12 + snapshot.as_of.month - 1
    idxs = list(range(end - months + 1, end + 1))
    by: dict[int, dict[str, int]] = {i: defaultdict(int) for i in idxs}
    for t in snapshot.transactions:
        i = t.ts.year * 12 + t.ts.month - 1
        if i in by and t.amount_pence < 0 and not t.is_transfer:
            by[i][t.category] += -t.amount_pence
    return [
        MonthSpend(month=_month_key(i), total_pence=sum(by[i].values()), by_category=dict(by[i]))
        for i in idxs
    ]


@router.get("/dashboard", response_model=Envelope[Dashboard])
async def dashboard(request: Request, snapshot: Snapshot = Depends(get_snapshot)):
    """Everything the dashboard tab needs. Pence values are for the local UI only."""
    holdings = sum(h.value_pence for h in snapshot.holdings)
    recent = sorted(snapshot.transactions, key=lambda t: t.ts, reverse=True)[:10]
    data = Dashboard(
        liquid_cash_pence=snapshot.liquid_cash_pence,
        isa_value_pence=snapshot.isa_value_pence,
        net_worth_pence=snapshot.liquid_cash_pence + holdings,
        allocation_pct=allocation_pct(snapshot),
        monthly_spend=monthly_spend(snapshot),
        recent_transactions=recent,
        sources=dict(snapshot.sources),
        as_of=snapshot.as_of,
    )
    return ok(data, request=request, snapshot=snapshot)
