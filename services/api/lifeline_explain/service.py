"""Explainer: LLM rewrite -> clean -> verify numbers -> cache, with template fallback on every failure path."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from lifeline_contracts.domain import Event, Outcome
from lifeline_contracts.next_move import Move
from lifeline_explain import prompts
from lifeline_explain.cache import TextCache, cache_key, make_cache
from lifeline_explain.config import CACHE_TTL_SECONDS, PROMPT_VERSION, ExplainSettings, has_api_key, load_settings
from lifeline_explain.llm import AnthropicLLM, LLMClient
from lifeline_explain.templates import clean, template_event, template_outcome
from lifeline_explain.verifier import verify

log = logging.getLogger(__name__)

REJECTED = "\x00rejected"  # cached marker: the verifier rejected this input once; serve the template


class Explainer:
    """Holds the LLM client and cache. `client=None` and no API key means templates only."""

    def __init__(
        self,
        client: LLMClient | None = None,
        cache: TextCache | None = None,
        settings: ExplainSettings | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.client = client
        self.cache: TextCache = cache if cache is not None else make_cache(self.settings.redis_url)

    @classmethod
    def from_env(cls) -> Explainer:
        settings = load_settings()
        client: LLMClient | None = None
        if settings.enabled and has_api_key():
            try:
                client = AnthropicLLM(settings)
            except Exception as exc:
                log.warning("explain: LLM client unavailable (%s); templates only", type(exc).__name__)
        return cls(client=client, settings=settings)

    # ---------- core ----------

    async def _call(self, key: str, user: str, schema: dict[str, Any]) -> dict[str, Any] | None:
        """Return parsed JSON from the cache or the LLM. None on timeout, error, refusal or bad JSON."""
        cached = await self._cache_get(key)
        if cached == REJECTED:
            return None
        if cached is not None:
            try:
                data = json.loads(cached)
                return data if isinstance(data, dict) else None
            except ValueError:
                return None
        if self.client is None:
            return None
        start = time.monotonic()
        try:
            raw = await asyncio.wait_for(
                self.client.complete(prompts.SYSTEM, user, schema), timeout=self.settings.timeout_seconds
            )
            data = json.loads(raw)
        except TimeoutError:
            log.info("explain: LLM timeout after %.1fs; template", time.monotonic() - start)
            return None
        except Exception as exc:
            log.info("explain: LLM failed (%s); template", type(exc).__name__)
            return None
        if not isinstance(data, dict):
            return None
        log.debug("explain: LLM ok in %.2fs", time.monotonic() - start)
        return data

    async def _cache_get(self, key: str) -> str | None:
        try:
            return await self.cache.get(key)
        except Exception:
            return None

    async def _cache_set(self, key: str, value: str) -> None:
        try:
            await self.cache.set(key, value, CACHE_TTL_SECONDS)
        except Exception as exc:
            log.debug("explain: cache set failed (%s)", type(exc).__name__)

    def _key(self, kind: str, **parts: Any) -> str:
        return cache_key(v=PROMPT_VERSION, model=self.settings.model, kind=kind, **parts)

    # ---------- public ----------

    async def event_text(self, event: Event) -> Event:
        try:
            return await self._event_text(event)
        except Exception as exc:
            log.warning("explain: event_text error (%s); template", type(exc).__name__)
            return template_event(event)

    async def _event_text(self, event: Event) -> Event:
        base = template_event(event)
        key = self._key(
            "event", template_id=event.template_id, facts=event.facts, text=base.text, year=event.year, age=event.age
        )
        user = prompts.event_prompt(
            title=event.title,
            text=base.text,
            area=event.area,
            year=event.year,
            age=event.age,
            facts=event.facts,
            choices=[c.label for c in event.choices],
        )
        data = await self._call(key, user, prompts.TEXT_SCHEMA)
        text = clean(str(data.get("text", "")), base.text) if data else None
        if text is None:
            return base
        verdict = verify(text, event.facts, base.text, year=event.year, age=event.age)
        if not verdict.ok:
            log.info("explain: rejected event %s numbers %s", event.template_id, verdict.unmatched)
            await self._cache_set(key, REJECTED)
            return base
        await self._cache_set(key, json.dumps({"text": text}))
        return base.model_copy(update={"text": text, "text_source": "llm"})

    async def outcome_text(self, event: Event, outcome: Outcome) -> Outcome:
        try:
            return await self._outcome_text(event, outcome)
        except Exception as exc:
            log.warning("explain: outcome_text error (%s); template", type(exc).__name__)
            return template_outcome(outcome)

    async def _outcome_text(self, event: Event, outcome: Outcome) -> Outcome:
        base = template_outcome(outcome)
        choice = next((c.label for c in event.choices if c.id == outcome.choice_id), outcome.choice_id)
        facts = {**event.facts, **outcome.facts, "_delta_money": outcome.deltas.money}
        key = self._key(
            "outcome",
            template_id=event.template_id,
            choice=outcome.choice_id,
            facts=facts,
            text=base.text,
            year=event.year,
            age=event.age,
        )
        user = prompts.outcome_prompt(
            event_title=event.title,
            event_text=event.text,
            choice=choice,
            text=base.text,
            good=outcome.good,
            year=event.year,
            age=event.age,
            facts=facts,
        )
        data = await self._call(key, user, prompts.TEXT_SCHEMA)
        text = clean(str(data.get("text", "")), base.text) if data else None
        if text is None:
            return base
        verdict = verify(text, facts, base.text, year=event.year, age=event.age)
        if not verdict.ok:
            log.info(
                "explain: rejected outcome %s/%s numbers %s", event.template_id, outcome.choice_id, verdict.unmatched
            )
            await self._cache_set(key, REJECTED)
            return base
        await self._cache_set(key, json.dumps({"text": text}))
        return base.model_copy(update={"text": text, "text_source": "llm"})

    async def move_text(self, move: Move) -> Move:
        try:
            return await self._move_text(move)
        except Exception as exc:
            log.warning("explain: move_text error (%s); template", type(exc).__name__)
            return move

    async def _move_text(self, move: Move) -> Move:
        move_facts: dict[str, float] = {
            "impact_per_year": move.impact_per_year,
            "worst_case_per_year": move.worst_case_per_year,
            "confidence": move.confidence,
        }
        if move.days_left is not None:
            move_facts["days_left"] = move.days_left
        if move.test_period is not None:
            move_facts["test_start"] = move.test_period.start
            move_facts["test_end"] = move.test_period.end
        all_facts = dict(move_facts)
        for i, ev in enumerate(move.evidence):
            all_facts.update({f"e{i}_{k}": v for k, v in ev.facts.items()})
        texts = [ev.text for ev in move.evidence]
        key = self._key(
            "move",
            move_kind=move.kind,
            facts=all_facts,
            headline=move.headline,
            action=move.action,
            evidence=texts,
            deadline=move.deadline,
        )
        user = prompts.move_prompt(
            kind=move.kind, headline=move.headline, action=move.action, evidence=texts, facts=all_facts
        )
        data = await self._call(key, user, prompts.MOVE_SCHEMA)
        if not data:
            return move

        rejected = False

        def pick(new: Any, old: str, facts: dict[str, float], max_len: int | None = None) -> str:
            # Per field: keep the LLM wording only if it is clean and every number traces to a fact.
            nonlocal rejected
            text = clean(str(new or ""), old, max_len)
            if text is None:
                return old
            if not verify(text, facts, old).ok:
                rejected = True
                return old
            return text

        headline = pick(data.get("headline"), move.headline, all_facts, max(120, len(move.headline) + 40))
        new_ev = data.get("evidence")
        evidence = list(move.evidence)
        if isinstance(new_ev, list) and len(new_ev) == len(move.evidence):
            evidence = [
                ev.model_copy(update={"text": pick(t, ev.text, {**ev.facts, **move_facts})})
                for ev, t in zip(move.evidence, new_ev, strict=True)
            ]
        if rejected:
            log.info("explain: rejected some move %s fields (numbers)", move.kind)
        # Cache the raw reply either way: every cache hit runs through the verifier again.
        await self._cache_set(key, json.dumps(data))
        return move.model_copy(update={"headline": headline, "evidence": evidence})
