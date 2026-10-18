"""ADR 0063: Penny answers in the chosen language; numbers stay Western digits with £ and %. Fake LLM."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from lifeline_contracts.chat import ChatRequest
from lifeline_explain import i18n, prompts
from lifeline_explain.chat import Penny
from lifeline_explain.chat_tools import ChatToolContext
from tests.unit.explain.test_chat import SETTINGS, FakeChatLLM, call, check_invariants, final, make_tools

PERSONAL: dict[str, str] = {
    "en": "You spend £1,840.50 a month.",
    "fr": "Vous dépensez £1,840.50 par mois.",
    "es": "Gastas £1,840.50 al mes.",
    "pt": "Você gasta £1,840.50 por mês.",
    "it": "Spendi £1,840.50 al mese.",
    "zh-Hans": "你每月花费 £1,840.50。",
    "hi": "आप हर महीने £1,840.50 ख़र्च करते हैं।",
    "ne": "तपाईं हरेक महिना £1,840.50 खर्च गर्नुहुन्छ।",
}
GENERAL: dict[str, str] = {
    "en": "A budget is a plan for your money.",
    "fr": "Un budget est un plan pour votre argent.",
    "es": "Un presupuesto es un plan para tu dinero.",
    "pt": "Um orçamento é um plano para o seu dinheiro.",
    "it": "Un budget è un piano per i tuoi soldi.",
    "zh-Hans": "预算就是你的用钱计划。",
    "hi": "बजट आपके पैसों की योजना है।",
    "ne": "बजेट तपाईंको पैसाको योजना हो।",
}
DISTRESS_IN: dict[str, str] = {
    "en": "I want to end it all",
    "fr": "J'ai envie de mourir",
    "es": "Quiero morir",
    "pt": "Quero morrer",
    "it": "Voglio morire",
    "zh-Hans": "我想死",
    "hi": "मैं आत्महत्या के बारे में सोच रहा हूँ",
    "ne": "मलाई मर्न मन लाग्छ",
}


async def run(lang: str, message: str, llm: Any, tools: Any = None) -> tuple[Any, FakeChatLLM]:
    ctx = ChatToolContext(tools=tools or make_tools())
    r = await Penny(llm=llm, settings=SETTINGS).answer(ChatRequest(message=message, language=lang), ctx)
    check_invariants(r)
    return r, llm


def test_every_language_has_every_fixed_text_and_step_label() -> None:
    assert set(i18n.LANGS) == {"en", "fr", "es", "pt", "it", "zh-Hans", "hi", "ne"}
    for table in (i18n.OUT_OF_SCOPE, i18n.DISTRESS, i18n.UNAVAILABLE, i18n.NOT_CONFIRMED, i18n.NO_OFFICIAL_SOURCE,
                  i18n.NO_INSTRUCTIONS, i18n.TEMPLATE_INTRO):  # fmt: skip
        assert set(table) == set(i18n.LANGS)
    for lang in i18n.LANGS:
        assert "116 123" in i18n.DISTRESS[lang][1] and "Samaritans" in i18n.DISTRESS[lang][1]
        assert "—" not in " ".join([i18n.OUT_OF_SCOPE[lang], *i18n.DISTRESS[lang], i18n.UNAVAILABLE[lang]])
    for en, by_lang in i18n.STEPS.items():
        assert set(by_lang) == set(i18n.LANGS) - {"en"}, en
    assert i18n.UNAVAILABLE["en"] == prompts.UNAVAILABLE_TEXT and i18n.OUT_OF_SCOPE["en"] == prompts.OUT_OF_SCOPE_TEXT
    assert i18n.DISTRESS["en"] == prompts.DISTRESS_TEXT
    assert i18n.step("Replaying 2021–2023…", "fr") == "Je rejoue 2021–2023…"


@pytest.mark.parametrize("lang", i18n.LANGS)
async def test_personal_answer_in_language(lang: str) -> None:
    llm = FakeChatLLM(call("finance_summary"), final(PERSONAL[lang]))
    r, _ = await run(lang, "How much do I spend?", llm)
    assert r.verified and r.mode == "checked" and r.bubbles[0].text == PERSONAL[lang]
    assert r.highlights and r.highlights[0].fact_id == "finance.monthly_spend"
    first = llm.requests[0]["messages"][-1]["content"]
    if lang == "en":
        assert "ANSWER LANGUAGE" not in first
    else:
        assert f"ANSWER LANGUAGE: {i18n.LANGUAGE_NAMES[lang]}" in first  # type: ignore[index]
    assert llm.requests[0]["system"] == prompts.PENNY_SYSTEM  # same cached system prompt in every language


@pytest.mark.parametrize("lang", i18n.LANGS)
async def test_general_answer_in_language(lang: str) -> None:
    r, _ = await run(lang, "What is a budget?", FakeChatLLM(final(GENERAL[lang])))
    assert r.verified and r.mode == "general" and r.bubbles[0].text == GENERAL[lang]


@pytest.mark.parametrize("lang", i18n.LANGS)
async def test_safety_replies_in_language(lang: str) -> None:
    llm = FakeChatLLM()
    r, _ = await run(lang, DISTRESS_IN[lang], llm)
    assert llm.requests == [] and [b.text for b in r.bubbles] == list(i18n.DISTRESS[lang])  # type: ignore[index]
    r2, _ = await run(lang, "Should I buy Bitcoin?", FakeChatLLM())
    assert r2.bubbles[0].text == i18n.OUT_OF_SCOPE[lang]  # type: ignore[index]
    ctx = ChatToolContext(tools=make_tools())
    r3 = await Penny(llm=None, settings=SETTINGS).answer(ChatRequest(message="Hi", language=lang), ctx)
    assert r3.bubbles[0].text == i18n.UNAVAILABLE[lang]  # type: ignore[index]


@pytest.mark.parametrize("lang", ["fr", "zh-Hans", "hi"])
async def test_step_labels_in_language(lang: str) -> None:
    llm = FakeChatLLM(call("finance_summary"), final(PERSONAL[lang]))
    ctx = ChatToolContext(tools=make_tools())
    ev = [e async for e in Penny(llm=llm, settings=SETTINGS).answer_stream(
        ChatRequest(message="Spend?", language=lang), ctx)]  # fmt: skip
    labels = [e.step.label for e in ev if e.type == "tool_step"]
    assert labels == [i18n.STEPS["Reading your accounts…"][lang]]  # type: ignore[index]


def test_french_figure_of_speech_is_not_distress() -> None:
    from lifeline_explain.chat import distress_rule

    assert not distress_rule("Je veux en finir avec mes dettes de carte")


# ---------- onboarding: no finance data ----------


def no_data_tools() -> Any:
    from lifeline_contracts.finance import FinanceSnapshot
    from lifeline_data.macro import mock_macro_table
    from lifeline_explain.chat_engine_tools import EngineToolSet

    snap = FinanceSnapshot(status="unavailable", source="none", as_of="2026-10-18", transactions=[], accounts=[])
    return EngineToolSet(snap, mock_macro_table(), date(2026, 10, 18))


async def test_onboarding_without_data_is_general_and_scoped() -> None:
    ts = no_data_tools()
    names = {s.name for s in ts.specs()}
    assert not names & {"finance_summary", "next_move", "user_balance", "habit_score", "cash_flow_projection"}
    assert "facts_table" in names and ts.has_user_data is False and ts.preload == ()
    llm = FakeChatLLM(final("A student budget starts with your loan, rent and food."))
    r = await Penny(llm=llm, settings=SETTINGS).answer(
        ChatRequest(message="How should I plan money at uni?", language="es"), ChatToolContext(tools=ts)
    )
    first = llm.requests[0]["messages"][-1]["content"]
    assert "NO USER DATA" in first and "ANSWER LANGUAGE: Spanish" in first and "APP DATA" not in first
    assert r.mode == "general" and r.verified and r.tool_calls == []


async def test_onboarding_never_claims_data_it_does_not_have() -> None:
    said = final("Your balance is £500, so you are fine.")
    llm = FakeChatLLM(said, said)
    r = await Penny(llm=llm, settings=SETTINGS).answer(
        ChatRequest(message="How much do I have?"), ChatToolContext(tools=no_data_tools())
    )
    assert "500" not in " ".join(b.text for b in r.bubbles) and not r.verified


# ---------- onboarding screen with user data ----------


async def test_onboarding_screen_is_public_only_even_with_data() -> None:
    from lifeline_contracts.chat import ChatContext
    from lifeline_data.macro import mock_macro_table
    from lifeline_explain.chat_engine_tools import EngineToolSet
    from tests.unit.engine.finance_builders import homeowner

    ts = EngineToolSet(homeowner(), mock_macro_table(), date(2026, 10, 18))
    assert ts.has_user_data
    onboarding = ChatContext(screen="onboarding")
    llm = FakeChatLLM(final("Most students budget week by week around their loan instalments."))
    r = await Penny(llm=llm, settings=SETTINGS).answer(
        ChatRequest(message="What is my next move?", context=onboarding), ChatToolContext(tools=ts)
    )
    req = llm.requests[0]
    offered = {t.get("name") for t in req["tools"]}
    assert not offered & {"finance_summary", "next_move", "user_balance", "habit_score", "test_move"}
    assert "facts_table" in offered and "web_search" in offered
    first = req["messages"][-1]["content"]
    assert "APP DATA" not in first and "NO USER DATA" in first
    assert r.mode == "general" and r.links == [] and r.tool_calls == []


async def test_onboarding_screen_blocks_personal_tool_and_links() -> None:
    from lifeline_contracts.chat import ChatContext

    llm = FakeChatLLM(call("next_move"), final("Budgeting helps."))
    r = await Penny(llm=llm, settings=SETTINGS).answer(
        ChatRequest(message="Help", context=ChatContext(screen="onboarding")), ChatToolContext(tools=make_tools())
    )
    tool_result = llm.requests[1]["messages"][-1]["content"][0]
    assert tool_result["is_error"] and r.tool_calls == [] and r.links == []
    r2 = await Penny(llm=FakeChatLLM(), settings=SETTINGS).answer(
        ChatRequest(message="Should I buy Bitcoin?", context=ChatContext(screen="onboarding")),
        ChatToolContext(tools=make_tools()),
    )
    assert r2.reaction == "shrug" and r2.links == []


# ---------- V6 final F-2, F-3, F-4: safety in every language ----------

PICK_ASK = {
    "fr": "Quelle crypto dois-je acheter ?", "es": "¿Qué acciones debo comprar?", "pt": "Devo comprar Bitcoin?",
    "it": "Quali azioni comprare?", "zh-Hans": "我应该买哪只股票？", "hi": "मुझे कौन सा शेयर खरीदना चाहिए?",
    "ne": "मैले कुन सेयर किन्नु पर्छ?", "en": "Which shares should I buy?",
}  # fmt: skip
PICK_ANSWER = {
    "fr": "Achetez du Bitcoin et des actions Tesla.", "es": "Compra acciones de Tesla y Bitcoin.",
    "pt": "Compre Bitcoin agora.", "it": "Compra azioni Tesla.", "zh-Hans": "买特斯拉股票和比特币。",
    "hi": "टेस्ला के शेयर और बिटकॉइन खरीदें।", "ne": "बिटकोइन किन्नुहोस्।", "en": "Buy Tesla shares now.",
}  # fmt: skip
CLAIM = {
    "fr": "Votre solde est de £50,000.", "es": "Tienes 1.749 £ en tu cuenta.", "pt": "Você tem £1,749.",
    "it": "Hai 1.749,00 £.", "zh-Hans": "你的余额是 £1,749。", "hi": "आपके पास £1,749 हैं।",
    "ne": "तपाईंसँग £1,749 छ।", "en": "You have £1,749.",
}  # fmt: skip
HARDSHIP = {
    "fr": "Je n'en peux plus, je n'ai plus rien à manger", "es": "No tengo dinero para comer",
    "pt": "Não aguento mais, não consigo pagar o aluguel", "it": "Non ce la faccio più",
    "zh-Hans": "我没钱吃饭，交不起房租", "hi": "मेरे पास खाने के पैसे नहीं हैं", "ne": "खाना किन्ने पैसा छैन",
    "en": "I can't afford food this week",
}  # fmt: skip


@pytest.mark.parametrize("lang", i18n.LANGS)
async def test_pick_question_refused_in_language(lang: str) -> None:
    llm = FakeChatLLM()
    r, _ = await run(lang, PICK_ASK[lang], llm)
    assert llm.requests == [] and r.bubbles[0].text == i18n.OUT_OF_SCOPE[lang]  # type: ignore[index]


@pytest.mark.parametrize("lang", i18n.LANGS)
async def test_pick_answer_replaced_in_language(lang: str) -> None:
    r, _ = await run(lang, "Conseil ?", FakeChatLLM(final(PICK_ANSWER[lang])))
    assert r.bubbles[0].text == i18n.OUT_OF_SCOPE[lang] and r.reaction == "shrug"  # type: ignore[index]


@pytest.mark.parametrize("lang", i18n.LANGS)
async def test_personal_claim_blocked_in_language(lang: str) -> None:
    said = final(CLAIM[lang])
    r, llm = await run(lang, "?", FakeChatLLM(said, said))
    text = " ".join(b.text for b in r.bubbles)
    assert not r.verified and len(llm.requests) == 2
    assert "1,749" not in text and "1.749" not in text and "50,000" not in text


@pytest.mark.parametrize("lang", i18n.LANGS)
async def test_hardship_gets_support_reply_in_language(lang: str) -> None:
    llm = FakeChatLLM()
    r, _ = await run(lang, HARDSHIP[lang], llm)
    assert llm.requests == [] and "116 123" in r.bubbles[1].text


def test_local_money_formats_are_money() -> None:
    from lifeline_explain.verifier import extract_numbers

    for text in ("1 749 £", "1.749 £", "1.749,00 £", "£1.749", "£1,749", "1,749 £"):
        (n,) = extract_numbers(text)
        assert n.value == 1749 and n.kind == "gbp", text
    (p,) = extract_numbers("£1.50")
    assert p.value == 1.5


@pytest.mark.parametrize(
    "text",
    ["A comprehensive guide from HMRC explains it.", "Compra frutta e verdura al mercato.", "去超市买菜。",
     "Je veux en finir avec mes dettes de carte."],
)  # fmt: skip
def test_everyday_text_is_not_a_pick_or_distress(text: str) -> None:
    from lifeline_explain.chat import distress_rule, gives_pick, out_of_scope_rule

    assert not gives_pick(text) and not out_of_scope_rule(text) and not distress_rule(text)
