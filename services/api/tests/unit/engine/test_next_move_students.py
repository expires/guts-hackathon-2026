"""ADR 0070 point 7: every sample student gets an active top move; "no action needed" is only a runner-up;
student trade-offs never talk about investing unless the user invests. Pure, no network."""

from __future__ import annotations

import re
from datetime import date

import pytest

from lifeline_contracts.finance import Account, FinanceSnapshot
from lifeline_contracts.macro import MacroTable
from lifeline_contracts.next_move import Move
from lifeline_engine.money.text import unsupported_numbers
from lifeline_engine.next_move import invests, is_no_op, next_move

TODAY = date(2026, 10, 17)
INVEST_WORDS = re.compile(r"invest|shares|stock market|pension", re.IGNORECASE)


STUDENTS = ("scholarship", "scottish", "commuter", "loan_england", "working", "mature", "international",
                "final_year", "rich", "graduate")


def _samples() -> list[tuple[str, FinanceSnapshot]]:
    statements = pytest.importorskip("lifeline_data.statements")
    return [(sid, statements.load_sample(sid)) for sid in STUDENTS]


def _texts(m: Move) -> list[str]:
    assert m.trade_off is not None
    return [m.trade_off.summary, *(p.text for p in m.trade_off.points)]


def test_every_sample_has_an_active_top_move(macro: MacroTable) -> None:
    for sid, snap in _samples():
        r = next_move(snap, macro, TODAY)
        assert not is_no_op(r.top), (sid, r.top.action)
        assert r.top.kind != "keep_cash", sid
        assert r.top.confidence_level is not None, sid
        for m in r.runners_up:
            assert m.id != r.top.id


def test_student_trade_offs_have_no_investing_words(macro: MacroTable) -> None:
    for sid, snap in _samples():
        assert not invests(snap), sid
        r = next_move(snap, macro, TODAY)
        for m in [r.top, *r.runners_up]:
            for text in _texts(m):
                assert not INVEST_WORDS.search(text), (sid, m.kind, text)
            for p in m.trade_off.points if m.trade_off else []:
                assert unsupported_numbers(p.text, p.facts) == [], p.text


def test_on_track_plan_moves_spare_current_account_cash(macro: MacroTable) -> None:
    snap = dict(_samples())["scholarship"]
    top = next_move(snap, macro, TODAY).top
    assert top.kind == "weekly_budget" and top.shortfall == 0
    current = sum(a.balance for a in snap.accounts if a.kind == "current")
    spare = next(e.facts["spare"] for e in top.evidence if "spare" in e.facts)
    assert 0 < spare <= current
    assert top.action.startswith("Move ") and top.reason and "spare" in top.reason


def test_investor_keeps_investing_wording() -> None:
    snap = dict(_samples())["graduate"]
    with_isa = snap.model_copy(update={"accounts": [*snap.accounts, Account(
        id="ss", name="Stocks and Shares ISA", kind="isa", provider="V", balance=2000.0)]})
    assert invests(with_isa) and not invests(snap)
