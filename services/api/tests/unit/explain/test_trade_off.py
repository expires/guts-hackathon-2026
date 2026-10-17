"""Ask Penny quotes a move's trade-off (ADR 0042), and the AI disclosure text (ADR 0043). No network."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from lifeline_contracts.chat import ChatRequest
from lifeline_contracts.domain import SourceRef
from lifeline_contracts.next_move import EvidencePoint, Move, MoveOption, TradeOff
from lifeline_explain import prompts
from lifeline_explain.chat import Penny
from lifeline_explain.chat_llm import LLMStep
from lifeline_explain.chat_tools import ChatToolContext, FunctionTool, FunctionToolSet, ToolOutput
from lifeline_explain.disclosure import ai_disclosure
from lifeline_explain.trade_off import attach_trade_offs, find_trade_offs, trade_off_facts
from tests.unit.explain.test_chat import (
    BOE,
    SETTINGS,
    FakeChatLLM,
    NoArgs,
    ask,
    call,
    check_invariants,
    f,
    final,
)

LENDER = SourceRef(source="bank:demo", series_id="mortgage", status="mock", note="Sample data")

TRADE_OFF = TradeOff(
    summary="Less flexibility: a fee if you leave early",
    points=[
        EvidencePoint(
            text="Leaving before 2031 costs an early repayment charge of £3,150, 3% of the loan.",
            facts={"erc": 3150, "erc_pct": 3, "fixed_until": 2031},
            source=LENDER,
        ),
        EvidencePoint(
            text="If rates fall, you keep paying 4.6% for 5 years.",
            facts={"fixed_rate": 4.6, "fix_years": 5},
        ),
    ],
)


def make_move(move_id: str = "fix_mortgage", trade_off: TradeOff | None = TRADE_OFF) -> Move:
    ev = [EvidencePoint(text=f"Evidence {i}.", facts={}) for i in ("one", "two", "three")]
    return Move(
        id=move_id,
        kind="fix_mortgage",
        action="Fix for 5 years",
        headline="Your deal ends soon",
        impact_per_year=1240,
        worst_case_per_year=-300,
        confidence=0.7,
        confidence_label="7 in 10 twins did better",
        evidence=ev,
        sources=[BOE],
        options=[MoveOption(id="fix_5y", label="Fix for 5 years", is_recommended=True)],
        testable=False,
        trade_off=trade_off,
    )


def next_move_with_trade_off(_: NoArgs) -> ToolOutput:
    """Engine result shape with the move's trade_off in it (contract model dump)."""
    mv = make_move()
    result: dict[str, Any] = {"top": {"id": mv.id, "action": mv.action, "headline": mv.headline}, "runners_up": []}
    attach_trade_offs(result, {mv.id: mv})
    return ToolOutput(
        result=result,
        facts=[
            f("next_move.top.impact_per_year", 1240, "gbp_per_year", "Expected gain a year", BOE),
            f("next_move.text.top.action.n1", 5, "years", "Number in top action", BOE),
        ],
        sources=[BOE],
    )


def tools() -> FunctionToolSet:
    return FunctionToolSet([FunctionTool("next_move", "Next move", NoArgs, next_move_with_trade_off)])


# ---------- unit ----------


def test_trade_off_facts_ids_and_units() -> None:
    facts = {x.id: x for x in trade_off_facts("fix_mortgage", TRADE_OFF)}
    assert set(facts) == {
        "tf_fix_mortgage_erc",
        "tf_fix_mortgage_erc_pct",
        "tf_fix_mortgage_fixed_until",
        "tf_fix_mortgage_fixed_rate",
        "tf_fix_mortgage_fix_years",
    }
    assert facts["tf_fix_mortgage_erc"].unit == "gbp" and facts["tf_fix_mortgage_erc"].value == 3150
    assert facts["tf_fix_mortgage_erc"].source_id == "bank:demo:mortgage"
    assert facts["tf_fix_mortgage_erc_pct"].unit == "percent"
    assert facts["tf_fix_mortgage_fixed_until"].unit == "date_year"
    assert facts["tf_fix_mortgage_fixed_rate"].unit == "percent"
    assert facts["tf_fix_mortgage_fix_years"].unit == "years"


def test_find_trade_offs_in_next_move_and_test_move_results() -> None:
    mv = make_move()
    nm = attach_trade_offs({"top": {"id": mv.id}, "runners_up": [{"id": "other"}]}, {mv.id: mv})
    assert nm["top"]["trade_off"]["summary"] == TRADE_OFF.summary and "trade_off" not in nm["runners_up"][0]
    tm = attach_trade_offs({"move_id": mv.id, "outcomes": []}, {mv.id: mv})
    assert [m for m, _ in find_trade_offs(nm)] == ["fix_mortgage"]
    assert [m for m, _ in find_trade_offs(tm)] == ["fix_mortgage"]
    # A move without a trade-off, or an invalid one, adds nothing.
    assert find_trade_offs(attach_trade_offs({"top": {"id": "x"}}, {"x": make_move("x", None)})) == []
    assert find_trade_offs({"top": {"id": "x", "trade_off": {"summary": "s", "points": []}}}) == []


