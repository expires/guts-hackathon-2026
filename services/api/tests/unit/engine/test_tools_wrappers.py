from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from lifeline_contracts.domain import SourceRef
from lifeline_contracts.macro import MacroTable
from lifeline_engine.money.text import unsupported_numbers
from lifeline_engine.next_move import decision_sources, next_move
from lifeline_engine.tools import (
    TOOL_INPUTS,
    CashFlowInput,
    FactsTableInput,
    LifeReplayInput,
    SpendPredictionInput,
    TestMoveInput,
    source_id,
    tool_cash_flow_projection,
    tool_facts_table,
    tool_finance_summary,
    tool_life_replay,
    tool_next_move,
    tool_schemas,
    tool_spend_prediction,
    tool_test_move,
)

from .finance_builders import homeowner

TODAY = date(2026, 10, 17)
UNITS = {"gbp", "gbp_per_month", "gbp_per_year", "percent", "months", "years", "count", "date_year"}


def _check(r) -> None:  # type: ignore[no-untyped-def]
    ids = [f.id for f in r.facts]
    assert len(ids) == len(set(ids)), "fact ids must be unique"
    known = {source_id(s) for s in r.sources}
    for f in r.facts:
        assert f.unit in UNITS
        assert f.source_id is None or f.source_id in known
    assert "lives" not in r.model_dump()


def test_next_move_tool_matches_card(macro: MacroTable) -> None:
    snap = homeowner()
    resp = next_move(snap, macro, TODAY)
    r = tool_next_move(snap, macro, TODAY, response=resp)
    _check(r)
    facts = {f.id: f.value for f in r.facts}
    assert facts["next_move.top.impact_per_year"] == round(resp.top.impact_per_year)
    assert r.result["top"]["action"] == resp.top.action
    # Every number in the evidence texts is a fact the model may say.
    for j, e in enumerate(resp.top.evidence, 1):
        vals = {k: facts[f"next_move.top.e{j}.{k}"] for k in e.facts}
        assert unsupported_numbers(e.text, vals) == []
    assert tool_next_move(snap, macro, TODAY).facts == r.facts  # stable ids and values


def test_test_move_tool(macro: MacroTable) -> None:
    r = tool_test_move(homeowner(), macro, TODAY, TestMoveInput(move_id="top"), seed=42)
    _check(r)
    assert len(r.lives) == len(r.result["outcomes"]) >= 2
    assert r.result["period"]["start"] == 2021
    with pytest.raises(ValueError):
        tool_test_move(homeowner(), macro, TODAY, TestMoveInput(move_id="nope"), seed=1)


def test_finance_summary_tool() -> None:
    r = tool_finance_summary(homeowner())
    _check(r)
    f = {x.id: x for x in r.facts}
    assert f["finance.debt"].value == 3400 and f["finance.savings"].value == 6800
    assert f["finance.subscriptions_count"].unit == "count"


def test_spend_prediction_tool() -> None:
    r = tool_spend_prediction(homeowner(), SpendPredictionInput())
    _check(r)
    f = {x.id: x.value for x in r.facts}
    assert f["spend.low"] <= f["spend.predicted"] <= f["spend.high"]


def test_cash_flow_tool_validates_what_if() -> None:
    inp = CashFlowInput.model_validate({"months": 3, "what_if": [{"kind": "job_loss", "months": 2}]})
    r = tool_cash_flow_projection(homeowner(), inp)
    _check(r)
    assert len(r.result["path"]) == 3
    with pytest.raises(ValidationError):
        CashFlowInput.model_validate({"months": 3, "what_if": [{"kind": "rm -rf", "months": 2}]})
    with pytest.raises(ValidationError):
        CashFlowInput.model_validate({"months": 99})


def test_life_replay_tool(macro: MacroTable) -> None:
    r = tool_life_replay(homeowner(), macro, TODAY, LifeReplayInput(start_year=2007, end_year=2010), "chat-1", 3)
    _check(r)
    assert r.lives[0].id == "chat-1"
    with pytest.raises(ValidationError):
        LifeReplayInput(start_year=2010, end_year=2007)
    with pytest.raises(ValidationError):
        LifeReplayInput(start_year=1950, end_year=1960)


