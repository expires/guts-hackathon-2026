"""Choice projections for "Not sure? Ask Penny" on Life events (ADR 0031).

For each choice of an open event, the sim plays a copy of the life forward a few years with the
default choice at every later event and no tab actions. Nothing is stored. Every number in
`facts` comes from that replay; `sources` lists the macro series behind it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from lifeline_contracts.chat import ChatFact
from lifeline_contracts.domain import SourceRef

ASSUMPTION = "Takes the default at every later event and no tab actions."


class ChoiceProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    choice_id: str
    label: str
    is_default: bool
    start_year: int = Field(description="The event's year. The path starts after the choice.")
    end_year: int
    years: list[int] = Field(description="Year of each net_worth_path point")
    net_worth_path: list[float] = Field(description="Net worth at the end of each year, first = right after the choice")
    end_net_worth: float
    cost: float = Field(
        description="GBP over the projection for the items this event controls: the choice's own one-off "
        "and monthly costs, plus the running costs of the event's tags (for example mortgage payments)."
    )
    missed_payments: int = Field(ge=0, description="Missed payments during the projection")
    index: float = Field(ge=0, description="Index at end_year against the autopilot twin")
    alive: bool = True
    assumption: str = ASSUMPTION
    facts: list[ChatFact]
    sources: list[SourceRef]
