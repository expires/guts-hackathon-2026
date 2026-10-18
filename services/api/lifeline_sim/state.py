"""Internal life state. `Life` (the wire model) is a projection of this.

The full state is never stored. It is rebuilt by replay from the seed, the character and
the recorded choices (see `lifeline_sim.replay`). That keeps `Life` within the contract and
makes rewind a replay with one choice changed.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from lifeline_contracts.domain import CharacterSpec, Event, Housing, LifeMode, Relationship
from lifeline_contracts.macro import MacroKey
from lifeline_sim import params as p
from lifeline_sim.index import IndexWeights, drawdown_fraction
from lifeline_sim.macroview import MacroView
from lifeline_sim.mortgage import monthly_payment
from lifeline_sim.paths import LoanPlan, path_living, start_path
from lifeline_sim.presets import is_unedited_preset, preset_extras
from lifeline_sim.quick import plan as quick_plan
from lifeline_sim.rng import rng
from lifeline_sim.setup import Setup
from lifeline_sim.tax import net_pay


@dataclass
class SimState:
    seed: int
    mode: LifeMode
    character: CharacterSpec
    region: str
    start_year: int
    year: int
    age: int
    alive: bool = True
    cause_of_death: str | None = None
    happiness: int = 70
    health: int = 85
    smarts: int = 55
    cash: float = 0.0
    savings: float = 0.0
    investments: float = 0.0
    crypto: float = 0.0
    pension: float = 0.0
    property_value: float = 0.0
    mortgage_balance: float = 0.0
    mortgage_rate: float | None = None
    mortgage_fixed_until: int | None = None
    mortgage_years_left: int = 0
    mortgage_tracker: bool = False  # the deal follows Bank Rate + TRACKER_MARGIN until mortgage_fixed_until
    other_debt: float = 0.0
    student_loan: float = 0.0
    income: float = 0.0  # gross per year (wage when employed, pension income when retired)
    employed: bool = True
    retired: bool = False
    student: bool = False
    job_title: str = ""
    years_in_role: int = 0
    housing: Housing = "rent"
    rent: float = 0.0  # per month
    living: float = 0.0  # per month, all costs except housing
    has_car: bool = True
    energy_fixed_until: int = 0  # last year of a fixed energy deal; 0 = no fix
    has_partner: bool = False
    married: bool = False
    children: int = 0
    relationships: list[Relationship] = field(default_factory=list)
    # Index tracking
    nw0: float = 0.0
    income0: float = 0.0
    peak: float = 0.0
    max_dd: float = 0.0
    missed: int = 0
    # Last year, for history text
    last_net_income: float = 0.0
    last_costs: float = 0.0
    last_missed: int = 0
    last_bonus: float = 0.0  # gross bonus paid this year
    last_bonus_net: float = 0.0
    last_bankrupt: bool = False
    last_forced_sale: bool = False
    last_graduated: bool = False
    pending: list[Event] = field(default_factory=list)
    focus_tags: tuple[str, ...] = ()  # scenario setup, see lifeline_sim.setup
    focus_until: int | None = None  # focus applies up to this year (the scenario end year)
    data_gaps: dict[int, list[str]] = field(default_factory=dict)  # year -> macro names a step skipped (ADR 0027)
    last_fired: dict[str, int] = field(default_factory=dict)  # template id -> last year it fired (cooldown)
    # Running totals since the start year, for `api.scenario_cost` ("Test it", ADR 0018).
    mortgage_paid: float = 0.0  # mortgage payments
    card_interest_paid: float = 0.0  # interest charged on card debt
    savings_interest: float = 0.0  # interest earned on savings
    energy_paid: float = 0.0  # typical yearly energy bill (ENERGY_TARIFF) for each year lived
    tag_cost: dict[str, float] = field(default_factory=dict)  # one-off costs of tagged event choices
    tag_living: dict[str, float] = field(default_factory=dict)  # monthly living change from tagged choices
    # Student paths and Quick Life (ADR 0052). See lifeline_sim.paths and lifeline_sim.quick.
    path_id: str | None = None
    quick: bool = False
    quick_stops: tuple[int, ...] = ()
    quick_event_years: tuple[int, ...] = ()
    quick_end_year: int | None = None
    loan_plan: LoanPlan | None = None  # student loan plan from the rules table; None = legacy Plan 2 constants
    study_kind: str | None = None  # "ug" or "pg" while studying on a path
    pg_loan: float = 0.0  # postgraduate loan balance (repaid at its own rate and threshold)
    last_loan_repaid: float = 0.0  # student and postgraduate loan repaid this year
    # Game ledger for the habit score (path lives): (year, take-home money, spending, wants spending,
    # missed payments in months).
    ledger: list[tuple[int, float, float, float, int]] = field(default_factory=list)
    bursary_2024: float = 0.0  # premade Quick Life student's bursary a study year, 2024 pounds
    want_adj: float = 0.0  # change to weekly wants spending from choices, 2024 pounds (path lives)
    living_adj: float = 0.0  # monthly living change from choices (path lives rebuild living each year)
    want_spend: float = 0.0  # one-off spending on wants (choices of templates tagged "want") not yet in the ledger

    def clone(self) -> SimState:
        return copy.deepcopy(self)

    @property
    def net_worth(self) -> float:
        return (
            self.cash
            + self.savings
            + self.investments
            + self.crypto
            + self.pension
            + self.property_value
            - self.mortgage_balance
            - self.other_debt
            - self.student_loan
            - self.pg_loan
        )

    @property
    def mortgage_payment(self) -> float:
        if self.mortgage_balance <= 0 or self.mortgage_years_left <= 0:
            return 0.0
        return monthly_payment(self.mortgage_balance, max(0.0, self.mortgage_rate or 0.0), self.mortgage_years_left)

    @property
    def housing_monthly(self) -> float:
        if self.housing == "rent":
            return self.rent
        if self.housing == "mortgage":
            return self.mortgage_payment
        return 0.0

    @property
    def monthly_costs(self) -> float:
        return self.housing_monthly + self.living

    def track_drawdown(self, w: IndexWeights) -> None:
        nw = self.net_worth
        self.peak = max(self.peak, nw)
        self.max_dd = max(self.max_dd, drawdown_fraction(self.peak, nw, self.income0, w))


def _clamp_stat(x: float) -> int:
    return int(max(0, min(100, round(x))))


def initial_state(
    character: CharacterSpec,
    mode: LifeMode,
    start_year: int,
    seed: int,
    mv: MacroView,
    w: IndexWeights,
    setup: Setup | None = None,
) -> SimState:
    """Build the state at the start year from the character, the setup and the macro data."""
    setup = setup or Setup()
    age = start_year - character.birth_year
    region = character.region
    extras = preset_extras(character.id)
    r = rng(seed, "init")
    retired = age >= p.STATE_PENSION_AGE
    employed = not retired and character.annual_income > 0
    # V5: a preset's money values describe its base year. Other start years scale them with
    # regional pay (income), CPI (cash, debts, pots) and regional house prices (home, mortgage).
    pay_x = price_x = house_x = 1.0
    if is_unedited_preset(character) and start_year != extras.base_year:
        pay_x = _ratio(mv, MacroKey.MEDIAN_PAY, start_year, extras.base_year, region)
        price_x = mv.price_level(start_year) / mv.price_level(extras.base_year)
        house_x = _ratio(mv, MacroKey.HOUSE_PRICE, start_year, extras.base_year, region)
    s = SimState(
        seed=seed,
        mode=mode,
        character=character,
        region=region,
        start_year=start_year,
        year=start_year,
        age=age,
        happiness=_clamp_stat(70 + r.randint(-6, 6)),
        health=_clamp_stat(92 - max(0, age - 35) * 0.8 + r.randint(-5, 5)),
        smarts=_clamp_stat(55 + extras.smarts_bonus + r.randint(-8, 8)),
        savings=round(character.savings * price_x, 2),
        other_debt=round(character.debt * price_x, 2),
        income=round(character.annual_income * pay_x, 2),
        employed=employed,
        retired=retired,
        student=character.occupation.strip().lower() == "student" and age < p.GRADUATION_AGE,
        job_title=extras.job_title or character.occupation.capitalize(),
        years_in_role=extras.years_in_role,
        housing=character.housing,
        property_value=round(character.property_value * house_x, 2),
        mortgage_balance=round(character.mortgage_balance * house_x, 2),
        student_loan=round(extras.student_loan * price_x, 2),
        pension=round(extras.pension * price_x, 2),
        investments=round(extras.investments * price_x, 2),
        has_car=extras.has_car if extras.has_car is not None else region != "london",
        has_partner=extras.has_partner,
        married=extras.married,
        children=extras.children,
    )
    if s.housing == "mortgage" and s.mortgage_balance <= 0:
        s.housing = "own"
    if s.housing == "own" and s.mortgage_balance > 0:
        s.housing = "mortgage"
    if s.housing == "mortgage":
        s.mortgage_rate = _rate(mv, MacroKey.MORTGAGE_2Y_FIX, start_year)
        s.mortgage_fixed_until = start_year + p.FIRST_FIX_YEARS
        s.mortgage_years_left = max(10, min(p.DEFAULT_MORTGAGE_TERM, 67 - age))
        if setup.deal_end_year is not None:
            # The current fix was taken out 2 years before it ends (5 years when it ends later
            # than that), at the rate of that year, never later than the start year.
            fix_len = 2 if setup.deal_end_year - start_year <= 2 else 5
            key = MacroKey.MORTGAGE_2Y_FIX if fix_len == 2 else MacroKey.MORTGAGE_5Y_FIX
            struck = min(start_year, setup.deal_end_year - fix_len)
            s.mortgage_rate = _rate(mv, key, struck)
            s.mortgage_fixed_until = setup.deal_end_year
    s.focus_tags = setup.focus
    s.focus_until = setup.focus_until
    if setup.path is not None:
        start_path(s, setup.path, mv, setup.student)
        if setup.quick:
            qp = quick_plan(seed, start_year)
            s.quick = True
            s.quick_stops = qp.stops
            s.quick_event_years = qp.event_years
            s.quick_end_year = qp.end_year
    net_monthly = net_pay(s.income, s.employed) / 12
    price = mv.price_level(start_year)
    s.living = max(p.MIN_LIVING_MONTHLY_2024 * price, net_monthly * p.LIVING_SHARE_OF_NET)
    if s.housing == "parents":
        s.living *= 0.6
    if s.housing == "rent" and not (setup.path is not None and s.rent > 0):
        house_price = mv.value(MacroKey.HOUSE_PRICE, start_year, region, 200_000.0)
        s.rent = round(house_price * p.GROSS_RENT_YIELD / 12 * (p.STUDENT_RENT_SHARE if s.student else 1.0))
    if setup.path is not None:
        s.living, _ = path_living(s, mv)
    s.cash = round(net_monthly * p.STARTING_CASH_MONTHS)
    s.relationships = _initial_relationships(s)
    s.nw0 = s.net_worth
    s.income0 = s.income
    s.peak = s.nw0
    s.track_drawdown(w)
    return s


def _rate(mv: MacroView, key: MacroKey, year: int) -> float:
    """A quoted mortgage rate. Live gaps (before 1995) use the variable-rate rule: Bank Rate + margin."""
    v = mv.opt(key, year) if mv.strict else mv.value(key, year, None, 4.5)
    if v is not None:
        return v
    bank = mv.opt(MacroKey.BANK_RATE, year)
    return round((bank if bank is not None else 0.0) + p.VARIABLE_MARGIN, 2)


def _ratio(mv: MacroView, key: MacroKey, year: int, base_year: int, region: str) -> float:
    now = mv.value(key, year, region, 0.0)
    base = mv.value(key, base_year, region, 0.0)
    return now / base if now > 0 and base > 0 else 1.0


def _initial_relationships(s: SimState) -> list[Relationship]:
    rels: list[Relationship] = []
    if s.age < 60:
        rels.append(Relationship(id="rl-mum", kind="parent", name="Mum", emoji="👩", closeness=80))
    if s.age < 55:
        rels.append(Relationship(id="rl-dad", kind="parent", name="Dad", emoji="👨", closeness=70))
    if s.has_partner:
        kind = "spouse" if s.married else "partner"
        rels.append(Relationship(id="rl-partner", kind=kind, name="Partner", emoji="💑", closeness=80))
    rels.extend(
        Relationship(id=f"rl-child-{i + 1}", kind="child", name=f"Child {i + 1}", emoji="🧒", closeness=85)
        for i in range(s.children)
    )
    return rels
