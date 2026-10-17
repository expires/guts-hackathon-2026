"""Calls into lifeline_explain (W5). Every call is async, has its own timeout and never raises.

New events get their wording once, when they first appear. The reworded text is stored in the life,
so later reads and replays never call the LLM again for the same event.
"""

from __future__ import annotations

import asyncio

from lifeline_contracts.domain import Event, Life, Outcome
from lifeline_contracts.next_move import NextMoveResponse
from lifeline_explain import api as explain_api


async def explain_new_events(
    before: Life | None, after: Life, extra: list[Event] | None = None
) -> tuple[Life, list[Event]]:
    """Reword pending events of `after` that were not pending in `before`, plus `extra` (e.g. AgeResult.events).

    Returns the updated life and the updated `extra` list.
    """
    old_ids = {e.id for e in before.pending_events} if before is not None else set()
    todo: dict[str, Event] = {e.id: e for e in after.pending_events if e.id not in old_ids}
    for e in extra or []:
        todo.setdefault(e.id, e)
    todo = {k: e for k, e in todo.items() if e.text_source == "template"}
    if not todo:
        return after, list(extra or [])
    done = await asyncio.gather(*(explain_api.event_text(e) for e in todo.values()))
    by_id = {e.id: e for e in done}
    life = after.model_copy(update={"pending_events": [by_id.get(e.id, e) for e in after.pending_events]})
    return life, [by_id.get(e.id, e) for e in (extra or [])]


async def explain_outcome(before: Life, event_id: str, outcome: Outcome) -> Outcome:
    event = next((e for e in before.pending_events if e.id == event_id), None)
    if event is None:
        return outcome
    return await explain_api.outcome_text(event, outcome)


async def explain_moves(resp: NextMoveResponse) -> NextMoveResponse:
    moves = await asyncio.gather(explain_api.move_text(resp.top), *(explain_api.move_text(m) for m in resp.runners_up))
    return resp.model_copy(update={"top": moves[0], "runners_up": list(moves[1:])})
