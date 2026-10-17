"""Synthetic UK adult population by IPF (iterative proportional fitting).

IPF rescales a seed joint table, one marginal at a time, until every marginal matches its target.

Axes of the joint table (in order):
    region (12) x age band (6) x occupation group (9) x tenure (4) x income band (5)

Target marginals:
- region x tenure: region shares (seed) x owner-occupied share per region (MacroTable,
  Nomis Census NM_2072_1). Owners split into outright and mortgage, non-owners into rent and
  parents, with seed ratios.
- age band (seed).
- occupation group: seed shares, with the unemployed share set from MacroTable unemployment.
- income band (seed). Band edges are multiples of regional median pay (MacroTable, Nomis ASHE).

Seed marginals and affinities are embedded, rounded, Census-2021-like values. They are labelled
SEED_SOURCE and are approximations, not official statistics.

Pure: no I/O, no clock. Randomness only through a passed numpy Generator.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from lifeline_contracts.domain import CharacterSpec, Housing, Sex
from lifeline_contracts.macro import MacroKey, MacroTable
from lifeline_contracts.observation import REGIONS
from lifeline_engine.macro_access import latest_year, value_or

FloatArray = NDArray[np.float64]

SEED_SOURCE = "Embedded Census-2021-like seed marginals (rounded approximations)"

# ---------- axes ----------

AGE_BANDS: tuple[tuple[int, int], ...] = ((18, 24), (25, 34), (35, 44), (45, 54), (55, 64), (65, 79))
OCCUPATION_GROUPS: tuple[str, ...] = (
    "managers_professional",
    "associate_technical",
    "admin_sales",
    "skilled_trades",
    "care_leisure",
    "elementary",
    "unemployed",
    "student",
    "retired",
)
TENURES: tuple[Housing, ...] = ("own", "mortgage", "rent", "parents")
# Income bands as multiples of regional median annual pay.
INCOME_BANDS: tuple[tuple[float, float], ...] = ((0.15, 0.5), (0.5, 0.8), (0.8, 1.2), (1.2, 2.0), (2.0, 5.0))

AXES: tuple[str, ...] = ("region", "age_band", "occupation", "tenure", "income_band")

# ---------- seed marginals (percent, sum 100) ----------

SEED_REGION_SHARE: tuple[float, ...] = (4.0, 11.1, 8.2, 7.3, 8.9, 9.4, 13.1, 13.7, 8.5, 4.7, 8.2, 2.9)
SEED_AGE_SHARE: tuple[float, ...] = (11.0, 18.0, 17.0, 17.0, 17.0, 20.0)
# Working groups first, then unemployed, student, retired.
SEED_OCCUPATION_SHARE: tuple[float, ...] = (28.0, 12.0, 13.0, 9.0, 9.0, 9.0, 4.0, 5.0, 11.0)
SEED_INCOME_SHARE: tuple[float, ...] = (22.0, 18.0, 22.0, 24.0, 14.0)
SEED_OWNER_SHARE_PCT = 62.3  # used when the table has no owner_occupied_share
SEED_UNEMPLOYMENT_PCT = 4.5  # used when the table has no unemployment
SEED_MEDIAN_PAY = 35_000.0
SEED_HOUSE_PRICE = 285_000.0
OUTRIGHT_SHARE_OF_OWNERS = 0.52  # Census 2021 E&W: 32.5% outright vs 29.8% mortgage
PARENTS_SHARE_OF_NON_OWNERS = 0.12

# ---------- seed affinities (relative weights, > 0) ----------

_LOW = 0.01
# age band x tenure (own, mortgage, rent, parents)
AFF_AGE_TENURE: tuple[tuple[float, ...], ...] = (
    (0.05, 0.3, 2.0, 3.0),
    (0.1, 1.2, 2.0, 0.6),
    (0.3, 2.0, 1.2, 0.15),
    (0.8, 2.0, 0.9, 0.08),
    (2.0, 1.0, 0.8, 0.05),
    (4.0, 0.2, 0.8, 0.02),
)
# age band x occupation group
AFF_AGE_OCC: tuple[tuple[float, ...], ...] = (
    (0.3, 0.6, 1.4, 0.8, 1.4, 1.6, 1.5, 8.0, _LOW),
    (1.0, 1.1, 1.0, 1.0, 1.0, 1.0, 1.0, 0.6, _LOW),
    (1.2, 1.1, 1.0, 1.0, 1.0, 1.0, 0.9, 0.1, _LOW),
    (1.2, 1.0, 1.0, 1.0, 1.0, 1.0, 0.9, 0.05, 0.03),
    (1.0, 0.9, 1.0, 1.0, 1.0, 1.0, 1.0, 0.03, 0.6),
    (0.15, 0.1, 0.15, 0.15, 0.15, 0.15, 0.1, 0.01, 8.0),
)
# occupation group x income band
AFF_OCC_INCOME: tuple[tuple[float, ...], ...] = (
    (0.2, 0.4, 1.0, 2.5, 3.0),
    (0.3, 0.8, 2.0, 1.8, 0.4),
    (0.6, 2.0, 1.6, 0.5, 0.05),
    (0.4, 1.4, 2.0, 1.0, 0.1),
    (1.2, 2.5, 1.0, 0.2, _LOW),
    (1.5, 2.5, 0.7, 0.1, _LOW),
    (5.0, 0.3, 0.02, _LOW, _LOW),
    (5.0, 0.3, 0.02, _LOW, _LOW),
    (2.5, 1.5, 0.6, 0.2, 0.05),
)

OCCUPATION_TITLES: dict[str, tuple[str, ...]] = {
    "managers_professional": (
        "banker",
        "software engineer",
        "teacher",
        "solicitor",
        "accountant",
        "doctor",
        "architect",
        "marketing manager",
    ),
    "associate_technical": (
        "nurse",
        "paramedic",
        "IT technician",
        "police officer",
        "graphic designer",
        "estate agent",
    ),
    "admin_sales": ("office administrator", "sales assistant", "receptionist", "call centre adviser", "bank clerk"),
    "skilled_trades": ("plumber", "electrician", "mechanic", "chef", "carpenter", "hairdresser"),
    "care_leisure": ("care worker", "teaching assistant", "nursery worker", "fitness instructor"),
    "elementary": ("delivery driver", "cleaner", "warehouse operative", "bar staff", "farm worker"),
    "unemployed": ("job seeker",),
    "student": ("student",),
    "retired": ("retired",),
}

REGION_TOWNS: dict[str, str] = {
    "north-east": "Newcastle",
    "north-west": "Manchester",
    "yorkshire-and-the-humber": "Leeds",
    "east-midlands": "Nottingham",
    "west-midlands": "Birmingham",
    "east-of-england": "Norwich",
    "london": "London",
    "south-east": "Brighton",
    "south-west": "Bristol",
    "wales": "Cardiff",
    "scotland": "Glasgow",
    "northern-ireland": "Belfast",
}

FIRST_NAMES: dict[Sex, tuple[str, ...]] = {
    "female": (
        "Olivia",
        "Amelia",
        "Isla",
        "Ava",
        "Grace",
        "Freya",
        "Priya",
        "Aisha",
        "Chloe",
        "Sophie",
        "Emma",
        "Zara",
    ),
    "male": (
        "Oliver",
        "George",
        "Harry",
        "Noah",
        "Jack",
        "Leo",
        "Arjun",
        "Mohammed",
        "James",
        "Callum",
        "Liam",
        "Owen",
    ),
}
SURNAMES: tuple[str, ...] = (
    "Smith",
    "Jones",
    "Taylor",
    "Brown",
    "Williams",
    "Wilson",
    "Patel",
    "Khan",
    "Evans",
    "Thomas",
    "Roberts",
    "Campbell",
    "Murphy",
    "Walker",
)

# ---------- IPF ----------


def ipf(
    seed: FloatArray,
    margins: Sequence[tuple[tuple[int, ...], FloatArray]],
    tol: float = 1e-10,
    max_iter: int = 2000,
) -> FloatArray:
    """Fit `seed` to target marginals by iterative proportional fitting.

    Each margin is (axes, target). `axes` is a sorted tuple of axis indices. `target` has the
    shape of the seed restricted to those axes. All targets must have the same total.
    Cells that are 0 in the seed stay 0. Returns a new array; `seed` is not changed.
    """
    if seed.ndim == 0 or np.any(seed < 0):
        raise ValueError("seed must be a non-negative array with at least one axis")
    if not margins:
        return np.array(seed, dtype=np.float64, copy=True)
    totals = [float(t.sum()) for _, t in margins]
    for (axes, target), total in zip(margins, totals, strict=True):
        if tuple(sorted(axes)) != axes or len(set(axes)) != len(axes):
            raise ValueError("margin axes must be sorted and unique")
        expected = tuple(seed.shape[a] for a in axes)
        if target.shape != expected:
            raise ValueError(f"margin shape {target.shape} != {expected}")
        if np.any(target < 0):
            raise ValueError("margin targets must be >= 0")
        if not math.isclose(total, totals[0], rel_tol=1e-9, abs_tol=1e-12):
            raise ValueError("margin totals differ")

    x = np.array(seed, dtype=np.float64, copy=True)
    s = float(x.sum())
    if s <= 0:
        raise ValueError("seed total must be > 0")
    x *= totals[0] / s

    for _ in range(max_iter):
        for axes, target in margins:
            other = tuple(i for i in range(x.ndim) if i not in axes)
            current = x.sum(axis=other)
            factor = np.divide(target, current, out=np.zeros_like(current), where=current > 0)
            shape = tuple(x.shape[i] if i in axes else 1 for i in range(x.ndim))
            x *= factor.reshape(shape)
        if max_margin_error(x, margins) < tol:
            break
    return x


def max_margin_error(x: FloatArray, margins: Sequence[tuple[tuple[int, ...], FloatArray]]) -> float:
    """Largest absolute difference between the margins of `x` and the targets."""
    err = 0.0
    for axes, target in margins:
        other = tuple(i for i in range(x.ndim) if i not in axes)
        err = max(err, float(np.max(np.abs(x.sum(axis=other) - target))))
    return err


# ---------- population model ----------


@dataclass(frozen=True)
class Population:
    """Joint shares over AXES (sums to 1) plus the targets used to fit it."""

    year: int
    joint: FloatArray
    margins: tuple[tuple[tuple[int, ...], FloatArray], ...]
    median_pay: dict[str, float]
    house_price: dict[str, float]


@dataclass(frozen=True)
class Person:
    """One synthetic adult. Engine-internal; convert to CharacterSpec for the API."""

    region: str
    age: int
    sex: Sex
    occupation_group: str
    occupation: str
    housing: Housing
    annual_income: float
    savings: float
    debt: float
    property_value: float
    mortgage_balance: float


def _normalise(v: Sequence[float]) -> FloatArray:
    a = np.asarray(v, dtype=np.float64)
    return a / a.sum()


def seed_joint() -> FloatArray:
    """Seed table: product of the pairwise affinities. Strictly positive."""
    at = np.asarray(AFF_AGE_TENURE, dtype=np.float64)  # (age, tenure)
    ao = np.asarray(AFF_AGE_OCC, dtype=np.float64)  # (age, occ)
    oi = np.asarray(AFF_OCC_INCOME, dtype=np.float64)  # (occ, income)
    joint = ao[:, :, None, None] * at[:, None, :, None] * oi[None, :, None, :]  # (age, occ, tenure, income)
    full = np.broadcast_to(joint[None, ...], (len(REGIONS), *joint.shape))
    return np.array(full, dtype=np.float64, copy=True)


def target_margins(macro: MacroTable, year: int) -> tuple[tuple[tuple[int, ...], FloatArray], ...]:
    """Target marginals for IPF, from the MacroTable where available and seed values otherwise."""
    region_share = _normalise(SEED_REGION_SHARE)
    region_tenure = np.zeros((len(REGIONS), len(TENURES)), dtype=np.float64)
    for i, region in enumerate(REGIONS):
        owner = value_or(macro, MacroKey.OWNER_OCCUPIED_SHARE, year, region, SEED_OWNER_SHARE_PCT) / 100.0
        owner = min(0.99, max(0.01, owner))
        renter = 1.0 - owner
        shares = (
            owner * OUTRIGHT_SHARE_OF_OWNERS,
            owner * (1.0 - OUTRIGHT_SHARE_OF_OWNERS),
            renter * (1.0 - PARENTS_SHARE_OF_NON_OWNERS),
            renter * PARENTS_SHARE_OF_NON_OWNERS,
        )
        region_tenure[i] = region_share[i] * np.asarray(shares)

    occ = np.asarray(SEED_OCCUPATION_SHARE, dtype=np.float64) / 100.0
    unemployment = value_or(macro, MacroKey.UNEMPLOYMENT, year, None, SEED_UNEMPLOYMENT_PCT) / 100.0
    unemployment = min(0.5, max(0.0, unemployment))
    inactive = float(occ[7] + occ[8])  # student + retired
    active = 1.0 - inactive
    working_seed = occ[:6] / occ[:6].sum()
    occ_target = np.concatenate(
        [working_seed * active * (1.0 - unemployment), [active * unemployment], occ[7:9]]
    ).astype(np.float64)

    return (
        ((0, 3), region_tenure),
        ((1,), _normalise(SEED_AGE_SHARE)),
        ((2,), occ_target / occ_target.sum()),
        ((4,), _normalise(SEED_INCOME_SHARE)),
    )


def build_population(macro: MacroTable, year: int) -> Population:
    """Fit the synthetic population for `year`. Deterministic."""
    margins = target_margins(macro, year)
    joint = ipf(seed_joint(), margins)
    return Population(
        year=year,
        joint=joint,
        margins=margins,
        median_pay={r: value_or(macro, MacroKey.MEDIAN_PAY, year, r, SEED_MEDIAN_PAY) for r in REGIONS},
        house_price={r: value_or(macro, MacroKey.HOUSE_PRICE, year, r, SEED_HOUSE_PRICE) for r in REGIONS},
    )


def _person_from_cell(pop: Population, cell: tuple[int, ...], rng: np.random.Generator) -> Person:
    r_i, a_i, o_i, t_i, b_i = cell
    region = REGIONS[r_i]
    lo_age, hi_age = AGE_BANDS[a_i]
    age = int(rng.integers(lo_age, hi_age + 1))
    group = OCCUPATION_GROUPS[o_i]
    titles = OCCUPATION_TITLES[group]
    occupation = titles[int(rng.integers(len(titles)))]
    housing = TENURES[t_i]
    sex: Sex = "female" if rng.random() < 0.51 else "male"

    lo_m, hi_m = INCOME_BANDS[b_i]
    mult = math.exp(rng.uniform(math.log(lo_m), math.log(hi_m)))
    income = round(pop.median_pay[region] * mult, -2)

    saving_rate = 0.05 + 0.08 * a_i
    savings = round(min(5_000_000.0, income * saving_rate * float(rng.lognormal(0.0, 1.0))), -1)
    debt = round(income * float(rng.uniform(0.0, 0.4)), -1) if rng.random() < 0.45 else 0.0

    property_value = 0.0
    mortgage_balance = 0.0
    if housing in ("own", "mortgage"):
        property_value = round(pop.house_price[region] * float(rng.lognormal(0.0, 0.25)), -3)
    if housing == "mortgage":
        ltv = min(0.85, max(0.1, 0.8 - 0.02 * (age - 30)))
        mortgage_balance = round(property_value * ltv * float(rng.uniform(0.7, 1.0)), -3)

    return Person(
        region=region,
        age=age,
        sex=sex,
        occupation_group=group,
        occupation=occupation,
        housing=housing,
        annual_income=float(income),
        savings=float(savings),
        debt=float(debt),
        property_value=float(property_value),
        mortgage_balance=float(mortgage_balance),
    )


def sample_people(pop: Population, n: int, rng: np.random.Generator) -> list[Person]:
    """Draw `n` people from the population. Same rng state gives the same people."""
    if n < 0:
        raise ValueError("n must be >= 0")
    flat = pop.joint.ravel()
    p = flat / flat.sum()
    idx = rng.choice(flat.size, size=n, p=p)
    shape = pop.joint.shape
    return [_person_from_cell(pop, tuple(int(c) for c in np.unravel_index(int(i), shape)), rng) for i in idx]


def person_to_character(
    person: Person, year: int, rng: np.random.Generator, char_id: str | None = None
) -> CharacterSpec:
    first = FIRST_NAMES[person.sex]
    name = f"{first[int(rng.integers(len(first)))]} {SURNAMES[int(rng.integers(len(SURNAMES)))]}"
    emoji = (
        ("👩" if person.sex == "female" else "👨") if person.age < 65 else ("👵" if person.sex == "female" else "👴")
    )
    birth_year = min(2026, max(1930, year - person.age))
    town = REGION_TOWNS[person.region]
    return CharacterSpec(
        id=char_id,
        name=name,
        emoji=emoji,
        sex=person.sex,
        occupation=person.occupation,
        region=person.region,
        town=town,
        birth_year=birth_year,
        annual_income=person.annual_income,
        savings=person.savings,
        debt=person.debt,
        housing=person.housing,
        property_value=person.property_value,
        mortgage_balance=person.mortgage_balance,
        blurb=f"{person.age}-year-old {person.occupation} from {town}. Drawn from the synthetic UK population.",
    )


def random_character(seed: int, macro: MacroTable) -> CharacterSpec:
    """Draw one person from the synthetic UK population for the latest table year. Deterministic."""
    year = latest_year(macro)
    rng = np.random.default_rng(seed % 2**64)  # numpy needs a non-negative seed
    pop = build_population(macro, year)
    person = sample_people(pop, 1, rng)[0]
    return person_to_character(person, year, rng, char_id=f"random-{seed}")
