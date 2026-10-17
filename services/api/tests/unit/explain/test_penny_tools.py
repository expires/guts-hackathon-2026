"""ADR 0060: Penny's full toolset, never asking for public facts, real step labels, chips that match the question."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from lifeline_contracts.chat import ChatRequest
from lifeline_explain import prompts
from lifeline_explain.chat import Penny
from lifeline_explain.chat_llm import LLMStep, ToolUse
from lifeline_explain.chat_tools import ChatToolContext, ToolInputError
from tests.unit.explain.test_chat import SETTINGS, FakeChatLLM, ask, call, check_invariants, final

RATE_DAY = date(2026, 10, 16)


async def fake_fx(base: str, quote: str) -> tuple[float, date] | None:
    return (0.104123, RATE_DAY) if (base, quote) == ("CNY", "GBP") else None


async def fake_cpi() -> tuple[float, date] | None:
    return 3.8, date(2026, 9, 1)


def tools() -> Any:
    from lifeline_data.macro import mock_macro_table
    from lifeline_explain.chat_engine_tools import EngineToolSet
    from tests.unit.engine.finance_builders import homeowner

    return EngineToolSet(homeowner(), mock_macro_table(), date(2026, 10, 17), fx=fake_fx, cpi=fake_cpi)


def results(messages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Facts by id from the tool results in the last user message."""
    facts: dict[str, dict[str, Any]] = {}
    for block in messages[-1]["content"]:
        if isinstance(block, dict) and block.get("type") == "tool_result" and not block.get("is_error"):
            for x in json.loads(block["content"])["facts"]:
                facts[x["id"]] = x
    return facts


FX_CALL = LLMStep(
    stop_reason="tool_use",
    tool_uses=[
        ToolUse(id="fx1", name="fx_convert", input={"amount": 1000000, "from_currency": "CNY"}),
        ToolUse(id="bal1", name="user_balance", input={}),
    ],
)


def holiday_answer(messages: list[dict[str, Any]]) -> LLMStep:
    f = results(messages)
    gbp, rate, bal = f["fx.converted"]["value"], f["fx.rate"]["value"], f["finance.balance"]["value"]
    return final(
        f"1,000,000 yuan is about £{gbp:,.0f} at a rate of {rate} per yuan (ECB rate, 16 October 2026).",
        f"You have £{bal:,.0f} in cash, so this holiday is out of reach for now.",
        reaction="brain",
    )


# ---------- red team: never ask for the rate ----------


async def test_holiday_in_yuan_converts_states_rate_and_checks_money() -> None:
    llm = FakeChatLLM(FX_CALL, holiday_answer)
    ev = [
        e
        async for e in Penny(llm=llm, settings=SETTINGS).answer_stream(
            ChatRequest(message="Can I afford a holiday that costs 1 million yuan?"), ChatToolContext(tools=tools())
        )
    ]
    r = ev[-1].response
    check_invariants(r)
    assert r.mode == "checked" and r.verified
    assert {"fx_convert", "user_balance"} <= {c.name for c in r.tool_calls}
    assert "?" not in " ".join(b.text for b in r.bubbles)  # never asks the user for the rate
    assert {"fx.converted", "finance.balance"} <= {h.fact_id for h in r.highlights}
    labels = [e.step.label for e in ev if e.type == "tool_step"]
    assert "Checking exchange rates…" in labels and "Checking your balance…" in labels
    src = next(s for s in r.sources if s.ref and s.ref.source == "frankfurter")
    assert "CNY" not in src.label and src.label.startswith("Exchange rates (ECB)")


async def test_asking_the_user_for_a_rate_is_blocked_and_looked_up() -> None:
    llm = FakeChatLLM(final("What is the exchange rate for yuan to pounds right now?"), FX_CALL, holiday_answer)
    r = await Penny(llm=llm, settings=SETTINGS).answer(
        ChatRequest(message="Can I afford a holiday that costs 1 million yuan?"), ChatToolContext(tools=tools())
    )
    assert "You asked the user for something you can look up" in llm.requests[1]["messages"][-1]["content"]
    assert r.verified and r.mode == "checked" and "fx_convert" in {c.name for c in r.tool_calls}


def test_prompt_never_asks_for_public_facts() -> None:
    assert "Never ask the user for a rate, a conversion, the date of a public event or any public fact" in (
        prompts.PENNY_SYSTEM
    )
    assert "Ask only for what only the user knows" in prompts.PENNY_SYSTEM


async def test_asking_about_the_users_own_plans_is_fine() -> None:
    r, _ = await ask("Help me plan a trip", FakeChatLLM(final(("question", "When do you want to travel?"))))
    assert r.verified and r.bubbles[0].kind == "question"


# ---------- each tool ----------


async def test_engine_toolset_offers_every_tool() -> None:
    ts = tools()
    names = {s.name for s in ts.specs()}
    assert {"next_move", "test_move", "finance_summary", "user_balance", "cash_flow_projection", "spend_prediction",
            "habit_score", "facts_table", "fx_convert", "inflation"} <= names  # fmt: skip


