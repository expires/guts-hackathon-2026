"""Room games run by the server (ADR 0052, 0059): Money Quiz and Same Decision.

- Content: W3's sim functions (`quiz_questions`, `decision_prompts`, `decision_outcomes`).
- Timing is server-side. One driver task per game, on the replica whose host sent `start`. It publishes each
  question, waits for the answer window (or until every connected player answered), then publishes the reveal.
- Answers and correct ids live in RoomDoc.game_state (server only). Scores: 100 for a correct answer plus a
  speed bonus of up to 50 points.
- Privacy: nothing here touches a user's real money. Same Decision outcomes are game money.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from lifeline_api.rooms import RoomDoc
from lifeline_api.state import AppState
from lifeline_contracts.macro import MacroTable
from lifeline_contracts.play import (
    DecisionOutcome,
    DecisionPrompt,
    DecisionReveal,
    GameOptions,
    PlayerChoice,
    PlayerScore,
    QuizQuestion,
    QuizReveal,
)
from lifeline_sim import api as sim_api

log = logging.getLogger(__name__)

QUIZ_ANSWER_MS = 15_000
DECISION_ANSWER_MS = 20_000
REVEAL_PAUSE_SECONDS = 3.0
POLL_SECONDS = 0.2
CORRECT_POINTS = 100
SPEED_BONUS = 50

class GameUnavailable(Exception):
    """The content for this game is not available yet."""


@dataclass(frozen=True)
class QuizItem:
    question: QuizQuestion
    correct_choice_id: str
    explanation: str


@dataclass(frozen=True)
class DecisionItem:
    prompt: DecisionPrompt
    outcomes: list[DecisionOutcome]
    penny_line: str


# ---------- content ----------


def quiz_items(options: GameOptions, seed: int) -> list[QuizItem]:
    """W3's questions (lessons and the facts table, each with its official source)."""
    items = sim_api.quiz_questions(seed=seed, topic=options.topic, n=options.questions)
    return [QuizItem(question=i.question, correct_choice_id=i.correct_choice_id, explanation=i.explanation)
            for i in items]


def decision_item(options: GameOptions, seed: int, macro: MacroTable) -> DecisionItem:
    """One Same Decision prompt in real history and every option's outcome in game money (W3)."""
    prompts = sim_api.decision_prompts(seed=seed, n=1, macro=macro, year=options.start_year)
    if not prompts:
        raise GameUnavailable("No decision for that year")
    prompt = prompts[0]
    outs = sim_api.decision_outcomes(prompt.id, macro=macro)
    best = max(outs, key=lambda o: o.game_money_change)
    label = next((o.label for o in prompt.options if o.id == best.option_id), best.option_id)
    return DecisionItem(prompt=prompt, outcomes=outs,
                        penny_line=f"In {prompt.year}, \u201c{label}\u201d came out best in game money.")


# ---------- scoring ----------


def points(correct: bool, answer_ms: int, window_ms: int) -> int:
    if not correct:
        return 0
    left = max(0.0, 1.0 - answer_ms / window_ms)
    return CORRECT_POINTS + round(SPEED_BONUS * left)


def ranking(doc: RoomDoc, last: dict[str, bool] | None = None) -> list[PlayerScore]:
    scores: dict[str, int] = doc.game_state.get("scores", {})
    rows = sorted(doc.players, key=lambda p: (-scores.get(p["id"], 0), p["name"]))
    out: list[PlayerScore] = []
    for i, p in enumerate(rows):
        score = scores.get(p["id"], 0)
        rank = i + 1 if i == 0 or score != scores.get(rows[i - 1]["id"], 0) else out[-1].rank
        out.append(PlayerScore(player_id=p["id"], name=p["name"], score=score, rank=rank,
                               last_correct=None if last is None else last.get(p["id"], False)))
    return out


def record_answer(doc: RoomDoc, player_id: str, round_id: str | None, choice_id: str | None) -> str | None:
    """Store the first answer in the open window. Returns an error code, or None when stored."""
    gs = doc.game_state
    if gs.get("round_id") is None or round_id != gs.get("round_id"):
        return "not_open"
    now_ms = int(time.time() * 1000)
    if now_ms > gs["deadline_ms"]:
        return "too_late"
    if choice_id not in gs.get("choice_ids", []):
        return "invalid_choice"
    answers = gs.setdefault("answers", {})
    if player_id in answers:
        return "already_answered"
    answers[player_id] = {"choice": choice_id, "ms": max(0, now_ms - gs["opened_ms"])}
    return None


# ---------- drivers ----------


