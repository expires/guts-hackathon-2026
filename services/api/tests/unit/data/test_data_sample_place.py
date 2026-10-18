"""Location bug (PENNY_V3_BUILD A1.4): town and region of an imported sample come from the student card.

Before the fix every sample profile was Manchester / north-west (docs/SEED_AUDIT.md)."""

from __future__ import annotations

from datetime import date

import pytest

from lifeline_contracts.observation import REGIONS
from lifeline_data.statements import list_samples
from lifeline_data.statements.samples import load_sample
from lifeline_engine.money.profile import profile

EXPECTED = {
    "scholarship": ("Sheffield", "yorkshire-and-the-humber"),
    "scottish": ("Edinburgh", "scotland"),
    "commuter": ("Bolton", "north-west"),
    "loan_england": ("Newcastle", "north-east"),
    "working": ("Leeds", "yorkshire-and-the-humber"),
    "mature": ("Birmingham", "west-midlands"),
    "international": ("Coventry", "west-midlands"),
    "final_year": ("Exeter", "south-west"),
    "rich": ("Leeds", "yorkshire-and-the-humber"),
    "graduate": ("London", "london"),
}


def test_every_card_city_is_expected() -> None:
    cards = {s.id: s.city for s in list_samples()}
    assert cards == {k: town for k, (town, _) in EXPECTED.items()}


@pytest.mark.parametrize("sample_id", sorted(EXPECTED))
def test_imported_profile_place_matches_card(sample_id: str) -> None:
    town, region = EXPECTED[sample_id]
    snap = load_sample(sample_id)
    assert snap.region == region
    assert snap.holder is not None
    assert snap.holder.town == town and snap.holder.region == region
    assert region in REGIONS
    today = date.fromisoformat(max(t.date for t in snap.transactions))
    decision, character = profile(snap, today)
    assert decision.region == region
    assert character.town == town and character.region == region
