"""Finance data for the Money tab and Next Move (ADR 0016, ADR 0018).

Tier 1: labelled fixture personas (`status="mock"`, `source="fixtures"`), chosen deterministically per
user subject. Tier 2 adds TrueLayer sandbox data through the bank session.

Public API (stable; W2 and W4 call these):
- `fixture_snapshot(subject, as_of=None) -> FinanceSnapshot`  sync, pure, offline, never raises.
- `persona_for_subject(subject) -> PersonaInfo`  region, postcode, age and the rest for profiles.
- `persona_id_for_subject(subject) -> str`
- `DataHub.finance_snapshot(subject)` (async) wraps `fixture_snapshot`.

Mapping rule: the demo device `demo-presenter-01` (JWT subject `demo_` + sha256("demo:<device>")[:24])
gets the Leeds homeowner. A subject `persona:<id>` or a raw persona id selects that persona (tests,
demo tools). Any other subject maps to a persona by a stable sha256 hash.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from lifeline_contracts.finance import FinanceSnapshot
from lifeline_data.finance.generator import FIXTURE_AS_OF, HISTORY_DAYS, build_snapshot
from lifeline_data.finance.personas import DEMO_DEVICE_ID, DEMO_PERSONA_ID, PERSONA_IDS, PERSONAS, Persona


def demo_subject(device_id: str) -> str:
    """Same rule as `lifeline_api.auth.demo_subject`. Kept here so the data layer does not import the API."""
    return "demo_" + hashlib.sha256(f"demo:{device_id}".encode()).hexdigest()[:24]


DEMO_SUBJECT = demo_subject(DEMO_DEVICE_ID)

# Subjects pinned to a persona. Everything else is hashed.
PINNED: dict[str, str] = {DEMO_SUBJECT: DEMO_PERSONA_ID, DEMO_DEVICE_ID: DEMO_PERSONA_ID}


@dataclass(frozen=True)
class PersonaInfo:
    """Facts about a persona that are not in FinanceSnapshot (for DecisionProfile and CharacterSpec)."""

    id: str
    label: str
    name: str
    sex: str
    birth_year: int
    occupation: str
    region: str
    town: str
    postcode: str
    gross_salary: float
    housing: str  # "rent" | "mortgage"
    monthly_rent: float | None
    unused_subscriptions: tuple[str, ...]
    notes: tuple[str, ...]

    def age(self, as_of: date = FIXTURE_AS_OF) -> int:
        return as_of.year - self.birth_year


def persona_id_for_subject(subject: str) -> str:
    if subject in PINNED:
        return PINNED[subject]
    if subject.startswith("persona:") and subject.removeprefix("persona:") in PERSONAS:
        return subject.removeprefix("persona:")
    if subject in PERSONAS:
        return subject
    digest = int.from_bytes(hashlib.sha256(f"finance:{subject}".encode()).digest()[:8], "big")
    return PERSONA_IDS[digest % len(PERSONA_IDS)]


def _info(p: Persona) -> PersonaInfo:
    return PersonaInfo(
        id=p.id, label=p.label, name=p.name, sex=p.sex, birth_year=p.birth_year, occupation=p.occupation,
        region=p.region, town=p.town, postcode=p.postcode, gross_salary=p.gross_salary, housing=p.housing,
        monthly_rent=p.rent, unused_subscriptions=p.unused_subscriptions, notes=p.notes,
    )


def persona_for_subject(subject: str) -> PersonaInfo:
    return _info(PERSONAS[persona_id_for_subject(subject)])


def persona_info(persona_id: str) -> PersonaInfo:
    return _info(PERSONAS[persona_id])


@lru_cache(maxsize=32)
def _cached(persona_id: str, as_of: date) -> FinanceSnapshot:
    return build_snapshot(PERSONAS[persona_id], as_of)


def fixture_snapshot(subject: str, as_of: date | None = None) -> FinanceSnapshot:
    """Labelled sample FinanceSnapshot for a user subject. Returns a fresh copy (callers may mutate it)."""
    return _cached(persona_id_for_subject(subject), as_of or FIXTURE_AS_OF).model_copy(deep=True)


__all__ = [
    "DEMO_DEVICE_ID",
    "DEMO_PERSONA_ID",
    "DEMO_SUBJECT",
    "FIXTURE_AS_OF",
    "HISTORY_DAYS",
    "PERSONA_IDS",
    "PersonaInfo",
    "demo_subject",
    "fixture_snapshot",
    "persona_for_subject",
    "persona_id_for_subject",
    "persona_info",
]