async def _open_round(state: AppState, code: str, round_id: str, choice_ids: list[str], window_ms: int,
                      message: dict[str, Any]) -> RoomDoc | None:
    async with state.rooms.lock(code):
        doc = await state.rooms.get(code)
        if doc is None:
            return None
        now_ms = int(time.time() * 1000)
        doc.game_state.update(round_id=round_id, choice_ids=choice_ids, answers={}, opened_ms=now_ms,
                              deadline_ms=now_ms + window_ms)
        await state.rooms.put(doc)
    await state.rooms.publish(code, message)
    return doc


async def _wait_answers(state: AppState, code: str) -> RoomDoc | None:
    """Until the window closes or every connected player answered. Returns the room with the window closed."""
    while True:
        doc = await state.rooms.get(code)
        if doc is None:
            return None
        gs = doc.game_state
        connected = {p["id"] for p in doc.players if p["connected"]}
        answered = set(gs.get("answers", {}))
        if int(time.time() * 1000) >= gs["deadline_ms"] or (connected and connected <= answered):
            break
        await asyncio.sleep(POLL_SECONDS)
    async with state.rooms.lock(code):
        doc = await state.rooms.get(code)
        if doc is not None:
            doc.game_state["round_id"] = None
            await state.rooms.put(doc)
    return doc


async def run_quiz(state: AppState, code: str, items: list[QuizItem], msg: Any) -> None:
    for item in items:
        q = item.question
        opened = await _open_round(state, code, q.id, [c.id for c in q.choices], q.answer_ms,
                                   msg("question", question=q))
        if opened is None:
            return
        doc = await _wait_answers(state, code)
        if doc is None:
            return
        last: dict[str, bool] = {}
        async with state.rooms.lock(code):
            doc = await state.rooms.get(code)
            if doc is None:
                return
            scores = doc.game_state.setdefault("scores", {})
            for p in doc.players:
                a = doc.game_state.get("answers", {}).get(p["id"])
                ok = a is not None and a["choice"] == item.correct_choice_id
                last[p["id"]] = ok
                scores[p["id"]] = scores.get(p["id"], 0) + points(ok, a["ms"] if a else 0, q.answer_ms)
            await state.rooms.put(doc)
        reveal = QuizReveal(question_id=q.id, correct_choice_id=item.correct_choice_id, explanation=item.explanation,
                            source_label=q.source_label, source_url=q.source_url, ranking=ranking(doc, last))
        await state.rooms.publish(code, msg("quiz_reveal", quiz_reveal=reveal))
        await asyncio.sleep(REVEAL_PAUSE_SECONDS)
    await _finish(state, code, msg)


async def run_decision(state: AppState, code: str, item: DecisionItem, msg: Any) -> None:
    pr = item.prompt
    opened = await _open_round(state, code, pr.id, [o.id for o in pr.options], pr.answer_ms,
                               msg("decision", decision=pr))
    if opened is None:
        return
    doc = await _wait_answers(state, code)
    if doc is None:
        return
    change = {o.option_id: o.game_money_change for o in item.outcomes}
    order = sorted(change, key=lambda k: change[k], reverse=True)
    async with state.rooms.lock(code):
        doc = await state.rooms.get(code)
        if doc is None:
            return
        scores = doc.game_state.setdefault("scores", {})
        answers = doc.game_state.get("answers", {})
        for p in doc.players:
            a = answers.get(p["id"])
            # Best outcome scores most; no answer scores nothing. Points, never money.
            scores[p["id"]] = 0 if a is None else 100 * (len(order) - order.index(a["choice"]))
        await state.rooms.put(doc)
    choices = [PlayerChoice(player_id=p["id"], name=p["name"],
                            option_id=(answers.get(p["id"]) or {}).get("choice")) for p in doc.players]
    reveal = DecisionReveal(prompt_id=pr.id, choices=choices, outcomes=item.outcomes, penny_line=item.penny_line,
                            ranking=ranking(doc))
    await state.rooms.publish(code, msg("decision_reveal", decision_reveal=reveal))
    await asyncio.sleep(REVEAL_PAUSE_SECONDS)
    await _finish(state, code, msg)


async def _finish(state: AppState, code: str, msg: Any) -> None:
    async with state.rooms.lock(code):
        doc = await state.rooms.get(code)
        if doc is None:
            return
        doc.status = "finished"
        for p in doc.players:
            p["finished"] = True
        await state.rooms.put(doc)
    await state.rooms.publish(code, msg("ranking", ranking=ranking(doc)))
    await state.rooms.publish(code, msg("finished", room=doc.public()))


def launch(state: AppState, coro: Any) -> None:
    """Keep a reference so the driver task is not garbage collected."""
    task = asyncio.create_task(coro)
    state.games.add(task)

    def done(t: asyncio.Task[Any]) -> None:
        state.games.discard(t)
        if not t.cancelled() and t.exception() is not None:
            log.warning("room game failed: %s", type(t.exception()).__name__)

    task.add_done_callback(done)
