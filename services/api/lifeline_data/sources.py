"""Registry of every data source in BUILD_SPEC section 2.

`tier` is the build tier that adds a live adapter. Sources with no live adapter yet serve mock data.
`key_env` lists the environment variables that must be set; a missing one gives status "mock".
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

OGL = "Open Government Licence v3.0"

HOUR = 3600
DAY = 24 * HOUR


@dataclass(frozen=True)
class SourceInfo:
    id: str
    name: str
    coverage: str
    attribution: str
    licence: str
    ttl_seconds: int
    needs_key: bool = False
    key_env: tuple[str, ...] = ()
    tier: int = 0
    url: str = ""


SOURCES: dict[str, SourceInfo] = {
    s.id: s
    for s in (
        SourceInfo(
            "boe", "Bank of England Database", "UK",
            "Contains Bank of England data. Source: Bank of England Interactive Database.",
            "Bank of England terms of use (free reuse with attribution)", 6 * HOUR,
            url="https://www.bankofengland.co.uk/boeapps/database/",
        ),
        SourceInfo(
            "ons", "Office for National Statistics", "UK",
            "Source: Office for National Statistics licensed under the Open Government Licence v3.0.",
            OGL, 12 * HOUR, url="https://www.ons.gov.uk/",
        ),
        SourceInfo(
            "nomis", "Nomis (ONS labour market and Census)", "UK; Census tables England and Wales",
            "Source: Nomis, Office for National Statistics. Contains public sector information licensed "
            "under the Open Government Licence v3.0.",
            OGL, DAY, url="https://www.nomisweb.co.uk/",
        ),
        SourceInfo(
            "landregistry", "HM Land Registry UK House Price Index", "UK",
            "Contains HM Land Registry data. Crown copyright and database right. Licensed under the Open "
            "Government Licence v3.0.",
            OGL, DAY, url="https://landregistry.data.gov.uk/",
        ),
        SourceInfo(
            "postcodes", "postcodes.io", "UK",
            "postcodes.io. Contains OS data, Royal Mail data and ONS data. Crown copyright and database right.",
            OGL, 30 * DAY, url="https://postcodes.io/",
        ),
        SourceInfo(
            "bankholidays", "GOV.UK bank holidays", "UK (England and Wales, Scotland, Northern Ireland)",
            "Contains public sector information licensed under the Open Government Licence v3.0 (GOV.UK).",
            OGL, DAY, tier=1, url="https://www.gov.uk/bank-holidays",
        ),
        SourceInfo(
            "frankfurter", "Frankfurter FX rates", "Global",
            "Exchange rates from Frankfurter, based on European Central Bank reference rates.",
            "Free to use (ECB reference rates)", HOUR, tier=1, url="https://www.frankfurter.app/",
        ),
        SourceInfo(
            "coingecko", "CoinGecko", "Global",
            "Data provided by CoinGecko.", "CoinGecko API terms (attribution required)", 15 * 60, tier=1,
            url="https://www.coingecko.com/",
        ),
        SourceInfo(
            "yahoo", "Yahoo Finance chart endpoint", "Global",
            "Market data from Yahoo Finance (unofficial endpoint).", "Yahoo terms of service; personal use",
            DAY, tier=1, url="https://finance.yahoo.com/",
        ),
        SourceInfo(
            "fred", "FRED, Federal Reserve Bank of St. Louis", "UK series (OECD)",
            "Source: OECD via FRED, Federal Reserve Bank of St. Louis.", "FRED terms of use", DAY, tier=1,
            url="https://fred.stlouisfed.org/",
        ),
        SourceInfo(
            "octopus", "Octopus Energy products API", "Great Britain",
            "Tariff data from Octopus Energy.", "Octopus Energy API terms", 6 * HOUR, tier=1,
            url="https://developer.octopus.energy/",
        ),
        SourceInfo(
            "carbonintensity", "Carbon Intensity API", "Great Britain",
            "Carbon Intensity API, National Energy System Operator.", "CC BY 4.0", 30 * 60, tier=1,
            url="https://carbonintensity.org.uk/",
        ),
        SourceInfo(
            "openmeteo", "Open-Meteo", "Global",
            "Weather data by Open-Meteo.com.", "CC BY 4.0", HOUR, tier=1, url="https://open-meteo.com/",
        ),
        SourceInfo(
            "police", "Police UK data API", "England, Wales and Northern Ireland",
            "Contains public sector information from data.police.uk licensed under the Open Government "
            "Licence v3.0.",
            OGL, 7 * DAY, tier=1, url="https://data.police.uk/",
        ),
        SourceInfo(
            "environmentagency", "Environment Agency flood monitoring API", "England",
            "This uses Environment Agency flood and river level data from the real-time data API (Beta).",
            OGL, 15 * 60, tier=1, url="https://environment.data.gov.uk/flood-monitoring/",
        ),
        SourceInfo(
            "companieshouse", "Companies House API", "UK",
            "Contains Companies House data licensed under the Open Government Licence v3.0.",
            OGL, DAY, needs_key=True, key_env=("COMPANIES_HOUSE_KEY",), tier=1,
            url="https://developer.company-information.service.gov.uk/",
        ),
        SourceInfo(
            "adzuna", "Adzuna jobs API", "UK",
            "Jobs data by Adzuna.", "Adzuna API terms", 6 * HOUR, needs_key=True,
            key_env=("ADZUNA_APP_ID", "ADZUNA_APP_KEY"), tier=1, url="https://developer.adzuna.com/",
        ),
        SourceInfo(
            "dvla", "DVLA Vehicle Enquiry Service", "Great Britain",
            "Contains public sector information licensed under the Open Government Licence v3.0 (DVLA).",
            OGL, DAY, needs_key=True, key_env=("DVLA_KEY",), tier=1,
            url="https://developer-portal.driver-vehicle-licensing.api.gov.uk/",
        ),
        SourceInfo(
            "dvsamot", "DVSA MOT history API", "Great Britain",
            "Contains public sector information licensed under the Open Government Licence v3.0 (DVSA).",
            OGL, DAY, needs_key=True, key_env=("DVSA_MOT_KEY",), tier=1,
            url="https://documentation.history.mot.api.gov.uk/",
        ),
        SourceInfo(
            "statxplore", "DWP Stat-Xplore", "Great Britain",
            "Source: Department for Work and Pensions, Stat-Xplore. Open Government Licence v3.0.",
            OGL, 7 * DAY, needs_key=True, key_env=("DWP_STATXPLORE_KEY",), tier=1,
            url="https://stat-xplore.dwp.gov.uk/",
        ),
        SourceInfo(
            "epc", "Energy Performance of Buildings register", "England and Wales",
            "Contains EPC data from the Department for Energy Security and Net Zero. Open Government "
            "Licence v3.0 (address data has extra terms).",
            OGL, 7 * DAY, needs_key=True, key_env=("EPC_KEY",), tier=1,
            url="https://epc.opendatacommunities.org/",
        ),
        SourceInfo(
            "openbanking", "Open Banking sandbox (TrueLayer)", "UK",
            "Sandbox account data via TrueLayer. Demo only.", "TrueLayer sandbox terms", 5 * 60,
            needs_key=True, key_env=("OB_CLIENT_ID", "OB_CLIENT_SECRET", "OB_REDIRECT_URI"), tier=1,
            url="https://docs.truelayer.com/",
        ),
    )
}


def missing_keys(source: SourceInfo, env: Mapping[str, str]) -> list[str]:
    """Names (never values) of required env vars that are unset or empty."""
    return [name for name in source.key_env if not env.get(name)]
