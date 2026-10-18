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


def winner_line(final: list[PlayerScore]) -> str | None:
    """Penny's one line at the end of a quiz or decision round. Numbers come from the ranking."""
    if not final:
        return None
    top = [r for r in final if r.rank == 1]
    if len(top) > 1:
        return f"A tie at the top: {' and '.join(r.name for r in top)} with {top[0].score} points."[:200]
    return f"{top[0].name} wins with {top[0].score} points."[:200]


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


# ---------- game state kept in the room (so any replica can resume, V3 F3) ----------


def store_quiz(doc: RoomDoc, items: list[QuizItem]) -> None:
    """Put the whole quiz (questions with answers) in the room's server-only state, at round 0."""
    data = [{"question": i.question.model_dump(mode="json"), "correct": i.correct_choice_id,
             "explanation": i.explanation} for i in items]
    doc.game_state.update(kind="quiz", items=data, round=0, round_id=None)


def store_decision(doc: RoomDoc, item: DecisionItem) -> None:
    data = [{"prompt": item.prompt.model_dump(mode="json"),
             "outcomes": [o.model_dump(mode="json") for o in item.outcomes], "penny_line": item.penny_line}]
    doc.game_state.update(kind="decision", items=data, round=0, round_id=None)


def open_round_message(doc: RoomDoc, msg: Any) -> dict[str, Any] | None:
    """The question or decision that is open now, to re-send to a player who reconnects."""
    gs = doc.game_state
    if gs.get("round_id") is None or int(time.time() * 1000) >= gs.get("deadline_ms", 0):
        return None
    item = gs["items"][gs["round"]]
    if gs.get("kind") == "quiz":
        return msg("question", question=QuizQuestion.model_validate(item["question"]))  # type: ignore[no-any-return]
    return msg("decision", decision=DecisionPrompt.model_validate(item["prompt"]))  # type: ignore[no-any-return]


# ---------- drivers ----------

HEARTBEAT_MS = 3000  # a dead driver is noticed within 3 s
HEARTBEAT_REFRESH_SECONDS = 1.0


async def driver_alive(state: AppState, code: str) -> bool:
    return await state.rooms.heartbeat_alive(code)


async def ensure_driver(state: AppState, code: str, msg: Any) -> bool:
    """Start a driver for a playing quiz or decision room when none is alive (after an API restart, or when
    the host restarts a stuck game). Only one replica wins the claim. True when a driver was started."""
    doc = await state.rooms.get(code)
    if doc is None or doc.status != "playing" or "items" not in doc.game_state:
        await state.rooms.set_active(code, False)  # gone, finished or not a timed game
        return False
    if await driver_alive(state, code) or not await state.rooms.claim_driver(code, HEARTBEAT_MS):
        return False
    launch(state, run_game(state, code, msg), code)
    return True


def local_driver_running(state: AppState, code: str) -> bool:
    task = state.memo.get(("driver", code))
    return task is not None and not task.done()


async def restart_driver(state: AppState, code: str, msg: Any) -> bool:
    """The host restarts a stalled game at once (V3 final): unless this process is driving it, take it over now,
    without waiting for the old heartbeat to expire."""
    if local_driver_running(state, code):
        return False
    await state.rooms.heartbeat(code, HEARTBEAT_MS)
    launch(state, run_game(state, code, msg), code)
    return True


async def watchdog(state: AppState, msg: Any, every: float = 1.0) -> None:
    """On every replica: re-claim playing games whose driver heartbeat expired (the replica died)."""
    while True:
        try:
            for code in await state.rooms.active_games():
                await ensure_driver(state, code, msg)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.info("game watchdog: %s", type(exc).__name__)
        await asyncio.sleep(every)


