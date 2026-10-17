"""Transaction categorisation (ADR 0016). Merchant table plus keyword rules. No LLM.

Order of rules for one transaction:
1. Money in (amount > 0): salary words give `income`; transfer words give `transfers`;
   a known merchant gives that merchant's category (a refund); anything else is `income`.
2. Money out: known merchant (matched on the merchant field, then on the description),
   then keyword rules on the description, then the bank's own label (`provider_category`),
   else `other`.
Matching is on lower case text. Longer keys win, so "amazon prime" beats "amazon".
"""

from __future__ import annotations

import re

from lifeline_contracts.finance import Category, Transaction

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
    "bp ": "transport",
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
    # entertainment
    "odeon": "entertainment",
    "vue": "entertainment",
    "cineworld": "entertainment",
    "ticketmaster": "entertainment",
    "steam": "entertainment",
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
    # housing
    "rent": "housing",
    "letting": "housing",
    "landlord": "housing",
    "mortgage": "housing",
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
    # gifts
    "moonpig": "gifts",
    "funky pigeon": "gifts",
    "interflora": "gifts",
}
_MERCHANT_KEYS: tuple[str, ...] = tuple(sorted(_MERCHANTS, key=lambda k: (-len(k), k)))

_INCOME_WORDS = ("salary", "payroll", "wages", "pay from", "hmrc", "dwp", "pension payment", "interest")
_TRANSFER_WORDS = (
    "transfer",
    "from savings",
    "to savings",
    "from isa",
    "from current",
    "standing order from",
    "payment received",
)
_SAVINGS_OUT_WORDS = ("to savings", " isa ", "saver", "save the change", "savings pot", "round up")
_CARD_LOAN_WORDS = (
    "credit card", "card payment to", "barclaycard", "amex", "american express", "vanquis payment", "loan",
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


def categorise(tx: Transaction) -> Category:
    desc = _norm(tx.description)
    merchant = merchant_category(tx.merchant) or merchant_category(tx.description)
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
    """Name to show for a payee: the merchant field, else the description in title case."""
    if tx.merchant:
        return tx.merchant
    return " ".join(w.capitalize() for w in merchant_key(tx).split()) or tx.description


def is_card_or_loan_payment(tx: Transaction) -> bool:
    return tx.amount < 0 and _has(_norm(tx.description), _CARD_LOAN_WORDS)


def label(category: Category) -> str:
    return CATEGORY_INFO[category][0]


def emoji(category: Category) -> str:
    return CATEGORY_INFO[category][1]
