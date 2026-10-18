"""Penny V3 (PENNY_V3_BUILD.md C5, D4, D6, ADR 0072). Fake LLM and fake tools, no network.

C5: general questions with general numbers (library opening hours) get a real answer labelled "General knowledge";
numbers about the user's money stay strictly checked. The onboarding chat never opens with a refusal.
"""

from __future__ import annotations

from typing import Any

from lifeline_contracts.chat import ChatContext, ChatRequest, ChatResponse
from lifeline_explain import i18n
from lifeline_explain.chat import MAX_BUBBLES, Penny
from lifeline_explain.chat_llm import LLMStep, WebResult
from lifeline_explain.chat_tools import ChatToolContext
from tests.unit.explain.test_chat import SETTINGS, FakeChatLLM, ask, call, check_invariants, final
from tests.unit.explain.test_chat_languages import no_data_tools

LIBRARY_Q = "How long does Edinburgh uni library stay open?"
LIBRARY_A = (
    "The Main Library at the University of Edinburgh is open 24 hours a day, 7 days a week during term time. "
    "Outside term it usually closes at 10pm."
)
ONBOARDING = ChatContext(screen="onboarding")
UNAVAILABLE = i18n.UNAVAILABLE["en"]


async def _onboarding(llm: FakeChatLLM, message: str = LIBRARY_Q, tools: Any = None) -> ChatResponse:
    req = ChatRequest(message=message, context=ONBOARDING)
    ctx = ChatToolContext(tools=tools or no_data_tools(), thread_id="t1", user_message_id="u1",
                          request_context=ONBOARDING)  # fmt: skip
    resp = await Penny(llm=llm, settings=SETTINGS).answer(req, ctx)
    check_invariants(resp)
    return resp


def _text(r: ChatResponse) -> str:
    return " ".join(b.text for b in r.bubbles)


# ---------- C5: general numbers ----------


async def test_library_hours_get_a_real_answer() -> None:
    r = await _onboarding(FakeChatLLM(final(LIBRARY_A)))
    assert r.verified and UNAVAILABLE not in _text(r)
    assert "24 hours" in _text(r) and "10pm" in _text(r)
    assert r.mode == "general" and r.bubbles[0].kind == "general_knowledge"


async def test_library_hours_after_a_tool_call_are_not_rejected() -> None:
    # The model looked in the facts table first (an app tool ran): the hours are still general numbers.
    llm = FakeChatLLM(call("facts_table"), final(LIBRARY_A))
    r = await _onboarding(llm)
    assert r.verified and "24 hours" in _text(r) and "ISA" not in _text(r)
    assert r.mode == "general" and r.bubbles[0].kind == "general_knowledge"
    assert len(llm.requests) == 2  # no rewrite round trip


async def test_library_hours_after_web_search() -> None:
    step = final(("general_knowledge", LIBRARY_A))
    step.web_searches = 1
    step.web_results = [WebResult(url="https://www.ed.ac.uk/information-services/library", title="Main Library",
                                  text="Open 24 hours in term time")]  # fmt: skip
    r = await _onboarding(FakeChatLLM(step))
    assert r.verified and "24 hours" in _text(r) and r.sources and r.sources[0].group == "general_knowledge"


async def test_library_hours_stream_a_bubble() -> None:
    req = ChatRequest(message=LIBRARY_Q, context=ONBOARDING)
    ctx = ChatToolContext(tools=no_data_tools(), request_context=ONBOARDING)
    penny = Penny(llm=FakeChatLLM(call("facts_table"), final(LIBRARY_A)), settings=SETTINGS)
    events = [e async for e in penny.answer_stream(req, ctx)]
    assert not [e for e in events if e.type == "error"]
    bubbles = [e.bubble.bubble for e in events if e.type == "bubble" and e.bubble is not None]
    assert bubbles and "24 hours" in bubbles[0].text and bubbles[0].kind == "general_knowledge"


async def test_checked_answer_keeps_general_hours_bubble() -> None:
    llm = FakeChatLLM(
        call("finance_summary"),
        final("You spend £1,840.50 a month.", ("general_knowledge", "Most uni libraries open 24 hours in exams.")),
    )
    r, _ = await ask("How much do I spend, and is the library open late?", llm)
    assert r.verified and r.mode == "checked" and len(r.bubbles) == 2
    assert r.bubbles[1].kind == "general_knowledge" and "24 hours" in r.bubbles[1].text
    assert any(s.label == "General knowledge" for s in r.sources)


