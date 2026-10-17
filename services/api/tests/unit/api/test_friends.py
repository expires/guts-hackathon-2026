"""Friends leaderboard: store, card and privacy rules (offline)."""

from __future__ import annotations

from pathlib import Path

from lifeline_api.auth import demo_subject
from lifeline_api.friends_card import build_card, mix_percentages, rebased_score
from lifeline_api.social import SocialStore, normalise_code
from lifeline_contracts import friends as friends_contracts
from lifeline_contracts.accounts import Holding
from lifeline_contracts.finance import FinanceSnapshot
from lifeline_contracts.friends import INVITE_ALPHABET, INVITE_LENGTH
from lifeline_data.finance import fixture_snapshot
from lifeline_data.returns import load_returns

FORBIDDEN = ("pence", "amount", "balance", "value", "salary", "income")


def _store(tmp_path: Path) -> SocialStore:
    return SocialStore(tmp_path / "social.json")


def test_code_alphabet_length_and_uniqueness(tmp_path: Path) -> None:
    s = _store(tmp_path)
    codes = {s.ensure(f"sub{i}").invite_code for i in range(300)}
    assert len(codes) == 300
    for c in codes:
        assert len(c) == INVITE_LENGTH and set(c) <= set(INVITE_ALPHABET)
        assert not set(c) & set("0O1I")
    assert normalise_code(" ab cd ") == "ABCD"


def test_stable_code_and_rotate(tmp_path: Path) -> None:
    s = _store(tmp_path)
    first = s.ensure("a").invite_code
    assert s.ensure("a").invite_code == first
    new = s.rotate_code("a").invite_code
    assert new != first
    assert s.subject_for_code(first) is None
    assert s.subject_for_code(new.lower()) == "a"


def test_friendship_symmetric_idempotent_and_self(tmp_path: Path) -> None:
    s = _store(tmp_path)
    assert s.add_friendship("a", "b") is True
    assert s.add_friendship("b", "a") is False
    assert s.add_friendship("a", "a") is False
    assert s.friends_of("a") == ["b"] and s.friends_of("b") == ["a"]
    assert s.remove_friendship("b", "a") is True
    assert s.friends_of("a") == [] and s.friends_of("b") == []


def test_persists_across_instances(tmp_path: Path) -> None:
    s = _store(tmp_path)
    p = s.set_settings("a", "Ash", True)
    s.ensure("b")
    s.add_friendship("a", "b")
    again = _store(tmp_path)
    assert again.profile("a") == p
    assert again.friends_of("b") == ["a"]
    assert (tmp_path / "social.json").stat().st_mode & 0o777 == 0o600


def test_corrupt_file_starts_empty(tmp_path: Path) -> None:
    (tmp_path / "social.json").write_text("{nope")
    assert _store(tmp_path).friends_of("a") == []


def test_share_mix_off_hides_mix_and_on_shows_percentages() -> None:
    snap = _snapshot_with_holdings()
    off = build_card(snap, load_returns(), friend_id="fr_x", display_name="A", share_mix=False)
    on = build_card(snap, load_returns(), friend_id="fr_x", display_name="A", share_mix=True)
    assert off.mix is None
    assert on.mix is not None and abs(sum(on.mix.values()) - 100) < 0.5
    assert off.growth_index is not None and off.growth_index == on.growth_index


def test_growth_index_depends_only_on_mix() -> None:
    snap = _snapshot_with_holdings()
    doubled = snap.model_copy(update={"holdings": [h.model_copy(update={"value": h.value * 7}) for h in snap.holdings]})
    a = build_card(snap, load_returns(), friend_id="f", display_name="A", share_mix=False)
    b = build_card(doubled, load_returns(), friend_id="f", display_name="A", share_mix=False)
    assert a.growth_index == b.growth_index
    assert mix_percentages(snap) == mix_percentages(doubled)


def test_rebased_score() -> None:
    assert rebased_score(60, 80) == 75.0
    assert rebased_score(None, 80) is None
    assert rebased_score(60, None) is None
    assert rebased_score(60, 0) is None


def test_schema_has_no_money_field_names() -> None:
    names: set[str] = set()
    for model in (
        friends_contracts.FriendCard,
        friends_contracts.LeaderboardEntry,
        friends_contracts.Leaderboard,
        friends_contracts.InviteCode,
        friends_contracts.JoinFriendRequest,
        friends_contracts.ShareSettings,
    ):
        names |= set(model.model_fields)
    assert names
    assert not [n for n in names if any(w in n for w in FORBIDDEN)]


def _snapshot_with_holdings() -> FinanceSnapshot:
    snap = fixture_snapshot(demo_subject("dev-0"))
    holdings = [
        Holding(instrument_id="a", name="Global fund", quantity=10, value=3000.0, asset_class="equity", region="US"),
        Holding(instrument_id="b", name="UK fund", quantity=5, value=1000.0, asset_class="equity", region="UK"),
        Holding(instrument_id="c", name="Bond fund", quantity=2, value=1000.0, asset_class="bond"),
    ]
    return snap.model_copy(update={"holdings": holdings})
