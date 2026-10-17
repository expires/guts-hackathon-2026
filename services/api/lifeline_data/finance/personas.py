"""Labelled fixture personas for the Money tab (ADR 0016, ADR 0018). All data here is sample data.

Each persona is a plain description. `generator.py` turns it into 12 months of transactions.
Amounts are GBP. Merchant names are real UK brands so categorisation rules see realistic text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from lifeline_contracts.finance import EnergyDetails, MortgageDetails

DEMO_DEVICE_ID = "demo-presenter-01"
DEMO_PERSONA_ID = "homeowner-leeds"


@dataclass(frozen=True)
class Sub:
    """A subscription. `rise` = (first date of the new price, new amount)."""

    merchant: str
    description: str
    amount: float
    day: int
    cadence: str = "monthly"  # monthly | yearly
    month: int | None = None  # yearly only
    rise: tuple[date, float] | None = None
    starts: date | None = None
    card: bool = False  # charged to the credit card, not the current account


@dataclass(frozen=True)
class Bill:
    merchant: str
    description: str
    amount: float
    day: int
    months: tuple[int, ...] | None = None  # None = every month
    kind: str = "DIRECT_DEBIT"


@dataclass(frozen=True)
class Shop:
    """One merchant in the discretionary spend mix. Amount is lognormal around `mean`."""

    merchant: str
    description: str
    weight: float
    mean: float
    spread: float = 0.35
    rainy: float = 1.0  # weight multiplier on a wet day
    warm: float = 1.0  # weight multiplier on a warm day (max >= 21 C)


@dataclass(frozen=True)
class Card:
    provider: str
    name: str
    apr_pct: float
    balance: float  # final balance, negative = owed
    purchase_share: float  # share of discretionary spend paid by card
    payment: float  # monthly payment from the current account
    payment_day: int = 20


@dataclass(frozen=True)
class Persona:
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
    net_pay: float
    employer: str
    housing: str  # rent | mortgage
    bank: str
    current_balance: float
    savings_provider: str
    savings_name: str
    savings_balance: float
    savings_rate_pct: float
    savings_transfer: float
    daily_spend: float  # mean discretionary spend per day before multipliers, GBP
    shops: tuple[Shop, ...]
    bills: tuple[Bill, ...]
    subs: tuple[Sub, ...]
    energy: EnergyDetails
    rent: float | None = None
    landlord: str | None = None
    rent_day: int = 1
    mortgage: MortgageDetails | None = None
    mortgage_day: int = 1
    card: Card | None = None
    isa_balance: float = 0.0
    pension_balance: float = 0.0
    overdraft_fee: float = 0.0
    unused_subscriptions: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default=())


def _groceries(*extra: Shop) -> tuple[Shop, ...]:
    return (
        Shop("Tesco", "TESCO STORES", 9, 32.0, 0.6),
        Shop("Sainsbury's", "SAINSBURYS S/MKTS", 5, 28.0, 0.6),
        Shop("Aldi", "ALDI", 4, 24.0, 0.5),
        Shop("Lidl", "LIDL GB", 3, 19.0, 0.5),
        Shop("Co-op", "CO-OP GROUP FOOD", 3, 8.5, 0.5),
        *extra,
    )


def _common_spend() -> tuple[Shop, ...]:
    return (
        Shop("Greggs", "GREGGS", 4, 4.6, 0.3, warm=0.9),
        Shop("Costa Coffee", "COSTA COFFEE", 4, 4.1, 0.25, rainy=1.1),
        Shop("Boots", "BOOTS", 2, 12.0, 0.6),
        Shop("Amazon", "AMAZON.CO.UK", 3, 21.0, 0.7, rainy=1.3),
        Shop("Deliveroo", "DELIVEROO", 2, 24.0, 0.3, rainy=1.8, warm=0.7),
        Shop("Nando's", "NANDOS", 1, 31.0, 0.3),
        Shop("Superdrug", "SUPERDRUG", 1, 9.0, 0.5),
        Shop("Primark", "PRIMARK", 1, 26.0, 0.5),
        Shop("Shell", "SHELL", 1.5, 52.0, 0.25),
        Shop("Vue Cinemas", "VUE CINEMAS", 0.6, 19.0, 0.3, rainy=1.4),
        Shop("Cash", "CASH WITHDRAWAL", 0.6, 40.0, 0.2),
    )


PERSONAS: dict[str, Persona] = {}


def _register(p: Persona) -> Persona:
    PERSONAS[p.id] = p
    return p


# 1. Demo persona (device demo-presenter-01). Fixed deal ends 2027-03-31: 165 days after 2026-10-17.
_register(
    Persona(
        id=DEMO_PERSONA_ID,
        label="Homeowner with a mortgage (Leeds)",
        name="Priya",
        sex="female",
        birth_year=1988,
        occupation="Marketing manager",
        region="yorkshire-and-the-humber",
        town="Leeds",
        postcode="LS6 1AN",
        gross_salary=38_000.0,
        net_pay=2_486.32,
        employer="NORTHGATE MEDIA LTD",
        housing="mortgage",
        bank="Lloyds",
        current_balance=1_243.18,
        savings_provider="Halifax",
        savings_name="Everyday Saver",
        savings_balance=6_850.42,
        savings_rate_pct=1.25,
        savings_transfer=150.0,
        daily_spend=23.0,
        mortgage=MortgageDetails(
            balance=180_000.0,
            rate_pct=2.09,
            rate_type="fixed",
            fixed_until="2027-03-31",
            years_left=23,
            property_value=240_000.0,
            monthly_payment=822.03,
            lender="Nationwide",
        ),
        energy=EnergyDetails(
            supplier="Octopus Energy", tariff="Flexible Octopus", monthly_cost=142.0, fixed_until=None
        ),
        card=Card("Barclaycard", "Barclaycard Platinum", 24.9, -3_420.55, 0.30, 360.0),
        pension_balance=41_200.0,
        shops=(
            *_groceries(Shop("Morrisons", "WM MORRISONS", 5, 31.0, 0.6)),
            *_common_spend(),
            Shop("Northern Trains", "NORTHERN TRAINS", 2, 8.9, 0.4),
            Shop("First Bus", "FIRST WEST YORKSHIRE", 2, 5.2, 0.2, rainy=1.3),
            Shop("Kirkgate Market", "KIRKGATE MARKET LEEDS", 0.8, 11.0, 0.4, rainy=0.6),
            Shop("Wetherspoons", "JD WETHERSPOON", 1.5, 18.0, 0.4, warm=1.6),
        ),
        bills=(
            Bill("Leeds City Council", "LEEDS CITY COUNCIL CTAX", 191.0, 1, months=(4, 5, 6, 7, 8, 9, 10, 11, 12, 1)),
            Bill("Yorkshire Water", "YORKSHIRE WATER", 41.5, 15),
            Bill("Virgin Media", "VIRGIN MEDIA", 38.0, 12),
            Bill("EE", "EE LIMITED", 22.0, 18),
            Bill("TV Licensing", "TV LICENCE MBP", 14.54, 1),
            Bill("Admiral", "ADMIRAL INSURANCE", 52.37, 5),
        ),
        subs=(
            Sub("Netflix", "NETFLIX.COM", 12.99, 9, rise=(date(2026, 6, 1), 13.99)),
            Sub("Spotify", "SPOTIFY UK", 12.99, 14),
            Sub("Amazon Prime", "AMAZON PRIME", 8.99, 21, card=True),
            Sub("Disney+", "DISNEY PLUS", 9.99, 3),
            Sub("PureGym", "PUREGYM LTD", 27.99, 1),
            Sub("iCloud", "APPLE.COM/BILL", 2.99, 25),
        ),
        unused_subscriptions=("Disney+", "PureGym"),
        notes=(
            "Fixed mortgage deal ends 2027-03-31.",
            "Netflix rose from 12.99 to 13.99 in June 2026.",
            "Disney+ and PureGym: no related spending, likely unused.",
            "Credit card balance at 24.9% APR while savings earn 1.25%.",
        ),
    )
)

# 2. Renter who saves. London, high rent, good habits, cash in a low-rate account.
_register(
    Persona(
        id="renter-saver-london",
        label="Renter who saves (London)",
        name="Tom",
        sex="male",
        birth_year=1996,
        occupation="Software tester",
        region="london",
        town="London",
        postcode="SW9 8DA",
        gross_salary=45_000.0,
        net_pay=2_874.11,
        employer="CITYLINE DIGITAL LTD",
        housing="rent",
        bank="Monzo",
        current_balance=2_105.67,
        savings_provider="NatWest",
        savings_name="Instant Saver",
        savings_balance=14_320.0,
        savings_rate_pct=1.1,
        savings_transfer=400.0,
        daily_spend=15.0,
        rent=1_650.0,
        landlord="J SMITH LETTINGS",
        rent_day=1,
        isa_balance=8_400.0,
        pension_balance=18_900.0,
        energy=EnergyDetails(
            supplier="British Gas", tariff="Fixed Price Jan 2027", monthly_cost=74.0, fixed_until="2027-01-31"
        ),
        shops=(
            *_groceries(Shop("Waitrose", "WAITROSE", 2, 27.0, 0.5)),
            Shop("Pret A Manger", "PRET A MANGER", 6, 6.4, 0.3),
            Shop("TfL", "TFL TRAVEL CH", 10, 7.9, 0.25),
            Shop("Costa Coffee", "COSTA COFFEE", 2, 4.0, 0.25),
            Shop("Boots", "BOOTS", 1.5, 11.0, 0.6),
            Shop("Amazon", "AMAZON.CO.UK", 1.5, 18.0, 0.7, rainy=1.3),
            Shop("Wagamama", "WAGAMAMA", 1, 22.0, 0.3),
            Shop("Uniqlo", "UNIQLO", 0.6, 35.0, 0.4),
            Shop("Lime", "LIME*RIDE", 1, 4.5, 0.3, rainy=0.4, warm=1.5),
            Shop("The Prince of Wales", "PRINCE OF WALES SW9", 1.5, 21.0, 0.4, warm=1.7),
        ),
        bills=(
            Bill("Lambeth Council", "LB LAMBETH CTAX", 158.0, 1, months=(4, 5, 6, 7, 8, 9, 10, 11, 12, 1)),
            Bill("Thames Water", "THAMES WATER", 33.0, 10),
            Bill("Hyperoptic", "HYPEROPTIC LTD", 30.0, 8),
            Bill("Giffgaff", "GIFFGAFF", 10.0, 20, kind="PURCHASE"),
            Bill("TV Licensing", "TV LICENCE MBP", 14.54, 1),
        ),
        subs=(
            Sub("Spotify", "SPOTIFY UK", 12.99, 6),
            Sub("Netflix", "NETFLIX.COM", 5.99, 17),
            Sub("Strava", "STRAVA", 54.99, 11, cadence="yearly", month=3),
        ),
        notes=("Large balance in an instant saver at 1.1%.", "Energy fixed until 2027-01-31."),
    )
)

# 3. Subscription creep. Manchester renter with many streaming and app subscriptions.
_register(
    Persona(
        id="subscription-creep-manchester",
        label="Too many subscriptions (Manchester)",
        name="Jordan",
        sex="male",
        birth_year=1993,
        occupation="Nurse",
        region="north-west",
        town="Manchester",
        postcode="M14 6HP",
        gross_salary=34_000.0,
        net_pay=2_301.48,
        employer="MANCHESTER UNIVERSITY NHS FT",
        housing="rent",
        bank="Santander",
        current_balance=612.40,
        savings_provider="Santander",
        savings_name="Easy Access Saver",
        savings_balance=1_150.0,
        savings_rate_pct=1.5,
        savings_transfer=50.0,
        daily_spend=21.0,
        rent=1_050.0,
        landlord="NORTHERN HOMES LETTINGS",
        rent_day=2,
        pension_balance=22_300.0,
        energy=EnergyDetails(supplier="EDF", tariff="Standard Variable", monthly_cost=98.0, fixed_until=None),
        shops=(
            *_groceries(Shop("Asda", "ASDA STORES", 4, 29.0, 0.6)),
            *_common_spend(),
            Shop("Bee Network", "BEE NETWORK BUS", 4, 2.0, 0.05, rainy=1.3),
            Shop("Metrolink", "TFGM METROLINK", 2, 4.2, 0.3),
            Shop("Steam", "STEAM PURCHASE", 0.6, 14.0, 0.6, rainy=1.5),
        ),
        bills=(
            Bill("Manchester City Council", "MANCHESTER CC CTAX", 142.0, 1, months=(4, 5, 6, 7, 8, 9, 10, 11, 12, 1)),
            Bill("United Utilities", "UNITED UTILITIES", 36.0, 12),
            Bill("Sky Broadband", "SKY DIGITAL", 32.0, 16),
            Bill("Vodafone", "VODAFONE LTD", 28.0, 22),
        ),
        subs=(
            Sub("Netflix", "NETFLIX.COM", 12.99, 4, rise=(date(2026, 6, 1), 13.99)),
            Sub("Spotify", "SPOTIFY UK", 19.99, 7, rise=(date(2026, 4, 1), 21.99)),
            Sub("Disney+", "DISNEY PLUS", 9.99, 11),
            Sub("Amazon Prime", "AMAZON PRIME", 8.99, 13),
            Sub("Apple One", "APPLE.COM/BILL", 18.95, 15),
            Sub("NOW", "NOW TV", 9.99, 19),
            Sub("Xbox Game Pass", "MICROSOFT*XBOX", 14.99, 23),
            Sub("Audible", "AUDIBLE UK", 7.99, 26),
            Sub("Headspace", "HEADSPACE", 9.99, 27),
            Sub("The Gym Group", "THE GYM GROUP", 24.99, 1),
            Sub("Microsoft 365", "MICROSOFT 365", 84.99, 9, cadence="yearly", month=2),
            Sub("Paramount+", "PARAMOUNT PLUS", 6.99, 5, starts=date(2026, 7, 5)),
        ),
        unused_subscriptions=("Headspace", "Audible"),
        notes=("12 subscriptions. Netflix and Spotify rose in 2026.",),
    )
)

# 4. Overspender. Bristol renter with an overdraft, buy-now-pay-later and an expensive card.
_register(
    Persona(
        id="overspender-bristol",
        label="Spending more than income (Bristol)",
        name="Megan",
        sex="female",
        birth_year=1999,
        occupation="Retail supervisor",
        region="south-west",
        town="Bristol",
        postcode="BS6 5QA",
        gross_salary=29_000.0,
        net_pay=2_011.87,
        employer="HARBOURSIDE RETAIL LTD",
        housing="rent",
        bank="Barclays",
        current_balance=-386.20,
        savings_provider="Barclays",
        savings_name="Rainy Day Saver",
        savings_balance=85.0,
        savings_rate_pct=1.0,
        savings_transfer=0.0,
        daily_spend=20.0,
        rent=925.0,
        landlord="CLIFTON LETTINGS",
        rent_day=1,
        pension_balance=6_100.0,
        overdraft_fee=15.0,
        energy=EnergyDetails(supplier="OVO Energy", tariff="Simpler Energy", monthly_cost=88.0, fixed_until=None),
        card=Card("Vanquis", "Vanquis Classic", 34.9, -4_810.0, 0.25, 260.0, payment_day=24),
        shops=(
            *_groceries(),
            *_common_spend(),
            Shop("ASOS", "ASOS.COM", 2, 38.0, 0.5, rainy=1.3),
            Shop("Klarna", "KLARNA*", 2, 29.0, 0.3),
            Shop("Uber", "UBER *TRIP", 3, 11.5, 0.4, rainy=1.6),
            Shop("Just Eat", "JUST EAT", 2, 22.0, 0.3, rainy=1.7),
            Shop("First Bus", "FIRST WEST OF ENGLAND", 2, 2.0, 0.05),
            Shop("Pub", "THE GRAPEVINE BRISTOL", 2, 24.0, 0.4, warm=1.7),
        ),
        bills=(
            Bill("Bristol City Council", "BRISTOL CITY COUNCIL", 152.0, 1, months=(4, 5, 6, 7, 8, 9, 10, 11, 12, 1)),
            Bill("Bristol Water", "BRISTOL WATER", 29.0, 14),
            Bill("BT", "BT GROUP PLC", 34.0, 9),
            Bill("Three", "THREE MOBILE", 31.0, 19),
        ),
        subs=(
            Sub("Netflix", "NETFLIX.COM", 12.99, 12),
            Sub("Spotify", "SPOTIFY UK", 12.99, 2),
            Sub("TikTok", "TIKTOK SHOP PLUS", 4.99, 16, card=True),
        ),
        notes=("Overdrawn most months. Card at 34.9% APR.",),
    )
)


PERSONA_IDS: tuple[str, ...] = tuple(PERSONAS)
