"""Transaction categorisation (ADR 0016). Merchant table plus keyword rules. No LLM.

Order of rules for one transaction:
1. Money in (amount > 0): salary and student-funding words (loan, grant, bursary, family) give
   `income`; transfer words give `transfers`; a known merchant gives that merchant's category
   (a refund); anything else is `income`.
2. Money out: savings words (incl. "... pot", a Monzo pot transfer) give `savings`; then a known
   merchant (longest key over the merchant field and the description), then keyword rules on the
   description, then the bank's own label (`provider_category`), else `other`.
Matching is on lower case text. Longer keys win, so "amazon prime" beats "amazon".
"""

from __future__ import annotations

import re

from lifeline_contracts.finance import Category, Transaction
from lifeline_engine.money.text import clean_name

# (label, emoji) per category.
CATEGORY_INFO: dict[Category, tuple[str, str]] = {
    "groceries": ("Groceries", "🛒"),
    "eating_out": ("Eating out", "🍔"),
    "transport": ("Transport", "🚆"),
    "shopping": ("Shopping", "🛍️"),
    "entertainment": ("Entertainment", "🎬"),
    "bills": ("Bills", "💡"),
    "housing": ("Housing", "🏠"),
    "subscriptions": ("Subscriptions", "🔁"),
    "health": ("Health", "💊"),
    "travel": ("Travel", "✈️"),
    "personal_care": ("Personal care", "💇"),
    "education": ("Education", "🎓"),
    "gifts": ("Gifts", "🎁"),
    "transfers": ("Transfers", "↔️"),
    "income": ("Income", "💷"),
    "savings": ("Savings", "🐷"),
    "cash": ("Cash", "💵"),
    "fees": ("Fees", "🧾"),
    "other": ("Other", "📦"),
}

# Categories that count as spending. Transfers, savings and income do not.
NOT_SPENDING: frozenset[Category] = frozenset({"transfers", "income", "savings"})

