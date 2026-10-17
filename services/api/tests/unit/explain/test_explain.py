"""Explain layer tests. No network: every LLM call goes to FakeLLM."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import fakeredis.aioredis
import pytest

from lifeline_contracts.domain import Choice, Deltas, Event, Outcome
from lifeline_contracts.next_move import EvidencePoint, Move, MoveOption
from lifeline_contracts.next_move import TestPeriod as Period
from lifeline_explain import api
from lifeline_explain.cache import MemoryCache, RedisCache
from lifeline_explain.config import ExplainSettings
from lifeline_explain.service import Explainer
from lifeline_explain.verifier import extract_numbers, verify


class FakeLLM:
    def __init__(self, reply: Any = None, delay: float = 0.0, exc: Exception | None = None) -> None:
        self.reply = reply
        self.delay = delay
        self.exc = exc
        self.calls: list[str] = []

    async def complete(self, system: str, user: str, schema: dict[str, Any]) -> str:
        self.calls.append(user)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.exc:
            raise self.exc
        return self.reply if isinstance(self.reply, str) else json.dumps(self.reply)


SETTINGS = ExplainSettings(model="claude-opus-5-5", timeout_seconds=0.2, redis_url=None, enabled=True)


def make(client: FakeLLM | None, cache: Any = None) -> Explainer:
    return Explainer(client=client, cache=cache or MemoryCache(), settings=SETTINGS)


@pytest.fixture
def event() -> Event:
    return Event(
        id="e1",
        template_id="mortgage_deal_end",
        area="home",
        year=2022,
        age=34,
        emoji="🏠",
        title="Your fixed deal ends",
        text="Your fix ends. The new rate is 4.1%, so your payment goes up to £1,050.17 a month.",
        choices=[Choice(id="fix_5y", label="Fix for 5 years", is_default=True), Choice(id="tracker", label="Tracker")],
        facts={"new_rate": 4.1, "monthly_payment": 1050.17},
    )


@pytest.fixture
def outcome() -> Outcome:
    return Outcome(
        event_id="e1",
        choice_id="fix_5y",
        text="You locked in. You pay £1,050.17 a month until 2027.",
        deltas=Deltas(money=-300),
        facts={"monthly_payment": 1050.17},
        good=True,
    )


def make_move() -> Move:
    return Move(
        id="m1",
        kind="fix_mortgage",
        action="Fix for 5 years",
        headline="Your deal ends in 165 days",
        impact_per_year=1240.0,
        worst_case_per_year=-310.0,
        confidence=0.7,
        confidence_label="7 in 10 twins in similar past periods did better",
        evidence=[
            EvidencePoint(text="Rates rose 3.2 points in 2022.", facts={"rate_rise": 3.2}),
            EvidencePoint(text="7 in 10 twins did better after fixing.", facts={"share": 0.7}),
            EvidencePoint(text="You would save £1,240 a year.", facts={"saving": 1240.0}),
        ],
        sources=[],
        options=[MoveOption(id="fix_5y", label="Fix for 5 years", is_recommended=True)],
        deadline="2027-03-31",
        days_left=165,
        testable=True,
        test_period=Period(start=2021, end=2023, label="2021-2023 rate shock"),
    )


# ---------- verifier ----------


def test_extract_formats() -> None:
    vals = {round(f.value, 4) for f in extract_numbers("£1,050.17 at 4.1%, 45 days, seven years, 7 in 10, £4.2k")}
    assert {1050.17, 4.1, 45.0, 7.0, 0.7, 4200.0} <= vals


def test_verify_accepts_rounding_and_percent_fraction() -> None:
    assert verify("About £1,050 a month at 4.1%.", {"p": 1050.17, "r": 0.041}).ok
    assert verify("Seven out of ten twins did better.", {"c": 0.68}).ok
    assert verify("At 34, in 2022, you pay more.", {}, year=2022, age=34).ok


def test_verify_rejects_invented_numbers() -> None:
    v = verify("You pay £1,200 a month, up 15%.", {"p": 1050.17})
    assert not v.ok and "1,200" in v.unmatched
    assert not verify("At 35 you pay more.", {}, year=2022, age=34).ok
    assert not verify("9 in 10 twins did better.", {"c": 0.7}).ok


def test_verify_allows_numbers_from_source_text() -> None:
    assert verify("Lock in for 5 years.", {}, source_text="Fix for 5 years").ok


# ---------- event and outcome ----------


async def test_valid_text_accepted(event: Event) -> None:
    fake = FakeLLM({"text": "Your fix is over. At 4.1% your bill climbs to £1,050.17 a month."})
    out = await make(fake).event_text(event)
    assert out.text_source == "llm"
    assert "climbs" in out.text
    assert out.facts == event.facts and out.choices == event.choices


async def test_invented_number_rejected(event: Event) -> None:
    fake = FakeLLM({"text": "Your fix is over. Your bill jumps by £400 a month."})
    out = await make(fake).event_text(event)
    assert out.text_source == "template"
    assert out.text == event.text


async def test_timeout_falls_back(event: Event) -> None:
    fake = FakeLLM({"text": "Too late."}, delay=1.0)
    out = await make(fake).event_text(event)
    assert out.text_source == "template" and out.text == event.text


async def test_exception_falls_back(event: Event, outcome: Outcome) -> None:
    fake = FakeLLM(exc=RuntimeError("boom"))
    ex = make(fake)
    assert (await ex.event_text(event)).text_source == "template"
    assert (await ex.outcome_text(event, outcome)).text_source == "template"


async def test_bad_json_falls_back(event: Event) -> None:
    out = await make(FakeLLM("not json")).event_text(event)
    assert out.text_source == "template"


async def test_no_key_uses_templates(event: Event, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    ex = Explainer.from_env()
    assert ex.client is None
    api.set_explainer(ex)
    try:
        out = await api.event_text(event)
    finally:
        api.set_explainer(None)
    assert out.text_source == "template" and out.text == event.text


async def test_cache_hit_avoids_second_call(event: Event) -> None:
    fake = FakeLLM({"text": "Your fix is over. At 4.1% you now pay £1,050.17 a month."})
    ex = make(fake)
    a = await ex.event_text(event)
    b = await ex.event_text(event)
    assert a.text == b.text and b.text_source == "llm"
    assert len(fake.calls) == 1


async def test_rejection_is_cached(event: Event) -> None:
    fake = FakeLLM({"text": "You pay £999."})
    ex = make(fake)
    await ex.event_text(event)
    out = await ex.event_text(event)
    assert out.text_source == "template" and len(fake.calls) == 1


async def test_redis_cache_and_fallback(event: Event) -> None:
    fake = FakeLLM({"text": "Your fix is over. At 4.1% you now pay £1,050.17 a month."})
    cache = RedisCache("redis://unused", client=fakeredis.aioredis.FakeRedis())
    await make(fake, cache).event_text(event)
    await make(fake, cache).event_text(event)
    assert len(fake.calls) == 1

    class Broken:
        async def get(self, key: str) -> None:
            raise ConnectionError("down")

        async def set(self, key: str, value: str, ex: int) -> None:
            raise ConnectionError("down")

    fake2 = FakeLLM({"text": "Your fix is over. At 4.1% you now pay £1,050.17 a month."})
    broken = RedisCache("redis://unused", client=Broken())
    await make(fake2, broken).event_text(event)
    out = await make(fake2, broken).event_text(event)
    assert out.text_source == "llm" and len(fake2.calls) == 1


async def test_outcome_accepts_delta_and_year(event: Event, outcome: Outcome) -> None:
    fake = FakeLLM({"text": "Good call. In 2022 you lose £300 now but pay £1,050.17 a month until 2027."})
    out = await make(fake).outcome_text(event, outcome)
    assert out.text_source == "llm"
    assert out.deltas == outcome.deltas and out.good is True


async def test_outcome_rejects_invented(event: Event, outcome: Outcome) -> None:
    fake = FakeLLM({"text": "Good call. You save £5,000 by 2027."})
    out = await make(fake).outcome_text(event, outcome)
    assert out.text_source == "template" and out.text == outcome.text


async def test_em_dash_removed(event: Event) -> None:
    fake = FakeLLM({"text": "Your fix is over — at 4.1% you pay £1,050.17 a month."})
    out = await make(fake).event_text(event)
    assert "—" not in out.text


# ---------- next move ----------


async def test_move_text_rewords_only_text_fields() -> None:
    move = make_move()
    fake = FakeLLM(
        {
            "headline": "165 days until your deal runs out",
            "action": "Switch to a tracker",
            "evidence": [
                "In 2022 rates jumped 3.2 points.",
                "Seven in ten twins came out ahead by fixing.",
                "Fixing saves you £1,240 each year.",
            ],
        }
    )
    out = await make(fake).move_text(move)
    assert out.headline == "165 days until your deal runs out"
    assert out.action == move.action == "Fix for 5 years"  # never reworded: must match the option label
    assert out.evidence[1].text.startswith("Seven in ten")
    unchanged = {"headline", "evidence"}
    assert out.model_dump(exclude=unchanged) == move.model_dump(exclude=unchanged)
    assert [e.facts for e in out.evidence] == [e.facts for e in move.evidence]


async def test_move_text_rejects_new_numbers_per_field() -> None:
    move = make_move()
    fake = FakeLLM(
        {
            "headline": "Only 160 days left on your deal",
            "action": "Fix for 5 years",
            "evidence": ["Rates rose 3.2 points in 2022.", "9 in 10 twins did better.", "Save £1,240 a year."],
        }
    )
    out = await make(fake).move_text(move)
    assert out.headline == move.headline
    assert out.evidence[1].text == move.evidence[1].text
    assert out.evidence[2].text == "Save £1,240 a year."


async def test_move_text_failures_return_input() -> None:
    move = make_move()
    assert await make(FakeLLM(exc=RuntimeError("x"))).move_text(move) == move
    assert await make(None).move_text(move) == move
    bad_len = FakeLLM({"headline": "Deal ends soon", "action": "Fix", "evidence": ["only one"]})
    out = await make(bad_len).move_text(move)
    assert out.evidence == move.evidence


async def test_api_module_uses_injected_explainer(event: Event) -> None:
    fake = FakeLLM({"text": "Your fix is over. At 4.1% you now pay £1,050.17 a month."})
    api.set_explainer(make(fake))
    try:
        out = await api.event_text(event)
        move = await api.move_text(make_move())
    finally:
        api.set_explainer(None)
    assert out.text_source == "llm"
    assert move.kind == "fix_mortgage"


def test_settings_repr_has_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from lifeline_explain.config import load_settings

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-secret")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "bad")
    s = load_settings()
    assert "sk-test" not in repr(s)
    assert s.timeout_seconds == 12.0 and s.model