async def test_fx_inflation_balance_habits_facts() -> None:
    ts = tools()
    fx = await ts.call("fx_convert", {"amount": 1000000, "from_currency": "cny"})
    by = {f.id: f for f in fx.facts}
    assert by["fx.rate"].value == 0.104123 and by["fx.converted"].value == 104123.0
    assert by["fx.converted"].unit == "gbp" and by["fx.rate"].label.endswith("16 October 2026")
    cpi = await ts.call("inflation", {})
    assert cpi.facts[0].id == "ons.cpi" and cpi.facts[0].label == "CPI inflation, September 2026"
    bal = await ts.call("user_balance", {})
    assert {f.id for f in bal.facts} == {"finance.balance", "finance.net_worth"}
    habits = await ts.call("habit_score", {})
    assert habits.facts and all(f.id.startswith("habit.") and 0 <= f.value <= 100 for f in habits.facts)
    assert ts.step_label("fx_convert", {}) == "Checking exchange rates…"
    assert ts.step_label("inflation", {}) == "Checking inflation…"


async def test_fx_unavailable_and_bad_currency() -> None:
    ts = tools()
    out = await ts.call("fx_convert", {"amount": 10, "from_currency": "USD"})
    assert out.facts == [] and out.result["status"] == "unavailable"
    try:
        await ts.call("fx_convert", {"amount": 10, "from_currency": "XXX"})
    except ToolInputError:
        pass
    else:
        raise AssertionError("unsupported currency accepted")


# ---------- chips match the question ----------


async def test_chips_only_with_a_question() -> None:
    step = final("You spend £1,840.50 a month.")
    payload = json.loads(step.text)
    payload["suggestions"] = ["Next move", "Summary"]
    step.text = json.dumps(payload)
    r, _ = await ask("Spend?", FakeChatLLM(call("finance_summary"), step))
    assert r.suggestions == []

    q = final("You spend £1,840.50 a month.", ("question", "Shall I add a food budget to your plan?"))
    payload = json.loads(q.text)
    payload["suggestions"] = ["Yes", "Yes, add it", "No, skip it"]
    q.text = json.dumps(payload)
    r2, _ = await ask("Spend?", FakeChatLLM(call("finance_summary"), q))
    assert r2.suggestions == ["Add it", "Skip it"]  # chips name the action


# ---------- links and chips that work for this user ----------


async def test_no_test_it_when_the_move_is_not_testable() -> None:
    from lifeline_explain.chat_tools import FunctionTool, FunctionToolSet, ToolOutput
    from tests.unit.explain.test_chat import BANK, NoArgs, f

    def untestable(_: NoArgs) -> ToolOutput:
        return ToolOutput(
            result={"top": {"id": "build_fund", "action": "Build a safety fund", "testable": False}},
            facts=[f("next_move.top.impact_per_year", 120, "gbp_per_year", "Expected gain a year", BANK)],
            sources=[BANK],
        )

    ts = FunctionToolSet([FunctionTool("next_move", "Next move", NoArgs, untestable)])
    step = final("Build a safety fund: it is worth £120 a year.", ("question", "Want to see how?"))
    payload = json.loads(step.text)
    payload["suggestions"] = ["Test it", "Show me how"]
    step.text = json.dumps(payload)
    r, _ = await ask("What's my next move?", FakeChatLLM(call("next_move"), step), tools=ts)
    assert r.verified and "test_it" not in r.links and r.suggestions == ["Show me how"]


async def test_general_lifetime_isa_answer_has_no_test_it() -> None:
    r, _ = await ask("What is a Lifetime ISA?", FakeChatLLM(final("A Lifetime ISA helps you save for a first home.")))
    assert "test_it" not in r.links and not any("test" in x.lower() for x in r.suggestions)


async def test_engine_lifetime_isa_question_quoting_rules_has_no_test_it() -> None:
    ts = tools()

    def answer(messages: list[dict[str, Any]]) -> LLMStep:
        content = messages[-1]["content"]
        data, _ = json.JSONDecoder().raw_decode(content[content.index("APP DATA") :].split(": ", 1)[1])
        fact = next(x for x in data["facts_table"]["facts"] if x["id"] == "rule.lisa_bonus_rate")
        return final(f"A Lifetime ISA adds a {fact['value']:g}% government bonus to what you pay in.")

    llm = FakeChatLLM(answer)
    r = await Penny(llm=llm, settings=SETTINGS).answer(
        ChatRequest(message="What is a Lifetime ISA?"), ChatToolContext(tools=ts)
    )
    assert r.verified and "test_it" not in r.links
    # V4 F3-1: only the official source behind the number, so the app shows "Checked against official sources".
    assert r.sources and {x.group for x in r.sources} == {"general_knowledge"}
    assert all(x.url and x.url.startswith("https://www.gov.uk/") for x in r.sources)
    assert {c.name for c in r.tool_calls} == {"facts_table"}


