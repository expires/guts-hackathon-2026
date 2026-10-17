"""Friends leaderboard. Friends see scores and a rebased growth index, never money amounts.

Deep link the app uses to add a friend: lifeline://join/<CODE> (8 characters, case does not matter).
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from lifeline_api import money
from lifeline_api.auth import Subject
from lifeline_api.errors import ApiError
from lifeline_api.friends_card import build_card, rebased_score
from lifeline_api.sim_bridge import call_pure
from lifeline_api.social import SocialProfile, SocialStore
from lifeline_api.state import AppState, get_state
from lifeline_contracts.friends import (
    FriendCard,
    InviteCode,
    JoinFriendRequest,
    Leaderboard,
    LeaderboardEntry,
    MyCard,
    ShareSettings,
)

router = APIRouter(tags=["friends"])


def _social(state: AppState) -> SocialStore:
    assert state.social is not None  # set in build_state
    return state.social


def _friend_name(p: SocialProfile) -> str:
    return p.display_name or f"Friend {p.friend_id[3:7].upper()}"


async def _card(state: AppState, sub: str, p: SocialProfile, name: str) -> FriendCard:
    snap = await money.snapshot(state, sub)
    return await call_pure(
        build_card, snap, money.returns(), friend_id=p.friend_id, display_name=name, share_mix=p.share_mix
    )


def _vs_me(is_me: bool, theirs: int | None, mine: int | None) -> float | None:
    if is_me:
        return 100.0 if mine is not None else None
    return rebased_score(theirs, mine)


async def _leaderboard(state: AppState, sub: str) -> Leaderboard:
    social = _social(state)
    me = social.ensure(sub)
    subs = [sub, *social.friends_of(sub)]
    cards: list[tuple[bool, FriendCard]] = []
    for s in subs:
        p = social.profile(s) or social.ensure(s)
        is_me = s == sub
        cards.append((is_me, await _card(state, s, p, (me.display_name or "You") if is_me else _friend_name(p))))
    cards.sort(key=lambda c: (c[1].overall_score is None, -(c[1].overall_score or 0), c[1].display_name))
    mine = next(c.overall_score for is_me, c in cards if is_me)
    entries = [
        LeaderboardEntry(
            card=c, rank=i, is_me=is_me,
            score_vs_me=_vs_me(is_me, c.overall_score, mine),
        )
        for i, (is_me, c) in enumerate(cards, start=1)
    ]
    return Leaderboard(entries=entries, my_invite_code=me.invite_code)


@router.get("/v1/friends", response_model=Leaderboard, response_model_exclude_none=True)
async def get_leaderboard(request: Request, sub: Subject) -> Leaderboard:
    """You and your friends, best habit score first. Only scores and a rebased growth index are shared."""
    state = get_state(request)
    async with _social(state).lock:
        return await _leaderboard(state, sub)


@router.post("/v1/friends/invite", response_model=InviteCode, response_model_exclude_none=True)
async def create_invite(request: Request, sub: Subject, rotate: bool = Query(default=False)) -> InviteCode:
    """Your invite code. It stays the same until you ask for a new one with ?rotate=true.

    Share it as the link lifeline://join/<CODE>."""
    social = _social(get_state(request))
    async with social.lock:
        p = social.rotate_code(sub) if rotate else social.ensure(sub)
        return InviteCode(code=p.invite_code)


@router.post("/v1/friends/join", response_model=Leaderboard, response_model_exclude_none=True)
async def join_friend(body: JoinFriendRequest, request: Request, sub: Subject) -> Leaderboard:
    """Add a friend with their invite code (from lifeline://join/<CODE>). Friendship goes both ways."""
    state = get_state(request)
    social = _social(state)
    async with social.lock:
        other = social.subject_for_code(body.code)
        if other is None:
            raise ApiError(404, "invite_not_found", "That invite code does not match anyone. Check it and try again.")
        if other == sub:
            raise ApiError(400, "cannot_add_self", "That is your own invite code. Send it to a friend instead.")
        social.ensure(sub)
        social.add_friendship(sub, other)  # already friends: nothing changes
        return await _leaderboard(state, sub)


@router.get("/v1/friends/me", response_model=MyCard, response_model_exclude_none=True)
async def get_my_card(request: Request, sub: Subject) -> MyCard:
    """Exactly what your friends can see about you."""
    state = get_state(request)
    social = _social(state)
    async with social.lock:
        p = social.ensure(sub)
        return await _card(state, sub, p, _friend_name(p))


@router.put("/v1/friends/me", response_model=MyCard, response_model_exclude_none=True)
async def put_my_settings(body: ShareSettings, request: Request, sub: Subject) -> MyCard:
    """Choose the name friends see and whether they can see your investment mix as percentages."""
    state = get_state(request)
    social = _social(state)
    async with social.lock:
        p = social.set_settings(sub, body.display_name, body.share_mix)
        return await _card(state, sub, p, _friend_name(p))


@router.delete("/v1/friends/{friend_id}", response_model=Leaderboard, response_model_exclude_none=True)
async def remove_friend(friend_id: str, request: Request, sub: Subject) -> Leaderboard:
    """Remove a friend for both of you. Removing someone who is not a friend does nothing."""
    state = get_state(request)
    social = _social(state)
    async with social.lock:
        other = social.subject_for_friend_id(friend_id)
        if other is not None:
            social.remove_friendship(sub, other)
        return await _leaderboard(state, sub)
