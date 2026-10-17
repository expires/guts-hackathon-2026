from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from lifeline_contracts.macro import MacroKey, MacroTable, MacroValue
from lifeline_engine.periods import macro_state, similar_years, standardise
from lifeline_engine.population import Person, build_population, sample_people
from lifeline_engine.twins import TwinIndex, find_twins, inverse_covariance, person_features


def _person(age: int = 30, income: float = 30_000, housing: str = "rent", region: str = "london") -> Person:
    return Person(
        region=region,
        age=age,
        sex="female",
        occupation_group="admin_sales",
        occupation="receptionist",
        housing=housing,  # type: ignore[arg-type]
        annual_income=income,
        savings=1_000,
        debt=0,
        property_value=0,
        mortgage_balance=0,
    )


# ---------- twins ----------


def test_singular_covariance_is_handled() -> None:
    # Everyone rents in London with no debt: several constant columns, rank-deficient covariance.
    people = [_person(age=20 + i, income=20_000 + 1_000 * i) for i in range(10)]
    inv = inverse_covariance(np.vstack([person_features(p) for p in people]))
    assert np.all(np.isfinite(inv))
    twins = find_twins(people[3], people, 3)
    assert twins[0].index == 3
    assert twins[0].distance == pytest.approx(0.0, abs=1e-9)
    assert {t.index for t in twins[1:]} == {2, 4}


def test_single_person_population() -> None:
    p = _person()
    twins = find_twins(p, [p], 5)
    assert len(twins) == 1 and twins[0].distance == pytest.approx(0.0, abs=1e-9)


def test_k_zero_and_empty() -> None:
    p = _person()
    assert find_twins(p, [p], 0) == []
    with pytest.raises(ValueError):
        find_twins(p, [], 3)


@settings(max_examples=20, deadline=None)
@given(st.integers(min_value=0, max_value=2**32 - 1), st.integers(min_value=0, max_value=199))
def test_twin_of_member_is_itself_at_distance_zero(seed: int, member: int) -> None:
    from tests.unit.engine.conftest import build_fixture_macro

    pop = build_population(build_fixture_macro(), 2020)
    people = sample_people(pop, 200, np.random.default_rng(seed))
    index = TwinIndex.build(people)
    twins = index.nearest(person_features(people[member]), 5)
    assert twins[0].distance == pytest.approx(0.0, abs=1e-6)
    assert twins[0].person == people[member]
    assert [t.distance for t in twins] == sorted(t.distance for t in twins)


def test_twins_deterministic(macro: MacroTable) -> None:
    pop = build_population(macro, 2020)
    people = sample_people(pop, 300, np.random.default_rng(11))
    target = _person(age=40, income=45_000, housing="mortgage", region="north-west")
    a = find_twins(target, people, 10)
    b = find_twins(target, people, 10)
    assert a == b


# ---------- periods ----------


def _table(rows: dict[int, dict[MacroKey, float]]) -> MacroTable:
    values: dict[str, MacroValue] = {}
    for year, kv in rows.items():
        for key, v in kv.items():
            values[MacroTable.make_key(key, year, None)] = MacroValue(
                key=key, year=year, region=None, value=v, source="t", series_id=key.value, status="mock"
            )
    return MacroTable(values=values)


def test_macro_state_hand_case() -> None:
    t = _table({2000: {MacroKey.BANK_RATE: 5.0}, 2001: {MacroKey.BANK_RATE: 4.0, MacroKey.CPI_INFLATION: 2.0}})
    s = macro_state(t, 2001)
    # bank 4, change -1, cpi 2; house price change, unemployment, stock return missing -> 0.
    assert s.tolist() == [4.0, -1.0, 2.0, 0.0, 0.0, 0.0]
    assert macro_state(t, 2000).tolist()[1] == 0.0


def test_standardise_zero_spread() -> None:
    z = standardise(np.array([[1.0, 5.0], [3.0, 5.0]]))
    assert z.tolist() == [[-1.0, 0.0], [1.0, 0.0]]


def test_similar_years_hand_case() -> None:
    # Features used: bank rate and its change (others missing, so z = 0).
    # (rate, change): 2010 (5.1, +0.1), 1995 (9.0, 0), 2002 (4.0, -5.0), 2004 (5.0, +1.0).
    # Population std: rate 1.911, change 2.356. z-distance to 2010:
    # 2004 = sqrt((0.1/1.911)^2 + (0.9/2.356)^2) = 0.386
    # 1995 = sqrt((3.9/1.911)^2 + (0.1/2.356)^2) = 2.041
    # 2002 = sqrt((1.1/1.911)^2 + (5.1/2.356)^2) = 2.240
    t = _table(
        {
            1995: {MacroKey.BANK_RATE: 9.0},
            2002: {MacroKey.BANK_RATE: 4.0},
            2004: {MacroKey.BANK_RATE: 5.0},
            2010: {MacroKey.BANK_RATE: 5.1},
        }
    )
    matches = similar_years(t, 2010, 2, candidates=[1995, 2002, 2004])
    assert [m.year for m in matches] == [2004, 1995]
    assert [m.distance for m in matches] == pytest.approx([0.386, 2.041], abs=1e-3)


def test_similar_years_excludes_target_and_exclusions(macro: MacroTable) -> None:
    matches = similar_years(macro, 2008, 5, exclude=[2007, 2009])
    years = [m.year for m in matches]
    assert len(years) == 5
    assert 2008 not in years and 2007 not in years and 2009 not in years
    assert similar_years(macro, 2008, 5) == similar_years(macro, 2008, 5)


def test_similar_years_empty_table(empty_macro: MacroTable) -> None:
    assert similar_years(empty_macro, 2020, 3) == []
