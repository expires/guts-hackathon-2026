"""ADR 0074: no player ever sees the word INDEX or an index number. Fake LLM, no network."""

from __future__ import annotations

from typing import Any

import pytest

from lifeline_contracts.chat import ChatFact
from lifeline_explain import game_scene, i18n, learn_scene, prompts
from lifeline_explain.chat import Draft, is_index_fact, says_index, without_index
from tests.unit.explain.test_chat import FakeChatLLM, ask, final

USER_FACING_MODULES = (i18n, game_scene, learn_scene)
FIXED_PROMPT_TEXTS = ("OUT_OF_SCOPE_TEXT", "DISTRESS_TEXT", "UNAVAILABLE_TEXT", "NO_INSTRUCTIONS_TEXT")


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in _strings(v)]
    return []


def test_no_user_facing_string_says_index() -> None:
    found: list[str] = []
    for mod in USER_FACING_MODULES:
        for name, value in vars(mod).items():
            if name.startswith("_") or not name.isupper():
                continue  # module constants only (fixed lines, chips, labels in the 8 languages)
            found += [f"{mod.__name__}.{name}: {s[:60]}" for s in _strings(value) if says_index(s)]
    for name in FIXED_PROMPT_TEXTS:
        found += [f"prompts.{name}" for s in _strings(getattr(prompts, name)) if says_index(s)]
    assert found == []


@pytest.mark.parametrize("text", [
    "Your Index went up to 72.", "INDEX: 640", "Tu Índice sube.", "Il tuo Indice sale.", "你的指数是 72。",
    "आपका सूचकांक 72 है।",
])  # fmt: skip
def test_index_is_detected_in_all_scripts(text: str) -> None:
    assert says_index(text)


@pytest.mark.parametrize("text", [
    "A tracker fund follows the market.", "An index fund spreads your money.", "Je ne donne pas d'indice.",
    "Your game money ends at £12,400.",
])  # fmt: skip
def test_finance_terms_and_hints_pass(text: str) -> None:
    assert not says_index(text)


def test_post_check_drops_the_sentence() -> None:
    d = without_index(Draft("eyes", [("answer", "Option A keeps more game money. Your Index rises to 72.")]))
    assert d.bubbles == [("answer", "Option A keeps more game money.")]
    d = without_index(Draft("eyes", [("answer", "Your Index rises to 72.")]), "fr")
    assert d.bubbles == [("answer", i18n.NO_INDEX["fr"])]


def test_index_facts_are_never_offered() -> None:
    assert is_index_fact(ChatFact(id="choice.a.index", value=72, unit="count", label="Index in 2031"))
    assert not is_index_fact(ChatFact(id="choice.a.net_worth", value=1200, unit="gbp", label="Net worth in 2031"))


async def test_answer_never_says_index() -> None:
    r, _ = await ask("How am I doing?", FakeChatLLM(final("You are doing fine. Your Index is 72.")))
    assert not any(says_index(b.text) for b in r.bubbles)


def test_prompt_rule() -> None:
    assert 'Never say "Index"' in prompts.PENNY_SYSTEM and "finance skill score out of 100" in prompts.PENNY_SYSTEM
    assert set(i18n.NO_INDEX) == set(i18n.LANGS)