def test_prompt_v4_states_trade_off() -> None:
    assert prompts.PENNY_PROMPT_VERSION == "penny-v4"
    assert prompts.PENNY_SYSTEM.startswith("[penny-v4]")
    assert '"What you give up:"' in prompts.PENNY_SYSTEM
    assert "do not make one up" in prompts.PENNY_SYSTEM


# ---------- verifier through Penny ----------


async def test_answer_quoting_trade_off_numbers_passes() -> None:
    llm = FakeChatLLM(
        call("next_move"),
        final(
            "Fix for 5 years. It is worth £1,240 a year.",
            "What you give up: leaving before 2031 costs £3,150, which is 3% of the loan. "
            "If rates fall, you still pay 4.6%.",
            reaction="brain",
        ),
    )
    r, _ = await ask("What's my next move?", llm, tools=tools())
    assert r.verified and r.reaction == "brain"
    used = {h.fact_id for h in r.highlights}
    assert {"tf_fix_mortgage_erc", "tf_fix_mortgage_erc_pct", "tf_fix_mortgage_fixed_rate"} <= used
    assert "tf_fix_mortgage_fixed_until" in used
    # The trade-off reached the model inside the tool result, with its facts.
    payload = json.loads(llm.requests[1]["messages"][-1]["content"][0]["content"])
    assert "trade_off" in payload["result"]["top"]
    assert any(x["id"] == "tf_fix_mortgage_erc" for x in payload["facts"])


async def test_invented_trade_off_number_fails() -> None:
    bad = final("Fix for 5 years. What you give up: leaving early costs £4,000.", reaction="brain")
    llm = FakeChatLLM(call("next_move"), bad, bad)
    r, _ = await ask("What's my next move?", llm, tools=tools())
    assert not r.verified and r.reaction == "question"
    assert all("4,000" not in b.text for b in r.bubbles)
    assert "4,000" in llm.requests[-1]["messages"][-1]["content"]  # the rewrite request named it


async def test_engine_toolset_attaches_trade_off_from_response() -> None:
    from datetime import date

    from lifeline_data.macro import mock_macro_table
    from lifeline_engine.next_move import next_move
    from lifeline_explain.chat_engine_tools import EngineToolSet
    from tests.unit.engine.finance_builders import homeowner

    snap, macro, today = homeowner(), mock_macro_table(), date(2026, 10, 17)
    resp = next_move(snap, macro, today, 0)
    resp = resp.model_copy(update={"top": resp.top.model_copy(update={"trade_off": TRADE_OFF})})
    ts = EngineToolSet(snap, macro, today, next_move_response=resp)

    def answer(messages: list[dict[str, Any]]) -> LLMStep:
        payload = json.loads(messages[-1]["content"][0]["content"])
        erc = next(x for x in payload["facts"] if x["id"] == f"tf_{resp.top.id}_erc")["value"]
        return final(f"What you give up: leaving early costs £{erc:,.0f}.", reaction="brain")

    llm = FakeChatLLM(call("next_move"), answer)
    r = await Penny(llm=llm, settings=SETTINGS).answer(ChatRequest(message="Next move?"), ChatToolContext(tools=ts))
    check_invariants(r)
    assert r.verified
    assert any(h.fact_id == f"tf_{resp.top.id}_erc" for h in r.highlights)


# ---------- AI disclosure (ADR 0043) ----------

DOC = Path(__file__).resolve().parents[5] / "docs" / "RESPONSIBLE_AI.md"


def _doc_sections(md: str, title: str) -> list[dict[str, Any]]:
    body = md.split(f"\n## {title}\n", 1)[1]
    body = re.split(r"\n## ", body, maxsplit=1)[0]
    sections: list[dict[str, Any]] = []
    for line in body.splitlines():
        if line.startswith("### "):
            sections.append({"heading": line[4:].strip(), "points": []})
        elif line.startswith("- ") and sections:
            sections[-1]["points"].append(line[2:].strip())
    return sections


def test_disclosure_json_shape_and_style() -> None:
    d = ai_disclosure()
    assert d["title"] == "How Penny uses AI"
    assert [s["heading"] for s in d["sections"]] == [
        "Where AI is used",
        "What stays deterministic",
        "How output is checked",
        "What happens when AI fails",
    ]
    for s in d["sections"]:
        assert s["points"] and all(isinstance(p, str) and p for p in s["points"])
        assert all("—" not in p and "–" not in p for p in s["points"])  # no em or en dashes


def test_disclosure_doc_matches_json() -> None:
    if not DOC.exists():  # e.g. inside the API container, which has no docs/
        import pytest

        pytest.skip("docs/RESPONSIBLE_AI.md not present")
    d = ai_disclosure()
    assert _doc_sections(DOC.read_text(encoding="utf-8"), d["title"]) == d["sections"]


def test_disclosure_names_real_test_files() -> None:
    api_root = Path(__file__).resolve().parents[3]
    text = " ".join(p for s in ai_disclosure()["sections"] for p in s["points"])
    for path in re.findall(r"services/api/([\w/]+\.py)", text):
        assert (api_root / path).exists(), path