_MERCHANTS: dict[str, Category] = {
    # groceries
    "tesco": "groceries",
    "sainsbury": "groceries",
    "asda": "groceries",
    "morrisons": "groceries",
    "aldi": "groceries",
    "lidl": "groceries",
    "waitrose": "groceries",
    "co-op": "groceries",
    "coop": "groceries",
    "iceland": "groceries",
    "ocado": "groceries",
    "m&s food": "groceries",
    "kirkgate market": "groceries",
    "m&s": "groceries",
    "marks & spencer": "groceries",
    "scotmid": "groceries",
    "wing yip": "groceries",
    "farmfoods": "groceries",
    "home bargains": "groceries",
    "b&m": "groceries",
    # eating out
    "pret": "eating_out",
    "greggs": "eating_out",
    "starbucks": "eating_out",
    "costa": "eating_out",
    "mcdonald": "eating_out",
    "kfc": "eating_out",
    "nando": "eating_out",
    "deliveroo": "eating_out",
    "just eat": "eating_out",
    "uber eats": "eating_out",
    "wagamama": "eating_out",
    "pizza": "eating_out",
    "wetherspoon": "eating_out",
    " pub ": "eating_out",
    "prince of wales": "eating_out",
    "domino": "eating_out",
    "subway": "eating_out",
    "burger king": "eating_out",
    "five guys": "eating_out",
    "dishoom": "eating_out",
    "mooboo": "eating_out",
    "caffe nero": "eating_out",
    "spoons": "eating_out",
    "stag and hounds": "eating_out",
    "tavern": "eating_out",
    " arms ": "eating_out",
    # students' union cafes, bars and shops: mostly food and drink
    "students' union": "eating_out",
    "students union": "eating_out",
    "student union": "eating_out",
    "students' association": "eating_out",
    "students' guild": "eating_out",
    "university union": "eating_out",
    " su bar": "eating_out",
    " su cafe": "eating_out",
    " su coffee": "eating_out",
    "yusu": "eating_out",
    "nusu": "eating_out",
    # transport
    "tfl": "transport",
    "trainline": "transport",
    "national rail": "transport",
    "uber": "transport",
    "lner": "transport",
    "avanti": "transport",
    "shell": "transport",
    "esso": "transport",
    "texaco": "transport",
    " bp ": "transport",
    "ringgo": "transport",
    "first bus": "transport",
    "stagecoach": "transport",
    "arriva": "transport",
    "northern trains": "transport",
    "gwr": "transport",
    "lime": "transport",
    "bee network": "transport",
    "metrolink": "transport",
    "tfgm": "transport",
    "bolt": "transport",
    "railcard": "transport",
    "go north east": "transport",
    "national express": "transport",
    "nxwm": "transport",
    "megabus": "transport",
    "scotrail": "transport",
    "lothian buses": "transport",
    # shopping
    "amazon": "shopping",
    "argos": "shopping",
    "john lewis": "shopping",
    "ikea": "shopping",
    "asos": "shopping",
    "primark": "shopping",
    "ebay": "shopping",
    "currys": "shopping",
    "zara": "shopping",
    "uniqlo": "shopping",
    "tiktok shop": "shopping",
    "klarna": "shopping",
    "clearpay": "shopping",
    "paypal pay in 3": "shopping",
    "apple store": "shopping",
    "jd sports": "shopping",
    "halfords": "shopping",
    "shein": "shopping",
    "depop": "shopping",
    "vinted": "shopping",
    "h&m": "shopping",
    "tk maxx": "shopping",
    "sports direct": "shopping",
    # entertainment
    "odeon": "entertainment",
    "vue": "entertainment",
    "cineworld": "entertainment",
    "ticketmaster": "entertainment",
    "steam": "entertainment",
    # nights out
    "nightclub": "entertainment",
    "timepiece": "entertainment",
    "revolution": "entertainment",
    "digital newcastle": "entertainment",
    "o2 academy": "entertainment",
    "bowling": "entertainment",
    # subscriptions
    "netflix": "subscriptions",
    "spotify": "subscriptions",
    "disney": "subscriptions",
    "amazon prime": "subscriptions",
    "prime video": "subscriptions",
    "apple.com": "subscriptions",
    "icloud": "subscriptions",
    "youtube": "subscriptions",
    "now tv": "subscriptions",
    "audible": "subscriptions",
    "xbox": "subscriptions",
    "playstation": "subscriptions",
    "puregym": "subscriptions",
    "the gym": "subscriptions",
    "gym group": "subscriptions",
    "microsoft": "subscriptions",
    "adobe": "subscriptions",
    "openai": "subscriptions",
    "chatgpt": "subscriptions",
    "patreon": "subscriptions",
    "strava": "subscriptions",
    "headspace": "subscriptions",
    "paramount": "subscriptions",
    "apple": "subscriptions",
    "disney+": "subscriptions",
    # bills
    "british gas": "bills",
    "octopus": "bills",
    "edf": "bills",
    "e.on": "bills",
    "eon": "bills",
    "ovo": "bills",
    "scottish power": "bills",
    "water": "bills",
    "council tax": "bills",
    "council": "bills",
    "bt group": "bills",
    "bt broadband": "bills",
    "sky": "bills",
    "virgin media": "bills",
    "vodafone": "bills",
    "o2": "bills",
    "ee limited": "bills",
    "three": "bills",
    "giffgaff": "bills",
    "tesco mobile": "bills",
    "tv licence": "bills",
    "aviva": "bills",
    "direct line": "bills",
    "admiral": "bills",
    "hyperoptic": "bills",
    "united utilities": "bills",
    "thames water": "bills",
    "tv licensing": "bills",
    " ee ": "bills",
    "smarty": "bills",
    "voxi": "bills",
    "lebara": "bills",
    " bills ": "bills",
    "bills share": "bills",
    # housing
    "rent": "housing",
    "letting": "housing",
    "landlord": "housing",
    "mortgage": "housing",
    "student lets": "housing",
    "unite students": "housing",
    "accommodation": "housing",
    # health
    "boots": "health",
    "pharmacy": "health",
    "dentist": "health",
    "bupa": "health",
    # travel
    "easyjet": "travel",
    "ryanair": "travel",
    "british airways": "travel",
    "airbnb": "travel",
    "booking.com": "travel",
    "premier inn": "travel",
    "travelodge": "travel",
    # personal care
    "barber": "personal_care",
    "hairdresser": "personal_care",
    "superdrug": "personal_care",
    # education
    "udemy": "education",
    "coursera": "education",
    "university": "education",
    "waterstones": "education",
    "blackwell": "education",
    "print shop": "education",
    "uni print": "education",
    # gifts
    "moonpig": "gifts",
    "funky pigeon": "gifts",
    "interflora": "gifts",
}
_MERCHANT_KEYS: tuple[str, ...] = tuple(sorted(_MERCHANTS, key=lambda k: (-len(k), k)))