async def test_wrong_personal_pound_amount_is_still_rejected() -> None:
    llm = FakeChatLLM(call("finance_summary"), final("You spend £2,500 a month."), final("You spend £2,400 a month."))
    r, _ = await ask("How much do I spend a month?", llm)
    assert not r.verified and "2,500" not in _text(r) and "2,400" not in _text(r)
    assert "not values of this turn's tool facts: 2,500" in llm.requests[2]["messages"][-1]["content"]


async def test_wrong_pound_amount_in_a_general_knowledge_bubble_is_rejected() -> None:
    bad = final(("general_knowledge", "Your spending is £2,500 a month."))
    llm = FakeChatLLM(call("finance_summary"), bad, bad)
    r, _ = await ask("How much do I spend a month?", llm)
    assert not r.verified and "2,500" not in _text(r)


async def test_general_figure_about_the_users_money_is_rejected() -> None:
    bad = final("That is 3 months of rent.")
    llm = FakeChatLLM(call("finance_summary"), bad, bad)
    r, _ = await ask("How long would my savings last?", llm)
    assert not r.verified and "3 months" not in _text(r)


# ---------- C5: no refusal opener in onboarding ----------


async def test_onboarding_drops_refusal_opener() -> None:
    llm = FakeChatLLM(final("I can't see your numbers yet. Most students budget week by week around their loan."))
    r = await _onboarding(llm, "How should I budget?")
    assert "can't see" not in _text(r).lower() and "budget week by week" in _text(r)
    first = llm.requests[0]["messages"][-1]["content"]
    assert "Never open with a refusal" in first


async def test_onboarding_refusal_only_is_retried() -> None:
    llm = FakeChatLLM(
        final("I don't have access to your bank data yet."),
        final("Start with your loan, take off rent, then split the rest by week."),
    )
    r = await _onboarding(llm, "How much can I spend?")
    assert "access" not in _text(r) and "split the rest by week" in _text(r)
    assert "Do not say you cannot see" in llm.requests[1]["messages"][-1]["content"]


async def test_onboarding_refusal_twice_still_answers() -> None:
    refusal = final("Sorry, I cannot see your account details.")
    r = await _onboarding(FakeChatLLM(refusal, refusal), "How much can I spend?")
    assert _text(r) == i18n.ONBOARDING_ANSWER["en"]


# ---------- D6: short answers ----------


def test_bubble_cap_matches_the_contract() -> None:
    from lifeline_contracts.chat import ChatResponse as Resp

    meta = Resp.model_fields["bubbles"].metadata
    max_len = next(m.max_length for m in meta if hasattr(m, "max_length"))
    assert max_len == MAX_BUBBLES


async def test_four_bubbles_are_cut_to_the_cap() -> None:
    llm = FakeChatLLM(final("Cook in batches.", "Use a Railcard.", "Buy own brand.", "Walk to campus."))
    r, _ = await ask("Tips?", llm)
    assert len(r.bubbles) == MAX_BUBBLES == 3


# ---------- B3.7, D4: forecast in Penny ----------


def _forecast_tools(stress_seen: list[int | None] | None = None) -> Any:
    from lifeline_data.macro import mock_macro_table
    from lifeline_explain.chat_engine_tools import EngineToolSet
    from tests.unit.engine.test_forecast import TODAY, run, snap

    s = snap()

    async def forecast(stress: int | None) -> Any:
        if stress_seen is not None:
            stress_seen.append(stress)
        return run(s, stress=stress)

    return EngineToolSet(s, mock_macro_table(), TODAY, forecast=forecast), run(s)


def test_forecast_facts_are_the_card_numbers() -> None:
    from lifeline_explain.forecast_tool import forecast_output

    _, fc = _forecast_tools()
    out = forecast_output(fc)
    facts = {f.id: f for f in out.facts}
    assert facts["forecast.per_week"].value == round(fc.per_week, 2) and facts["forecast.per_week"].unit == "gbp"
    assert facts["forecast.per_day"].value == round(fc.per_day, 2)
    assert facts["forecast.buffer_pct"].value == fc.buffer_pct and facts["forecast.buffer_pct"].unit == "percent"
    assert facts["forecast.days"].value == fc.days
    assert all(f.source_id for f in out.facts)