# ---------- V6 S5-F1: the conversion states its rate and date ----------


def no_rate_answer(messages: list[dict[str, Any]]) -> LLMStep:
    f = results(messages) if any(isinstance(b, dict) for b in messages[-1]["content"]) else {}
    gbp = f.get("fx.converted", {}).get("value", 104123.0)
    return final(f"1,000,000 yuan is about £{gbp:,.0f}, which is more than you have.", reaction="brain")


async def test_conversion_without_rate_is_rewritten_once() -> None:
    seen: list[dict[str, Any]] = []

    def remember(messages: list[dict[str, Any]]) -> LLMStep:
        seen.append(messages[-1])
        return no_rate_answer(messages)

    def fixed(_: list[dict[str, Any]]) -> LLMStep:
        return holiday_answer([seen[0]])

    llm = FakeChatLLM(FX_CALL, remember, fixed)
    r = await Penny(llm=llm, settings=SETTINGS).answer(
        ChatRequest(message="Can I afford a holiday that costs 1 million yuan?"), ChatToolContext(tools=tools())
    )
    assert "does not state the rate, the rate date" in llm.requests[2]["messages"][-1]["content"]
    assert r.verified and "0.104123" in r.bubbles[0].text


async def test_conversion_without_rate_twice_gets_the_fixed_rate_line() -> None:
    first: dict[str, Any] = {}

    def remember(messages: list[dict[str, Any]]) -> LLMStep:
        first.update(results(messages))
        return no_rate_answer(messages)

    def again(_: list[dict[str, Any]]) -> LLMStep:
        return final(f"1,000,000 yuan is about £{first['fx.converted']['value']:,.0f}.", reaction="brain")

    llm = FakeChatLLM(FX_CALL, remember, again)
    ev = [
        e
        async for e in Penny(llm=llm, settings=SETTINGS).answer_stream(
            ChatRequest(message="Can I afford a holiday that costs 1 million yuan?"), ChatToolContext(tools=tools())
        )
    ]
    r = ev[-1].response
    check_invariants(r)
    assert r.verified and r.bubbles[-1].text == "Rate: 1 CNY = £0.104123 (ECB, 16 Oct 2026)."
    assert [e.bubble.bubble.text for e in ev if e.type == "bubble"][-1] == r.bubbles[-1].text  # passes the stream check


def test_generic_tracker_fund_advice_is_not_a_pick() -> None:
    from lifeline_explain.chat import gives_pick

    assert not gives_pick("Pick a cheap tracker fund inside a stocks and shares ISA if you invest at all.")
    assert not gives_pick("If you invest, a low-cost index fund is a common choice.")
    assert gives_pick("Pick the Vanguard FTSE Global All Cap fund.")
    assert gives_pick("Buy Tesla shares now.")
    assert gives_pick("You could buy NVDA.")


# ---------- V4 advisories: whole percentages, action chips ----------


def test_whole_percentages_have_no_trailing_zero() -> None:
    from lifeline_explain.chat import clean_bubble, tidy_numbers

    assert clean_bubble("The bonus is 25.0% and the rate is 4.5%.") == "The bonus is 25% and the rate is 4.5%."
    assert tidy_numbers("Repay 9.00 per cent above the threshold") == "Repay 9 per cent above the threshold"
    assert tidy_numbers("Version 1.0 costs £10.0") == "Version 1.0 costs £10.0"  # only percentages change


async def test_percentage_fact_is_sent_and_highlighted_without_trailing_zero() -> None:
    from lifeline_explain.chat_tools import FunctionTool, FunctionToolSet, ToolOutput
    from tests.unit.explain.test_chat import BANK, NoArgs, f

    def rule(_: NoArgs) -> ToolOutput:
        return ToolOutput(result={}, facts=[f("rule.lisa_bonus_rate", 25.0, "percent", "LISA bonus 25.0%", BANK)],
                          sources=[BANK])  # fmt: skip

    ts = FunctionToolSet([FunctionTool("facts_table", "Rules", NoArgs, rule)])
    llm = FakeChatLLM(call("facts_table"), final("The government adds a 25.0% bonus."))
    r, _ = await ask("What is a Lifetime ISA?", llm, tools=ts)
    sent = json.loads(llm.requests[1]["messages"][-1]["content"][0]["content"])["facts"][0]
    assert sent["value"] == 25 and "25.0" not in sent["label"]
    assert r.bubbles[0].text == "The government adds a 25% bonus."
    h = r.highlights[0]
    assert r.bubbles[0].text[h.start : h.start + h.length] == "25%"


def test_chips_name_the_action() -> None:
    from lifeline_explain.chat import clean_suggestions

    assert clean_suggestions(["Yes, show me how", "No, I'm fine for now"]) == ["Show me how", "I'm fine for now"]
    assert clean_suggestions(["Yes", "No"]) == []