async def _pause(state: AppState, code: str, seconds: float) -> None:
    """Sleep between rounds while keeping the heartbeat fresh."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        await state.rooms.heartbeat(code, HEARTBEAT_MS)
        await asyncio.sleep(min(HEARTBEAT_REFRESH_SECONDS, max(0.0, end - time.monotonic())))


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


async def _reopen_round(state: AppState, code: str, window_ms: int, message: dict[str, Any]) -> RoomDoc | None:
    async with state.rooms.lock(code):
        doc = await state.rooms.get(code)
        if doc is None:
            return None
        now_ms = int(time.time() * 1000)
        doc.game_state.update(opened_ms=now_ms, deadline_ms=now_ms + window_ms)
        await state.rooms.put(doc)
    await state.rooms.publish(code, message)
    return doc


async def _wait_answers(state: AppState, code: str) -> RoomDoc | None:
    """Until the window closes or every connected player answered. Returns the room with the window closed."""
    while True:
        await state.rooms.heartbeat(code, HEARTBEAT_MS)
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


async def run_game(state: AppState, code: str, msg: Any) -> None:
    """Drive the game from the round stored in the room. Resumes an open round instead of re-opening it."""
    while True:
        await state.rooms.heartbeat(code, HEARTBEAT_MS)
        doc = await state.rooms.get(code)
        if doc is None or doc.status != "playing":
            return
        gs = doc.game_state
        r = int(gs.get("round", 0))
        items = gs.get("items", [])
        if r >= len(items):
            break
        item = items[r]
        quiz = gs.get("kind") == "quiz"
        if quiz:
            q = QuizQuestion.model_validate(item["question"])
            rid, choice_ids, window, message = q.id, [c.id for c in q.choices], q.answer_ms, msg("question", question=q)
        else:
            pr = DecisionPrompt.model_validate(item["prompt"])
            rid, choice_ids, window, message = (pr.id, [o.id for o in pr.options], pr.answer_ms,
                                                msg("decision", decision=pr))
        if gs.get("round_id") == rid:
            # Resumed mid-round (after a restart): restart the answer window from now, keep the answers given,
            # and send the question again. Never a question whose window has already closed.
            if await _reopen_round(state, code, window, message) is None:
                return
        elif await _open_round(state, code, rid, choice_ids, window, message) is None:
            return
        if await _wait_answers(state, code) is None:
            return
        reveal = await (_reveal_quiz(state, code, item, msg) if quiz else _reveal_decision(state, code, item, msg))
        if reveal is None:
            return
        await state.rooms.publish(code, reveal)
        await _pause(state, code, REVEAL_PAUSE_SECONDS)
    await _finish(state, code, msg)


async def _reveal_quiz(state: AppState, code: str, item: dict[str, Any], msg: Any) -> dict[str, Any] | None:
    q = QuizQuestion.model_validate(item["question"])
    last: dict[str, bool] = {}
    async with state.rooms.lock(code):
        doc = await state.rooms.get(code)
        if doc is None:
            return None
        scores = doc.game_state.setdefault("scores", {})
        for p in doc.players:
            a = doc.game_state.get("answers", {}).get(p["id"])
            ok = a is not None and a["choice"] == item["correct"]
            last[p["id"]] = ok
            scores[p["id"]] = scores.get(p["id"], 0) + points(ok, a["ms"] if a else 0, q.answer_ms)
        doc.game_state["round"] = int(doc.game_state.get("round", 0)) + 1
        await state.rooms.put(doc)
    reveal = QuizReveal(question_id=q.id, correct_choice_id=item["correct"], explanation=item["explanation"],
                        source_label=q.source_label, source_url=q.source_url, ranking=ranking(doc, last))
    return msg("quiz_reveal", quiz_reveal=reveal)  # type: ignore[no-any-return]


async def _reveal_decision(state: AppState, code: str, item: dict[str, Any], msg: Any) -> dict[str, Any] | None:
    pr = DecisionPrompt.model_validate(item["prompt"])
    outcomes = [DecisionOutcome.model_validate(o) for o in item["outcomes"]]
    change = {o.option_id: o.game_money_change for o in outcomes}
    order = sorted(change, key=lambda k: change[k], reverse=True)
    async with state.rooms.lock(code):
        doc = await state.rooms.get(code)
        if doc is None:
            return None
        scores = doc.game_state.setdefault("scores", {})
        answers = doc.game_state.get("answers", {})
        for p in doc.players:
            a = answers.get(p["id"])
            # Best outcome scores most; no answer scores nothing. Points, never money.
            scores[p["id"]] = 0 if a is None else 100 * (len(order) - order.index(a["choice"]))
        doc.game_state["round"] = int(doc.game_state.get("round", 0)) + 1
        await state.rooms.put(doc)
    choices = [PlayerChoice(player_id=p["id"], name=p["name"],
                            option_id=(answers.get(p["id"]) or {}).get("choice")) for p in doc.players]
    reveal = DecisionReveal(prompt_id=pr.id, choices=choices, outcomes=outcomes, penny_line=item["penny_line"],
                            ranking=ranking(doc))
    return msg("decision_reveal", decision_reveal=reveal)  # type: ignore[no-any-return]


async def _finish(state: AppState, code: str, msg: Any) -> None:
    async with state.rooms.lock(code):
        doc = await state.rooms.get(code)
        if doc is None:
            return
        doc.status = "finished"
        for p in doc.players:
            p["finished"] = True
        await state.rooms.put(doc)
    await state.rooms.set_active(code, False)
    final = ranking(doc)
    await state.rooms.publish(code, msg("ranking", ranking=final))
    await state.rooms.publish(code, msg("finished", room=doc.public(), winner_line=winner_line(final)))


def launch(state: AppState, coro: Any, code: str | None = None) -> None:
    """Keep a reference so the driver task is not garbage collected."""
    task = asyncio.create_task(coro)
    state.games.add(task)
    if code is not None:
        state.memo[("driver", code)] = task

    def done(t: asyncio.Task[Any]) -> None:
        state.games.discard(t)
        if not t.cancelled() and t.exception() is not None:
            log.warning("room game failed: %s", type(t.exception()).__name__)

    task.add_done_callback(done)
