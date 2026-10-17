from __future__ import annotations

import string
from collections import Counter

import pytest

from lifeline_contracts.domain import Event
from lifeline_contracts.macro import MacroTable
from lifeline_sim.concepts import concept_ids
from lifeline_sim.events.engine import (
    STATE_VARS,
    LoadedTemplate,
    build_event,
    load_templates,
    render,
    resolve,
    state_env,
)
from lifeline_sim.events.schema import Template
from lifeline_sim.expr import Expr, ExprError
from lifeline_sim.index import load_weights
from lifeline_sim.replay import view_for
from lifeline_sim.state import initial_state

from .helpers import preset

TEMPLATES = load_templates()


def test_template_count_and_areas() -> None:
    assert len(TEMPLATES) >= 150
    areas = Counter(lt.t.area for lt in TEMPLATES)
    assert len(areas) == 11  # every area in BUILD_SPEC section 2
    assert all(n >= 10 for n in areas.values()), areas


@pytest.mark.parametrize("lt", TEMPLATES, ids=lambda lt: lt.t.id)
def test_template_rules(lt: LoadedTemplate) -> None:
    t = lt.t
    assert sum(c.default for c in t.choices) == 1
    assert t.concept_id in concept_ids()
    branches = [b for c in t.choices for b in c.branches]
    goods = {bool(b.good.eval(_neutral_facts(t))) for b in branches}
    assert len(branches) >= 2
    # Each template offers a good and a bad money path (for most fact values).
    assert goods == {True, False} or any(not isinstance(b.good, Expr) or b.good.names for b in branches)
    for name in (n for e in [t.probability, *t.facts.values()] for n in e.names):
        assert name in STATE_VARS or name in t.facts or name in _macro_vars(), f"{t.id}: unknown name {name}"


def _macro_vars() -> set[str]:
    from lifeline_sim.macroview import macro_names

    return set(macro_names())


def _neutral_facts(t: Template) -> dict[str, float]:
    return dict.fromkeys(t.facts, 1.0)


@pytest.mark.parametrize("lt", TEMPLATES, ids=lambda lt: lt.t.id)
def test_template_renders_and_resolves(lt: LoadedTemplate, macro: MacroTable) -> None:
    """Build every template against a real state, render all text, resolve every choice."""
    mv = view_for(macro)
    w = load_weights()
    for pid, year in (("nurse-leeds", 2008), ("banker-london", 2022), ("pensioner", 2015)):
        s = initial_state(preset(pid), "preset", year, 1, mv, w)
        s.last_net_income = 20_000.0
        env = {**mv.env(s.year, s.region), **state_env(s)}
        ev = build_event(lt, s, mv, env, f"ev-{year}-1")
        assert isinstance(ev, Event)
        _check_placeholders_are_facts(lt.t.text, ev)
        for choice in lt.t.choices:
            res = resolve(ev, choice.id, s.seed)
            assert res.text
            for b in choice.branches:
                render(b.text, ev.facts)
        if lt.macro_keys:
            assert ev.sources, f"{lt.t.id} reads macro data but has no sources"


def _check_placeholders_are_facts(text: str, ev: Event) -> None:
    for _, field, _, _ in string.Formatter().parse(text):
        if field:
            assert field in ev.facts


def test_state_env_matches_declared_vars(macro: MacroTable) -> None:
    s = initial_state(preset("nurse-leeds"), "preset", 2006, 1, view_for(macro), load_weights())
    assert set(state_env(s)) == set(STATE_VARS)


def test_template_ids_unique_and_prefixed() -> None:
    ids = [lt.t.id for lt in TEMPLATES]
    assert len(ids) == len(set(ids))
    assert all(i.split(".")[0] == lt.t.area for i, lt in zip(ids, TEMPLATES, strict=True))


def test_effects_may_only_read_facts() -> None:
    bad = {
        "id": "work.bad",
        "area": "work",
        "emoji": "x",
        "title": "t",
        "text": "t",
        "concept_id": "inflation",
        "probability": 0.1,
        "facts": {"a": 1},
        "choices": [
            {"id": "a", "label": "A", "default": True, "text": "x", "good": True, "effects": {"cash": "income"}},
            {"id": "b", "label": "B", "text": "x", "good": False},
        ],
    }
    with pytest.raises(ValueError):
        Template.model_validate(bad)


def test_expr_is_safe() -> None:
    for src in ("__import__('os')", "a.b", "[1,2]", "lambda: 1", "open('x')"):
        with pytest.raises(ExprError):
            Expr.parse(src)
    assert Expr.parse("clamp(a / 0, -1, 1) + (2 if b > 1 else 3)").eval({"a": 5, "b": 2}) == 2.0
    assert Expr.parse("(1 + 0.004) ** -300").eval({}) == pytest.approx(1.004**-300)
