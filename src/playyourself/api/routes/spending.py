from fastapi import APIRouter, Depends, Query, Request

from playyourself.api.deps import get_snapshot
from playyourself.api.envelope import Envelope, ok
from playyourself.decision.spending import SpendingAnalysis, analyse_spending
from playyourself.domain.models import Snapshot

router = APIRouter(tags=["spending"])


@router.get("/spending", response_model=Envelope[SpendingAnalysis])
async def get_spending(
    request: Request,
    months: int = Query(6, ge=1, le=12),
    snapshot: Snapshot = Depends(get_snapshot),
):
    """Spending analysis over the last N complete months. Pence values: local UI only."""
    return ok(analyse_spending(snapshot, months), request=request, snapshot=snapshot)