async def test_forecast_tool_is_offered_and_preloaded() -> None:
    seen: list[int | None] = []
    ts, _ = _forecast_tools(seen)
    assert "forecast" in {s.name for s in ts.specs()} and ts.preload == ("finance_summary", "forecast")
    out = await ts.call("forecast", {"stress_2022": True})
    assert seen == [2022] and any(f.id == "forecast.stress.per_week" for f in out.facts)


async def test_explain_my_weekly_budget_from_the_forecast_screen() -> None:
    ts, fc = _forecast_tools()
    answer = f"You can spend £{fc.per_week:,.2f} a week, about £{fc.per_day:,.2f} a day, until your next money."
    llm = FakeChatLLM(final(answer, f"That leaves a £{fc.buffer_amount:,.2f} buffer."))
    rc = ChatContext(screen="forecast", title="Weekly budget")
    req = ChatRequest(message="Explain my weekly budget", context=rc)
    r = await Penny(llm=llm, settings=SETTINGS).answer(req, ChatToolContext(tools=ts, request_context=rc))
    check_invariants(r)
    assert r.verified and r.mode == "checked" and 1 <= len(r.bubbles) <= MAX_BUBBLES
    assert len(llm.requests) == 1  # the forecast went with the question: no tool round trip
    first = llm.requests[0]["messages"][-1]["content"]
    assert "APP DATA" in first and '"forecast"' in first and "FORECAST SCREEN" in first
    assert "forecast" not in {t.get("name") for t in llm.requests[0]["tools"]}  # already loaded
    assert {h.fact_id for h in r.highlights} >= {"forecast.per_week", "forecast.per_day"}
    assert all(s.group == "your_data" for s in r.sources)
    assert r.links == ["maths"]  # D5: "See the maths"


async def test_wrong_weekly_figure_on_the_forecast_screen_is_rejected() -> None:
    ts, fc = _forecast_tools()
    bad = final("You can spend £999 a week.")
    rc = ChatContext(screen="forecast")
    r = await Penny(llm=FakeChatLLM(bad, bad), settings=SETTINGS).answer(
        ChatRequest(message="Explain my weekly budget", context=rc), ChatToolContext(tools=ts, request_context=rc)
    )
    assert not r.verified and "999" not in _text(r)


async def test_no_forecast_tool_without_user_data() -> None:
    ts = no_data_tools()
    assert "forecast" not in {s.name for s in ts.specs()}


# ---------- D4: lesson card ----------


async def test_lesson_question_focuses_on_the_quoted_card() -> None:
    from lifeline_explain import learn_scene
    from tests.unit.explain.test_learn_lesson_chat import LESSON_ID, SPEC

    heading, card = SPEC.cards[1]
    message = f'About this card: "{card}" Why does this matter?'
    scene = learn_scene.lesson_scene(LESSON_ID, message)
    assert scene is not None and scene.output.result["current_card"]["index"] == 1
    rc = ChatContext(screen="learn_lesson", lesson_id=LESSON_ID)
    llm = FakeChatLLM(final("It means every choice has a cost: what you give up."))
    ctx = ChatToolContext(tools=no_data_tools(), request_context=rc, scene=scene)
    r = await Penny(llm=llm, settings=SETTINGS).answer(ChatRequest(message=message, context=rc), ctx)
    assert r.verified
    first = llm.requests[0]["messages"][-1]["content"]
    assert "LESSON DATA" in first and "current_card" in first and heading in first


def test_card_index_wins_and_unknown_card_is_none() -> None:
    from lifeline_explain import learn_scene

    cards = [("One", "First card text here."), ("Two", "Second card text here.")]
    assert learn_scene.current_card(cards, "anything", card_index=0) == 0
    assert learn_scene.current_card(cards, "What is this?") is None
    assert learn_scene.current_card(cards, "second card text here. huh?") == 1


# ---------- forecast_what_if (BOSS item, ADR 0072) ----------


def _what_if_tools() -> Any:
    from lifeline_data.macro import mock_macro_table
    from lifeline_engine import forecast as fe
    from lifeline_explain.chat_engine_tools import EngineToolSet
    from tests.unit.engine.test_forecast import TODAY, run, snap

    s = snap()
    calls: list[Any] = []

    async def forecast(stress: int | None) -> Any:
        return run(s, stress=stress)

    async def what_if(changes: list[Any]) -> Any:
        calls.append(changes)
        return fe.what_if(s, TODAY, 10, 3.1, 10.5, 2.06, changes)

    ts = EngineToolSet(s, mock_macro_table(), TODAY, forecast=forecast, what_if=what_if)
    return ts, calls, run(s), lambda changes: fe.what_if(s, TODAY, 10, 3.1, 10.5, 2.06, changes)