_INCOME_WORDS = (
    "salary",
    "payroll",
    "wages",
    "pay from",
    "hmrc",
    "dwp",
    "pension payment",
    "interest",
    # student money in (same words as lifeline_data.statements.detect)
    "bursary",
    "scholarship",
    " grant",
    "student loans",
    "student finance",
    " slc ",
    "maintenance loan",
    "saas ",
    "allowance",
    "family support",
    "rider payment",
    "payout",
    " mum ",
    " dad ",
    " parents ",
    "rent help",
)
_TRANSFER_WORDS = (
    "transfer",
    "from savings",
    "to savings",
    "from isa",
    "from current",
    "standing order from",
    "payment received",
)
_SAVINGS_OUT_WORDS = ("to savings", " isa ", "saver", "save the change", "savings pot", "round up", " pot ")
_CARD_LOAN_WORDS = (
    "credit card",
    "card payment to",
    "barclaycard",
    "amex",
    "american express",
    "vanquis payment",
    "loan",
)
_CASH_WORDS = ("atm", "cash withdrawal", "cashpoint")
_FEE_WORDS = ("fee", "overdraft", "charge")

_PROVIDER_MAP: dict[str, Category] = {
    "groceries": "groceries",
    "eating_out": "eating_out",
    "eating out": "eating_out",
    "restaurants": "eating_out",
    "transport": "transport",
    "shopping": "shopping",
    "entertainment": "entertainment",
    "bills": "bills",
    "bills_and_services": "bills",
    "utilities": "bills",
    "housing": "housing",
    "holidays": "travel",
    "travel": "travel",
    "personal_care": "personal_care",
    "health": "health",
    "education": "education",
    "gifts": "gifts",
    "cash": "cash",
    "charges": "fees",
    "fees": "fees",
    "income": "income",
    "savings": "savings",
    "transfers": "transfers",
    "subscriptions": "subscriptions",
}


def _norm(text: str | None) -> str:
    return f" {(text or '').lower().strip()} "


def _has(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


def merchant_category(text: str | None) -> Category | None:
    """Category of a known merchant named in `text`, else None."""
    t = _norm(text)
    for key in _MERCHANT_KEYS:
        if key in t:
            return _MERCHANTS[key]
    return None


def _merchant_of(tx: Transaction) -> Category | None:
    """Known merchant in the merchant field or the description. The longest key over both wins, so
    "Apple" + "APPLE STORE" is shopping and "University of York" + "ACCOMMODATION" is housing."""
    m, d = _norm(tx.merchant), _norm(tx.description)
    for key in _MERCHANT_KEYS:
        if key in m or key in d:
            return _MERCHANTS[key]
    return None


def categorise(tx: Transaction) -> Category:
    desc = _norm(tx.description)
    merchant = _merchant_of(tx)
    if tx.amount > 0:
        if _has(desc, _INCOME_WORDS):
            return "income"
        if _has(desc, _TRANSFER_WORDS):
            return "transfers"
        return merchant if merchant is not None else "income"
    if _has(desc, _SAVINGS_OUT_WORDS):
        return "savings"
    if _has(desc, _CARD_LOAN_WORDS):
        return "transfers"
    if merchant is not None:
        return merchant
    if _has(desc, _CASH_WORDS):
        return "cash"
    if _has(desc, ("transfer",)):
        return "transfers"
    if _has(desc, _FEE_WORDS):
        return "fees"
    if tx.provider_category:
        mapped = _PROVIDER_MAP.get(tx.provider_category.strip().lower())
        if mapped is not None:
            return mapped
    return "other"


_KEY_STRIP = re.compile(r"[^a-z& ]+")


def merchant_key(tx: Transaction) -> str:
    """Stable grouping key for one payee: the merchant name, else the description without digits and refs."""
    raw = (tx.merchant or tx.description).lower()
    cleaned = _KEY_STRIP.sub(" ", raw.replace(".com", " "))
    words = [w for w in cleaned.split() if len(w) > 1 or w == "&"]
    return " ".join(words[:3]) or raw.strip()


def display_name(tx: Transaction) -> str:
    """Name to show for a payee: the merchant field, else the description in title case. Untrusted text, so it
    is cleaned (no digits, %, currency signs or number words) before it reaches any engine text."""
    if tx.merchant:
        return clean_name(tx.merchant)
    return clean_name(" ".join(w.capitalize() for w in merchant_key(tx).split()) or tx.description)


def is_card_or_loan_payment(tx: Transaction) -> bool:
    return tx.amount < 0 and _has(_norm(tx.description), _CARD_LOAN_WORDS)


def label(category: Category) -> str:
    return CATEGORY_INFO[category][0]


def emoji(category: Category) -> str:
    return CATEGORY_INFO[category][1]
