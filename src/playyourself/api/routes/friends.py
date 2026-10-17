import asyncio
import json
import logging
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from playyourself.adapters.aggregator import fetch_snapshot
from playyourself.adapters.base import Capability
from playyourself.adapters.mock import MockAdapter
from playyourself.api.deps import HISTORY_DAYS, get_returns, get_snapshot
from playyourself.api.envelope import Envelope, ok
from playyourself.decision.friends import FriendCard, share_card
from playyourself.decision.returns import ReturnSeries
from playyourself.domain.models import Snapshot
from playyourself.settings import Settings, get_settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/friends", tags=["friends"])

# persona -> display name, shares pie (two of four, to demo opt-in)
FRIENDS = {
    "friend_alex": ("Alex", True),
    "friend_sam": ("Sam", True),
    "friend_priya": ("Priya", False),
    "friend_jordan": ("Jordan", False),
}


class ShareIn(BaseModel):
    share_pie: bool


class SharePrefs(BaseModel):
    share_pie: bool = False


class LeaderboardEntry(FriendCard):
    rank: int
    is_me: bool = False
    rebased_score: float | None = None  # overall score with my score = 100


def _prefs_path(settings: Settings) -> Path:
    return settings.cache_dir / "friends_prefs.json"


def load_prefs(settings: Settings) -> SharePrefs:
    try:
        return SharePrefs.model_validate_json(_prefs_path(settings).read_text())
    except (OSError, ValueError):
        return SharePrefs()


def save_prefs(settings: Settings, prefs: SharePrefs) -> None:
    path = _prefs_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prefs.model_dump()))


async def _friend_snapshot(persona: str) -> Snapshot:
    adapters = [
        MockAdapter("monzo", persona, frozenset({Capability.BALANCES, Capability.TRANSACTIONS})),
        MockAdapter("trading212", persona, frozenset({Capability.HOLDINGS, Capability.BALANCES})),
    ]
    return await fetch_snapshot(adapters, date.today() - timedelta(days=HISTORY_DAYS), 5.0, 0, None)


@router.get("/leaderboard", response_model=Envelope[list[LeaderboardEntry]])
async def leaderboard(
    request: Request,
    snapshot: Snapshot = Depends(get_snapshot),
    returns: ReturnSeries = Depends(get_returns),
    settings: Settings = Depends(get_settings),
):
    """Me plus friend personas, ranked by overall habit score. No amounts anywhere."""
    prefs = load_prefs(settings)
    snaps = await asyncio.gather(*(_friend_snapshot(p) for p in FRIENDS))
    cards = [(share_card("You", snapshot, prefs.share_pie, returns), True)]
    for (_, (name, pie)), snap in zip(FRIENDS.items(), snaps, strict=True):
        cards.append((share_card(name, snap, pie, returns), False))
    cards.sort(key=lambda c: -1 if c[0].overall_score is None else c[0].overall_score, reverse=True)
    mine = next(c.overall_score for c, me in cards if me)
    entries = [
        LeaderboardEntry(
            **c.model_dump(),
            rank=i + 1,
            is_me=me,
            rebased_score=(
                round(c.overall_score / mine * 100, 1)
                if mine and c.overall_score is not None
                else None
            ),
        )
        for i, (c, me) in enumerate(cards)
    ]
    return ok(entries, request=request, snapshot=snapshot)


@router.put("/share", response_model=Envelope[SharePrefs])
async def put_share(body: ShareIn, request: Request, settings: Settings = Depends(get_settings)):
    """Opt in or out of sharing your asset-class pie (percentages only)."""
    prefs = SharePrefs(share_pie=body.share_pie)
    save_prefs(settings, prefs)
    return ok(prefs, request=request)


@router.get("/me/card", response_model=Envelope[FriendCard])
async def my_card(
    request: Request,
    snapshot: Snapshot = Depends(get_snapshot),
    returns: ReturnSeries = Depends(get_returns),
    settings: Settings = Depends(get_settings),
):
    """Exactly the payload that would leave the device."""
    card = share_card("You", snapshot, load_prefs(settings).share_pie, returns)
    return ok(card, request=request, snapshot=snapshot)
