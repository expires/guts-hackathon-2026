"""Friends leaderboard. Privacy rule: no money amounts ever leave a user's own scope.

Friends see only a display name, 0-100 habit scores, a growth index rebased to 100 and, if the user opts in,
their investment mix as percentages. Deep link used by the app: lifeline://join/<CODE>.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0, O, 1, I
INVITE_LENGTH = 8

REBASED_EXPLAIN = (
    "Growth is how an investment mix would have grown, shown as 100 at the start, "
    "so 150 means it grew by half. Friends are compared on the same scale, with no money amounts."
)


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FriendCard(_M):
    """Exactly what a friend can see about one person."""

    friend_id: str = Field(description="Opaque id for this person in the friends list. Not their account id")
    display_name: str
    overall_score: int | None = Field(default=None, ge=0, le=100, description="Overall habit score, 0-100")
    factor_scores: dict[str, int] = Field(
        description="Habit factor id to 0-100 score. Factors that cannot be scored yet are left out"
    )
    growth_index: float | None = Field(
        default=None, description="Their current investment mix replayed over the whole period, 100 at the start"
    )
    mix: dict[str, float] | None = Field(
        default=None, description="Investment mix as percentages by asset class. Only when they chose to share it"
    )
    data_status: Literal["live", "mock"] = Field(description="mock means sample data, not connected accounts")
    updated_at: str


class LeaderboardEntry(_M):
    card: FriendCard
    rank: int = Field(ge=1)
    is_me: bool
    score_vs_me: float | None = Field(
        default=None, description="Their overall score rebased so that yours is 100. Null if either is missing"
    )


class InviteCode(_M):
    code: Annotated[str, StringConstraints(pattern=r"^[A-HJ-NP-Z2-9]{8}$")]
    expires_at: str | None = None


class Leaderboard(_M):
    entries: list[LeaderboardEntry]
    my_invite_code: str
    explain: str = Field(default=REBASED_EXPLAIN, description="One plain-English line on what rebased to 100 means")


class JoinFriendRequest(_M):
    code: str = Field(min_length=1, max_length=16, description="An invite code. Case and spaces do not matter")


class ShareSettings(_M):
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
    share_mix: bool = Field(description="Let friends see your investment mix as percentages")


MyCard = FriendCard
