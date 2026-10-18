"""Penny discusses the user's own Trading 212 allocation: tools, facts, filter and output checks. Offline."""

from __future__ import annotations

import asyncio
import re
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from lifeline_contracts.accounts import Holding
from lifeline_contracts.finance import Account, FinanceSnapshot
from lifeline_data.macro import mock_macro_table
from lifeline_data.returns import load_returns
from lifeline_engine import portfolio
from lifeline_explain.chat import gives_pick, out_of_scope_rule
from lifeline_explain.chat_engine_tools import EngineToolSet
from lifeline_explain.verifier import verify

TODAY = date(2026, 10, 17)


def hold(name: str, value: float, cls: str = "equity", region: str | None = "US") -> Holding:
    return Holding(instrument_id=name, name=name, quantity=1, value=value, asset_class=cls, region=region)  # type: ignore[arg-type]


HOLDINGS = [
    hold("Apple", 410.0),
    hold("Vanguard FTSE Global", 300.0, region="Global"),
    hold("UK Gilt", 200.0, "bond", "UK"),
    hold("Cash pot", 90.0, "cash", "UK"),
]


def snap(holdings: list[Holding]) -> FinanceSnapshot:
    return FinanceSnapshot(
        status="live", source="trading212", as_of="2026-10-17",
        accounts=[Account(id="t1", name="Trading 212", kind="isa", provider="trading212", balance=1000.0)],
        transactions=[], holdings=holdings,
    )  # fmt: skip


def toolset(holdings: list[Holding], with_returns: bool = True) -> EngineToolSet:
    return EngineToolSet(snap(holdings), mock_macro_table(), TODAY, returns=load_returns() if with_returns else None)


def run(ts: EngineToolSet, name: str) -> Any:
    return asyncio.run(ts.call(name, {}))


def test_offered_only_with_holdings() -> None:
    names = {s.name for s in toolset(HOLDINGS).specs()}
    assert {"my_investments", "mix_history"} <= names
    bare = {s.name for s in toolset([]).specs()}
    assert not ({"my_investments", "mix_history"} & bare)


def test_my_investments_facts_and_note() -> None:
    out = run(toolset(HOLDINGS), "my_investments")
    f = {x.id: x.value for x in out.facts}
    assert f["invest.total"] == 1000.0 and f["invest.count"] == 4
    assert f["invest.top1_pct"] == 41.0 and f["invest.top3_pct"] == 91.0
    assert f["invest.h1.value"] == 410.0 and f["invest.h1.pct"] == 41.0
    assert f["invest.class.equity"] == 71.0 and f["invest.class.bond"] == 20.0
    assert out.result["concentration"].startswith("Your biggest holding is 41% of your investments")
    assert out.sources[0].source == "trading212"
    desc = "Your biggest holding is 41% of your investments and your top 3 make up 91%. Shares are 71% of the total."
    assert verify(desc, f).ok
    assert not verify("Your biggest holding is 55% of your investments.", f).ok


def test_mix_history_labelled_and_checked() -> None:
    out = run(toolset(HOLDINGS), "mix_history")
    assert out.result["label"] == "Illustrative past returns, not a forecast"
    periods = {r["period"] for r in out.result["results"]}
    assert len(periods) == 3
    ids = {x.id for x in out.facts}
    assert "mixhist.gfc_2008.yours.drop" in ids and "mixhist.gfc_2008.all_shares.drop" in ids
    shares = {x.id: x.value for x in out.facts}
    # More bonds, smaller fall: 60/40 never falls further than all shares in the same window.
    for p in portfolio.PERIODS:
        assert shares[f"mixhist.{p}.shares_60_bonds_40.drop"] <= shares[f"mixhist.{p}.all_shares.drop"]


def test_mix_history_pure_helpers() -> None:
    assert portfolio.drop_and_recovery([100, 90, 80, 100, 120]) == (20.0, 1)
    assert portfolio.drop_and_recovery([100, 90, 80]) == (20.0, None)
    assert portfolio.mix_history([], load_returns()) == ()
    assert portfolio.describe([]) is None


ALLOW = [
    "how is my portfolio split", "what am I invested in", "am I diversified", "is my portfolio risky",
    "talk me through my allocation", "how would my mix have done in 2008", "what does my stock allocation look like",
    "what stocks do I hold", "what are my biggest holdings", "is my portfolio too concentrated in equities",
]  # fmt: skip
DENY = [
    "should I buy NVDA", "which stock should I buy", "best fund to invest in", "should I sell Tesla",
    "what crypto should I get", "how much should I put in Tesla", "should I transfer my pension",
    "help with my tax return", "what should I invest in", "should I buy more of my biggest holding",
    "how much should I put into shares",
]  # fmt: skip


@pytest.mark.parametrize("msg", ALLOW)
def test_own_portfolio_questions_pass(msg: str) -> None:
    assert not out_of_scope_rule(msg)


@pytest.mark.parametrize("msg", DENY)
def test_picks_and_advice_still_refused(msg: str) -> None:
    assert out_of_scope_rule(msg)


@pytest.mark.parametrize(
    "text",
    [
        "You should hold 60% bonds and 40% shares.",
        "I would suggest moving to a 70% shares mix.",
        "Buy Vanguard FTSE Global with the rest of your cash.",
        "Sell your Tesla and keep the cash.",
        "Aim to hold 20% in bonds.",
    ],
)
def test_output_blocks_prescriptions(text: str) -> None:
    assert gives_pick(text)


@pytest.mark.parametrize(
    "text",
    [
        "Your biggest holding is 41% of your investments. Your top 3 holdings make up 91%.",
        "Shares are 71% of your mix and bonds 20%. Illustrative past returns, not a forecast.",
        "In 2008 a mix like yours fell 30% and took 40 months to recover.",
    ],
)
def test_output_allows_descriptions(text: str) -> None:
    assert not gives_pick(text)


def test_no_amounts_reach_friends_or_circles() -> None:
    root = Path(__file__).resolve().parents[3]
    for rel in ("lifeline_api/routes/circles.py",):
        assert not re.search(r"holdings|my_investments|invest\.", (root / rel).read_text())