def _answer_for(res: Any) -> LLMStep:
    from datetime import date as _date

    after = res.after
    if after.run_out_date:
        d = _date.fromisoformat(after.run_out_date)
        first = f"It gets tight: at this pace you run out on {d.day} {d.strftime('%B')}."
    else:
        first = f"Yes. After it you can spend £{after.per_week:,.2f} a week."
    diff = after.per_week - res.before.per_week
    second = f"That is £{abs(diff):,.2f} a week {'less' if diff < 0 else 'more'} than now."
    return final(first, second)


async def _ask_what_if(message: str, change: dict[str, Any], screen: str | None) -> tuple[ChatResponse, Any, Any]:
    from lifeline_contracts.forecast import WhatIfChange

    ts, calls, _, engine = _what_if_tools()
    res = engine([WhatIfChange.model_validate(change)])
    llm = FakeChatLLM(call("forecast_what_if", changes=[change]), _answer_for(res))
    rc = ChatContext(screen=screen) if screen else None  # type: ignore[arg-type]
    r = await Penny(llm=llm, settings=SETTINGS).answer(ChatRequest(message=message, context=rc),
                                                       ChatToolContext(tools=ts, request_context=rc))  # fmt: skip
    check_invariants(r)
    return r, calls, res


def _assert_engine_numbers(r: ChatResponse, calls: list[Any]) -> None:
    assert calls, "the what-if tool did not run"
    assert r.verified and r.mode == "checked"
    assert "forecast_what_if" in [c.name for c in r.tool_calls]
    used = {f.id for f in r.facts}
    assert used and all(i.startswith(("whatif.", "forecast.")) for i in used), used


async def test_what_if_concert_on_the_30th() -> None:
    change = {"kind": "one_off_cost", "amount": 60, "date": "2026-10-30", "label": "Concert ticket"}
    r, calls, res = await _ask_what_if("Can I afford a £60 concert on the 30th?", change, "forecast")
    _assert_engine_numbers(r, calls)
    assert res.after.per_week < res.before.per_week


async def test_what_if_loan_a_week_late() -> None:
    from datetime import date as _date
    from datetime import timedelta

    _, _, fc, _ = _what_if_tools()
    assert fc.next_money is not None
    late = (_date.fromisoformat(fc.next_money.date) + timedelta(days=7)).isoformat()
    change = {"kind": "move_payment", "target": fc.next_money.label, "date": late}
    r, calls, res = await _ask_what_if("What if my loan is a week late?", change, None)
    _assert_engine_numbers(r, calls)
    assert res.after.days > res.before.days


async def test_what_if_two_extra_shifts() -> None:
    change = {"kind": "extra_income", "amount": 2 * 48.0, "date": "2026-10-24", "label": "2 extra shifts"}
    r, calls, res = await _ask_what_if("What if I work 2 extra shifts?", change, None)
    _assert_engine_numbers(r, calls)
    assert res.after.per_week > res.before.per_week


async def test_what_if_wrong_number_is_rejected() -> None:
    ts, _, _, _ = _what_if_tools()
    change = {"kind": "one_off_cost", "amount": 60, "date": "2026-10-30"}
    bad = final("After it you can spend £5 a week.")
    r = await Penny(llm=FakeChatLLM(call("forecast_what_if", changes=[change]), bad, bad), settings=SETTINGS).answer(
        ChatRequest(message="Can I afford a £60 concert on the 30th?"), ChatToolContext(tools=ts)
    )
    assert not r.verified and "£5 a week" not in _text(r)


async def test_what_if_unclear_question_asks_once() -> None:
    ts, calls, _, _ = _what_if_tools()
    llm = FakeChatLLM(final(("question", "How much is the ticket, and which day is the concert?")))
    r = await Penny(llm=llm, settings=SETTINGS).answer(ChatRequest(message="Can I afford a concert?"),
                                                       ChatToolContext(tools=ts))  # fmt: skip
    assert r.verified and not calls and r.bubbles[0].kind == "question"
    assert "forecast_what_if" in {t.get("name") for t in llm.requests[0]["tools"]}
