"""Human names for sources in Ask Penny (ADR 0051): "Bank of England · savings rates · live".

Never show internal series codes (IUMB6VJ, NM_17_5). An unknown series shows the organisation name only.
"""

from __future__ import annotations

import re

from lifeline_contracts.domain import SourceRef
from lifeline_explain.official import nice_date, official_label

SEP = " · "

ORGS: dict[str, str] = {
    "boe": "Bank of England",
    "ons": "ONS",
    "nomis": "ONS Nomis",
    "landregistry": "HM Land Registry",
    "companieshouse": "Companies House",
    "octopus": "Octopus Energy",
    "frankfurter": "Exchange rates (ECB)",
    "coingecko": "CoinGecko",
    "yahoo": "Yahoo Finance",
    "fred": "FRED",
    "guardian": "The Guardian",
    "govuk": "GOV.UK",
    "gov.uk": "GOV.UK",
    "facts_table": "GOV.UK",
    "bankholidays": "GOV.UK bank holidays",
    "police": "Police UK",
    "environmentagency": "Environment Agency",
    "postcodes": "postcodes.io",
    "sim": "Penny game",
    "engine": "Penny engine",
}

SERIES: dict[str, str] = {
    # Bank of England
    "IUMBEDR": "Bank Rate",
    "IUMB6VJ": "savings rates",
    "IUMBV34": "2-year fixed mortgage rates",
    "IUMBV42": "5-year fixed mortgage rates",
    "IUMBV37": "3-year fixed mortgage rates",
    "IUMTLMV": "standard variable mortgage rates",
    "IUMBV48": "tracker mortgage rates",
    "IUMBV24": "lifetime tracker mortgage rates",
    "IUMCCTL": "credit card rates",
    # ONS and Nomis
    "D7G7": "inflation (CPI)",
    "D7GT": "energy prices",
    "D7IO": "fuel prices",
    "PIPR": "rents",
    "IPHRP": "rents",
    "NM_30_1": "pay",
    "NM_17_5": "unemployment",
    "NM_2072_1": "home ownership",
    # Others
    "ukhpi-average-price": "house prices",
    "ukhpi-annual-change": "house price change",
    "IRLTLT01GBM156N": "10-year gilt yield",
    "^FTAS": "UK shares (FTSE All-Share)",
    "bitcoin": "Bitcoin price",
    "GBPUSD": "pound to dollar",
    "dual-fuel-typical-bill": "typical energy bill",
    "rates": "rates news",
}

STATUS: dict[str, str] = {"live": "live", "cached": "saved copy", "mock": "sample data", "unavailable": "unavailable"}


def _checked(note: str) -> str:
    """'2026/27, checked 2026-10-17' or 'checked 17 Oct 2026' -> 'checked 17 Oct 2026'."""
    m = re.search(r"checked (\d{4}-\d{2}-\d{2})", note)
    if m:
        return f"checked {nice_date(m.group(1))}"
    m = re.search(r"checked [^,;]+", note)
    return m.group(0).strip() if m else ""


def series_name(series_id: str) -> str | None:
    return SERIES.get(series_id) or SERIES.get(series_id.upper())


def source_label(ref: SourceRef) -> str:
    """Human label for a source chip. Never contains a series code."""
    src = ref.source.lower()
    status = STATUS.get(str(ref.status), "")
    if src.startswith(("bank:", "statement", "user", "profile", "finance")) or src == "bank":
        parts = ["Your money data", "sample data" if ref.status == "mock" else ""]
    elif src in {"govuk", "gov.uk", "facts_table", "official"} and ref.series_id.startswith("https://"):
        # ADR 0058: "gov.uk · Repaying your student loan · checked 17 Oct 2026"
        return official_label(ref.series_id, _checked(ref.note or ""))
    elif src in {"govuk", "gov.uk", "facts_table"}:
        parts = ["GOV.UK", ref.note or ""]
    elif src == "web":
        parts = [ref.note or "Web page", "web search"]
    else:
        org = ORGS.get(src, ref.source if ref.source.isalpha() else "Live data")
        name = series_name(ref.series_id)
        if name is None and src == "guardian":
            name = "news"
        parts = [org, name or "", status]
    return SEP.join(p for p in parts if p)[:120]
