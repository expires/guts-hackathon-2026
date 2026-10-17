"""Preset characters and the God Mode option lists.

`PresetExtras` holds start values that `CharacterSpec` has no field for (student loan,
pension pot, family). Lives built from a preset id get these extras; other lives get defaults.
"""

from __future__ import annotations

from dataclasses import dataclass

from lifeline_contracts.domain import CharacterSpec
from lifeline_contracts.observation import REGIONS


@dataclass(frozen=True)
class PresetExtras:
    job_title: str | None = None
    years_in_role: int = 0
    student_loan: float = 0.0
    pension: float = 0.0
    investments: float = 0.0
    smarts_bonus: int = 0
    has_car: bool | None = None
    has_partner: bool = False
    married: bool = False
    children: int = 0
    base_year: int = 2024  # the year the preset's money values describe


_PRESETS: list[tuple[CharacterSpec, PresetExtras]] = [
    (
        CharacterSpec(
            id="nurse-leeds",
            name="Amira",
            emoji="👩🏽‍⚕️",
            sex="female",
            occupation="nurse",
            region="yorkshire-and-the-humber",
            town="Leeds",
            birth_year=1982,
            annual_income=24800.0,
            savings=3200.0,
            debt=1500.0,
            housing="rent",
            blurb="NHS nurse renting in Leeds.",
        ),
        PresetExtras(
            job_title="Staff nurse",
            years_in_role=2,
            student_loan=18000.0,
            pension=4100.0,
            smarts_bonus=8,
            base_year=2006,
        ),
    ),
    (
        CharacterSpec(
            id="banker-london",
            name="Tom",
            emoji="👨🏻‍💼",
            sex="male",
            occupation="banker",
            region="london",
            town="London",
            birth_year=1979,
            annual_income=92000.0,
            savings=41000.0,
            debt=0.0,
            housing="mortgage",
            property_value=410000.0,
            mortgage_balance=290000.0,
            blurb="Investment banker with a flat in Canary Wharf.",
        ),
        PresetExtras(
            job_title="Associate",
            years_in_role=4,
            pension=38000.0,
            investments=25000.0,
            smarts_bonus=12,
            has_partner=True,
            base_year=2006,
        ),
    ),
    (
        CharacterSpec(
            id="student",
            name="Priya",
            emoji="🧑🏽‍🎓",
            sex="female",
            occupation="student",
            region="west-midlands",
            town="Birmingham",
            birth_year=2005,
            annual_income=7800.0,
            savings=600.0,
            debt=300.0,
            housing="rent",
            blurb="Second-year student with a weekend job.",
        ),
        PresetExtras(
            job_title="Bar staff (part time)", student_loan=27000.0, smarts_bonus=10, has_car=False, base_year=2024
        ),
    ),
    (
        CharacterSpec(
            id="plumber",
            name="Dan",
            emoji="👷🏼‍♂️",
            sex="male",
            occupation="plumber",
            region="north-west",
            town="Manchester",
            birth_year=1990,
            annual_income=36000.0,
            savings=5200.0,
            debt=4000.0,
            housing="rent",
            blurb="Self-employed plumber with a van loan.",
        ),
        PresetExtras(
            job_title="Plumber", years_in_role=8, pension=6000.0, has_car=True, has_partner=True, base_year=2022
        ),
    ),
    (
        CharacterSpec(
            id="pensioner",
            name="Maureen",
            emoji="👵🏻",
            sex="female",
            occupation="retired",
            region="south-west",
            town="Plymouth",
            birth_year=1950,
            annual_income=17500.0,
            savings=22000.0,
            debt=0.0,
            housing="own",
            property_value=245000.0,
            blurb="Retired teaching assistant who owns her home.",
        ),
        PresetExtras(job_title="Retired", pension=60000.0, married=True, has_partner=True, children=2, base_year=2022),
    ),
    (
        CharacterSpec(
            id="teacher-glasgow",
            name="Callum",
            emoji="👨🏻‍🏫",
            sex="male",
            occupation="teacher",
            region="scotland",
            town="Glasgow",
            birth_year=1988,
            annual_income=41000.0,
            savings=8000.0,
            debt=0.0,
            housing="mortgage",
            property_value=165000.0,
            mortgage_balance=120000.0,
            blurb="Secondary teacher in Glasgow. Some data uses the UK average.",
        ),
        PresetExtras(
            job_title="Maths teacher",
            years_in_role=6,
            student_loan=9000.0,
            pension=21000.0,
            smarts_bonus=10,
            base_year=2022,
        ),
    ),
]

_EXTRAS: dict[str, PresetExtras] = {c.id: e for c, e in _PRESETS if c.id is not None}
_DEFAULT_EXTRAS = PresetExtras()


def presets() -> list[CharacterSpec]:
    return [c.model_copy() for c, _ in _PRESETS]


def preset(preset_id: str) -> CharacterSpec | None:
    for c, _ in _PRESETS:
        if c.id == preset_id:
            return c.model_copy()
    return None


def is_unedited_preset(character: CharacterSpec) -> bool:
    """True when the character is a preset with its money values unchanged."""
    base = next((c for c, _ in _PRESETS if c.id is not None and c.id == character.id), None)
    if base is None:
        return False
    fields = ("annual_income", "savings", "debt", "property_value", "mortgage_balance", "region", "housing")
    return all(getattr(base, f) == getattr(character, f) for f in fields)


def preset_extras(character_id: str | None) -> PresetExtras:
    if character_id is None:
        return _DEFAULT_EXTRAS
    return _EXTRAS.get(character_id, _DEFAULT_EXTRAS)


# God Mode: the player picks one value from each list. Incomes are 2024 pounds, gross per year.
GOD_MODE_OCCUPATIONS: dict[str, float] = {
    "student": 7800.0,
    "care worker": 23500.0,
    "nurse": 33000.0,
    "teacher": 41000.0,
    "plumber": 36000.0,
    "electrician": 38000.0,
    "software developer": 55000.0,
    "doctor": 70000.0,
    "banker": 92000.0,
    "retired": 17500.0,
}
GOD_MODE_WEALTH: dict[str, float] = {"broke": 0.0, "some savings": 5000.0, "comfortable": 40000.0, "rich": 250000.0}


def god_mode_options() -> dict[str, list[str]]:
    return {
        "occupations": list(GOD_MODE_OCCUPATIONS),
        "regions": list(REGIONS),
        "wealth": list(GOD_MODE_WEALTH),
        "housing": ["parents", "rent", "own", "mortgage"],
    }