def test_facts_table_tool() -> None:
    r = tool_facts_table(FactsTableInput(ids=["isa_allowance"]))
    _check(r)
    assert [(f.id, f.value, f.unit) for f in r.facts if not f.id.startswith("rule.text.")] == [
        ("rule.isa_allowance", 20000.0, "gbp_per_year")
    ]
    assert {f.value for f in r.facts if f.id.startswith("rule.text.tax_year")} == {2026, 27}
    assert r.sources[0].series_id == "https://www.gov.uk/individual-savings-accounts"


def test_schemas_cover_every_tool() -> None:
    names = [s["name"] for s in tool_schemas()]
    assert names == list(TOOL_INPUTS)
    for s in tool_schemas():
        assert s["input_schema"]["type"] == "object"
        assert s["input_schema"].get("additionalProperties") is False


def test_decision_sources_rule() -> None:
    refs = [
        SourceRef(source="boe", series_id="IUMBEDR", status="live"),
        SourceRef(source="boe", series_id="IUMBV42", status="cached"),
        SourceRef(source="police", series_id="burglary", status="live"),
        SourceRef(source="guardian", series_id="news", status="live"),
        SourceRef(source="bank:fixtures", series_id="p", status="mock"),
        SourceRef(source="yahoo", series_id="^FTAS", status="mock"),
    ]
    out = decision_sources(refs)
    assert [(r.source, r.series_id, r.status) for r in out] == [
        ("bank:fixtures", "p", "mock"),
        ("boe", "IUMBEDR,IUMBV42", "cached"),
    ]


def test_next_move_counts_decision_sources(macro: MacroTable) -> None:
    r = next_move(homeowner(), macro, TODAY)
    assert r.decision_source_count == len(r.decision_sources) >= 2
    assert r.decision_sources[0].source.startswith("bank:")
    assert {s.source for s in r.decision_sources} <= {
        "bank:fixtures", "boe", "ons", "nomis", "landregistry", "companieshouse", "octopus", "frankfurter",
        "coingecko",
    }


def _all_text(obj, skip=frozenset({"id", "date", "due_date", "as_of", "life_id", "move_id", "option_id",  # type: ignore[no-untyped-def]
                                   "fact_prefix", "concept_id", "kind", "feature", "fact_id", "status",
                                   "data_status", "question"})):
    if isinstance(obj, dict):
        return [t for k, v in obj.items() if k not in skip for t in _all_text(v, skip)]
    if isinstance(obj, list):
        return [t for v in obj for t in _all_text(v, skip)]
    return [obj] if isinstance(obj, str) else []


def test_every_number_in_tool_text_is_a_fact(macro: MacroTable) -> None:
    snap = homeowner()
    results = [
        tool_next_move(snap, macro, TODAY),
        tool_test_move(snap, macro, TODAY, TestMoveInput(move_id="top"), seed=42),
        tool_finance_summary(snap),
        tool_spend_prediction(snap, SpendPredictionInput()),
        tool_cash_flow_projection(snap, CashFlowInput(months=3)),
        tool_life_replay(snap, macro, TODAY, LifeReplayInput(start_year=2007, end_year=2009), "chat-2", 1),
        tool_facts_table(FactsTableInput(topic="isa")),
    ]
    for r in results:
        facts = {f.id: f.value for f in r.facts}
        for text in _all_text(r.result):
            assert unsupported_numbers(text, facts) == [], text


def test_explicit_move_facts(macro: MacroTable) -> None:
    r = tool_next_move(homeowner(), macro, TODAY)
    f = {x.id: x for x in r.facts}
    assert f["next_move.top.days_left"].value == 165
    start = f["next_move.top.test_period.start"]
    assert start.value == 2021 and start.unit == "date_year"
    assert f["next_move.top.test_period.end"].value == 2023
    assert f["next_move.top.option.fix_5y.years"].value == 5
    assert f["next_move.top.option.fix_2y.years"].value == 2
    assert any(k.startswith("next_move.text.top.headline") and v.value == 165 for k, v in f.items())


