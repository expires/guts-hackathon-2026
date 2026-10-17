from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from lifeline_contracts.domain import CharacterSpec
from lifeline_contracts.macro import MacroTable
from lifeline_contracts.observation import REGIONS
from lifeline_engine.population import (
    TENURES,
    build_population,
    ipf,
    max_margin_error,
    random_character,
    sample_people,
)

# ---------- IPF: hand-calculated ----------


def test_ipf_2x2_hand_case() -> None:
    # Uniform seed, rows (0.3, 0.7), cols (0.6, 0.4): independence gives the outer product.
    seed = np.ones((2, 2))
    rows = np.array([0.3, 0.7])
    cols = np.array([0.6, 0.4])
    fit = ipf(seed, [((0,), rows), ((1,), cols)])
    assert fit == pytest.approx(np.outer(rows, cols), abs=1e-12)


def test_ipf_keeps_seed_odds_ratio() -> None:
    # IPF preserves the cross-product ratio of the seed.
    seed = np.array([[4.0, 1.0], [1.0, 1.0]])
    fit = ipf(seed, [((0,), np.array([0.5, 0.5])), ((1,), np.array([0.5, 0.5]))])
    assert (fit[0, 0] * fit[1, 1]) / (fit[0, 1] * fit[1, 0]) == pytest.approx(4.0, rel=1e-9)
    # Symmetric margins and seed: a = d, b = c, a + b = 0.5, a/b = 2 -> a = 1/3, b = 1/6.
    assert fit[0, 0] == pytest.approx(1 / 3, abs=1e-9)
    assert fit[0, 1] == pytest.approx(1 / 6, abs=1e-9)


def test_ipf_rejects_bad_input() -> None:
    seed = np.ones((2, 2))
    with pytest.raises(ValueError):
        ipf(seed, [((0,), np.array([0.5, 0.5])), ((1,), np.array([0.7, 0.7]))])
    with pytest.raises(ValueError):
        ipf(seed, [((0,), np.array([1.0, 0.0, 0.0]))])
    with pytest.raises(ValueError):
        ipf(-seed, [((0,), np.array([0.5, 0.5]))])


@settings(max_examples=60, deadline=None)
@given(st.integers(min_value=0, max_value=2**32 - 1))
def test_ipf_margins_match_within_1e6(s: int) -> None:
    rng = np.random.default_rng(s)
    truth = rng.uniform(0.05, 1.0, size=(3, 4, 2, 3))
    truth /= truth.sum()
    margins = [
        ((0, 2), truth.sum(axis=(1, 3))),
        ((1,), truth.sum(axis=(0, 2, 3))),
        ((3,), truth.sum(axis=(0, 1, 2))),
    ]
    seed = rng.uniform(0.01, 1.0, size=truth.shape)
    fit = ipf(seed, margins)
    assert max_margin_error(fit, margins) < 1e-6


# ---------- population ----------


def test_population_fits_all_margins(macro: MacroTable) -> None:
    pop = build_population(macro, 2020)
    assert pop.joint.sum() == pytest.approx(1.0, abs=1e-9)
    assert max_margin_error(pop.joint, pop.margins) < 1e-6


def test_owner_share_follows_macro(fixture_macro: MacroTable) -> None:
    pop = build_population(fixture_macro, 2020)
    by_region_tenure = pop.joint.sum(axis=(1, 2, 4))
    own = TENURES.index("own")
    mortgage = TENURES.index("mortgage")
    for i, region in enumerate(REGIONS):
        share = (by_region_tenure[i, own] + by_region_tenure[i, mortgage]) / by_region_tenure[i].sum()
        assert share == pytest.approx(fixture_macro.value(_owner_key(), 2020, region) / 100, abs=1e-6)


def _owner_key():  # type: ignore[no-untyped-def]
    from lifeline_contracts.macro import MacroKey

    return MacroKey.OWNER_OCCUPIED_SHARE


def test_population_works_on_empty_table(empty_macro: MacroTable) -> None:
    pop = build_population(empty_macro, 2025)
    assert max_margin_error(pop.joint, pop.margins) < 1e-6


def test_sample_is_deterministic(macro: MacroTable) -> None:
    pop = build_population(macro, 2020)
    a = sample_people(pop, 50, np.random.default_rng(7))
    b = sample_people(pop, 50, np.random.default_rng(7))
    assert a == b


def test_sample_respects_structure(fixture_macro: MacroTable) -> None:
    pop = build_population(fixture_macro, 2020)
    people = sample_people(pop, 3000, np.random.default_rng(1))
    retired = [p for p in people if p.occupation_group == "retired"]
    assert retired
    assert sum(p.age >= 55 for p in retired) / len(retired) > 0.9
    owners = sum(p.housing in ("own", "mortgage") for p in people) / len(people)
    assert 0.5 < owners < 0.75


# ---------- random_character ----------


@given(st.integers(min_value=-(2**40), max_value=2**40))
@settings(max_examples=25, deadline=None)
def test_random_character_deterministic_and_valid(seed: int) -> None:
    from tests.unit.engine.conftest import build_fixture_macro

    macro = build_fixture_macro()
    a = random_character(seed, macro)
    b = random_character(seed, macro)
    assert a == b
    assert isinstance(a, CharacterSpec)
    CharacterSpec.model_validate(a.model_dump())
    assert a.region in REGIONS
    if a.housing == "mortgage":
        assert 0 < a.mortgage_balance <= a.property_value
    if a.housing in ("rent", "parents"):
        assert a.property_value == 0 and a.mortgage_balance == 0


def test_random_character_varies_with_seed(macro: MacroTable) -> None:
    chars = {random_character(s, macro).model_dump_json() for s in range(20)}
    assert len(chars) == 20


def test_random_character_on_empty_table(empty_macro: MacroTable) -> None:
    c = random_character(3, empty_macro)
    assert c.birth_year <= 2026
