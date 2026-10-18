"""Module boundaries. Each worker implements its side; the API (W4) calls them.

Rules:
- Sim and engine functions are pure and synchronous. Same inputs give the same outputs.
- `Life` objects are values. Functions return new objects; they never mutate inputs.
- Data hub and explain are async because they may do I/O.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from lifeline_contracts.domain import (
    ActionResult,
    AgeResult,
    Challenge,
    CharacterSpec,
    ChoiceResult,
    Concept,
    Decision,
    DecisionProfile,
    Evaluation,
    Event,
    Life,
    LifeMode,
    LifeSummary,
    Outcome,
    RewindResult,
)
from lifeline_contracts.finance import FinanceSnapshot
from lifeline_contracts.macro import MacroTable
from lifeline_contracts.observation import Observation, SourceStatus


class DataHub(Protocol):
    """W1: `lifeline_data.hub.DataHub` implements this."""

    async def series(self, source: str, series_id: str, region: str | None = None) -> list[Observation]: ...

    async def statuses(self) -> list[SourceStatus]: ...

    async def macro_table(self) -> MacroTable:
        """Annual MacroTable for 1990..current year. Never raises: falls back to cached, then mock."""
        ...

    async def finance_snapshot(self, subject: str) -> FinanceSnapshot | None:
        """Money tab data for one user (ADR 0016). None without own data, in every mode (ADR 0071). Never raises."""
        ...

    async def fx_rate(self, base: str, quote: str) -> tuple[float, date] | None:
        """Quote units per 1 base and the ECB reference date (Frankfurter). None when no real rate (ADR 0060)."""
        ...

    async def cpi(self) -> tuple[float, date] | None:
        """Latest ONS CPI annual rate (%) and its month. None when no real value (ADR 0060)."""
        ...

    async def bank_holidays(self, region: str | None) -> set[date]:
        """gov.uk bank holidays for the region's division (ADR 0017). Never raises."""
        ...

    async def daily_weather(
        self, region: str | None, start: date, end: date, *, today: date | None = None
    ) -> list[dict[str, object]]:
        """Open-Meteo daily weather: [{date, temp_max_c, rain_mm, status}] (ADR 0017). Never raises."""
        ...

    async def lookup_postcode(self, postcode: str) -> dict[str, str] | None:
        """Returns {'region': slug, 'town': name, 'postcode': normalised} or None."""
        ...


class SimAPI(Protocol):
    """W3: module `lifeline_sim.api` exposes these as plain functions."""

    def new_life(
        self, life_id: str, character: CharacterSpec, mode: LifeMode, start_year: int, seed: int, macro: MacroTable
    ) -> Life: ...

    def age(self, life: Life, macro: MacroTable) -> AgeResult: ...

    def choose(self, life: Life, event_id: str, choice_id: str, macro: MacroTable) -> ChoiceResult: ...

    def act(
        self, life: Life, tab: str, action_id: str, params: dict[str, float | str], macro: MacroTable
    ) -> ActionResult: ...

    def rewind(self, life: Life, decision_id: str, macro: MacroTable) -> RewindResult: ...

    def summary(self, life: Life) -> LifeSummary: ...

    def play_scenario(
        self,
        life_id: str,
        character: CharacterSpec,
        start_year: int,
        end_year: int,
        policy: dict[str, str],
        seed: int,
        macro: MacroTable,
    ) -> Life:
        """'Test it' (ADR 0018). Play from start_year to end_year. At each event, if policy has the event's
        template_id (or a tag the template declares, e.g. 'mortgage_deal_end'), take that choice id;
        otherwise take the default. Deterministic."""
        ...

    def presets(self) -> list[CharacterSpec]: ...

    def concepts(self, macro: MacroTable | None = None) -> list[Concept]: ...

    def challenges(self) -> list[Challenge]: ...


class EngineAPI(Protocol):
    """W2: module `lifeline_engine.api` exposes these as plain functions."""

    def random_character(self, seed: int, macro: MacroTable) -> CharacterSpec:
        """Draw one person from the synthetic UK population."""
        ...

    def decide(self, profile: DecisionProfile, macro: MacroTable, as_of_year: int) -> Decision: ...

    def evaluate(self, macro: MacroTable) -> Evaluation: ...


class ExplainAPI(Protocol):
    """W5: module `lifeline_explain.api`. Never raises. Falls back to the template text."""

    async def event_text(self, event: Event) -> Event: ...

    async def outcome_text(self, event: Event, outcome: Outcome) -> Outcome: ...