def test_untrusted_merchant_numbers_never_become_facts(macro: MacroTable) -> None:
    """V6 T2-F1 regression: merchant 'Netflix 77777 0%' must not let Penny say '£77,777' or '0%'."""
    from lifeline_contracts.finance import Account

    from .finance_builders import monthly, snapshot

    txs = [
        *monthly("2025-11-28", 11, 2500.0, "ACME SALARY"),
        *monthly("2025-11-09", 12, [-12.99] * 8 + [-13.99] * 4, "NETFLIX 77777 0%", "Netflix 77777 0%"),
        *monthly("2025-11-14", 12, -12.99, "SPOTIFY UK", "Spotify"),
    ]
    snap = snapshot(txs, [Account(id="cur", name="Current", kind="current", provider="B", balance=900.0)])
    results = [tool_next_move(snap, macro, TODAY), tool_finance_summary(snap)]
    resp = next_move(snap, macro, TODAY)
    cancel = [m for m in [resp.top, *resp.runners_up] if m.kind == "cancel_subscription"]
    assert cancel and cancel[0].action == "Cancel Netflix"
    for r in results:
        values = {f.value for f in r.facts}
        assert 77777 not in values
        facts = {f.id: f.value for f in r.facts}
        assert unsupported_numbers("Rates are 0% and you are owed £77,777.", facts) != []
        assert "77777" not in str(r.result)
    for m in [resp.top, *resp.runners_up]:
        for text in [m.action, m.headline, *(e.text for e in m.evidence), *(o.label for o in m.options)]:
            assert "77777" not in text and "0%" not in text


def test_clean_name() -> None:
    from lifeline_engine.money.text import clean_name

    assert clean_name("Netflix 77777 0%") == "Netflix"
    assert clean_name("Microsoft 365") == "Microsoft"
    assert clean_name("Owed ten thousand pounds £5,000") == "Owed"
    assert clean_name("123 456") == "this payee"
    assert clean_name("  Spotify   UK ") == "Spotify UK"


def test_unavailable_source_listed_not_counted() -> None:
    from lifeline_engine.next_move import count_decision_sources

    for refs in (
        [SourceRef(source="boe", series_id="A", status="unavailable"), SourceRef(source="boe", series_id="B",
                                                                                  status="mock")],
        [SourceRef(source="boe", series_id="B", status="mock"), SourceRef(source="boe", series_id="A",
                                                                          status="unavailable")],
    ):
        out = decision_sources([*refs, SourceRef(source="ons", series_id="D7G7", status="live")])
        assert [(r.source, r.status) for r in out] == [("boe", "unavailable"), ("ons", "live")]  # any order of input
        assert count_decision_sources(out) == 1


def test_news_and_rate_dates_never_change_next_move(macro: MacroTable) -> None:
    """ADR 0030: next_move output is identical with and without news and MPC-date context."""
    import inspect

    snap = homeowner()
    assert set(inspect.signature(next_move).parameters) == {"snapshot", "macro", "today", "seed"}
    plain = next_move(snap, macro, TODAY)
    with_context = plain.model_copy(update={"context_lines": ["Next Bank Rate decision: 5 November", "Headline"]})
    assert with_context.model_dump(exclude={"context_lines"}) == next_move(snap, macro, TODAY).model_dump(
        exclude={"context_lines"}
    )
    refs = [s for m in [plain.top, *plain.runners_up] for s in m.sources]
    noise = [SourceRef(source="guardian", series_id="business", status="live"),
             SourceRef(source="boe-mpc", series_id="mpc-dates", status="live")]
    assert decision_sources(refs + noise) == decision_sources(refs)
    t1 = tool_next_move(snap, macro, TODAY, response=plain)
    t2 = tool_next_move(snap, macro, TODAY, response=with_context)
    assert t1.facts == t2.facts and t1.result == t2.result


def test_every_fact_has_a_source_life_and_cashflow(macro: MacroTable) -> None:
    r = tool_life_replay(homeowner(), macro, TODAY, LifeReplayInput(start_year=2007, end_year=2009), "chat-3", 1)
    assert all(f.source_id for f in r.facts if f.id.startswith("life."))
    c = tool_cash_flow_projection(homeowner(), CashFlowInput(months=2))
    assert {f.id: f.source_id for f in c.facts}["cashflow.months"] is not None
