"""Key-needing sources. Keys come only from the environment (`Adapter.key`), are never logged, and never
appear in error messages. The hub checks keys first: a missing key gives labelled mock data.

- Companies House: HTTP basic auth, key as the username, blank password.
- EPC (get-energy-performance-data): `Authorization: Bearer <EPC_KEY>`.
- DWP Stat-Xplore: `APIKey: <DWP_STATXPLORE_KEY>` header, POST /table.
- Adzuna: app_id and app_key query parameters.
- DVLA Vehicle Enquiry: `x-api-key` header, POST.
- DVSA MOT history: `x-api-key` header plus an OAuth bearer token (`DVSA_MOT_TOKEN`, optional here).
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any, ClassVar

from lifeline_contracts.observation import Observation
from lifeline_data.base import Adapter, FetchError, PayloadError, parse_number, utcnow

COMPANIES_HOUSE_SEARCH_URL = "https://api.company-information.service.gov.uk/advanced-search/companies"
EPC_SEARCH_URL = "https://api.get-energy-performance-data.communities.gov.uk/api/domestic/search"
STATXPLORE_TABLE_URL = "https://stat-xplore.dwp.gov.uk/webapi/rest/v1/table"
ADZUNA_HISTORY_URL = "https://api.adzuna.com/v1/api/jobs/gb/history"
DVLA_URL = "https://driver-vehicle-licensing.api.gov.uk/vehicle-enquiry/v1/vehicles"
DVSA_MOT_URL = "https://history.mot.api.gov.uk/v1/trade/vehicles/registration/{reg}"

# Universal Credit monthly caseload (people on UC), Great Britain.
STATXPLORE_UC_QUERY: dict[str, Any] = {
    "database": "str:database:UC_Monthly",
    "measures": ["str:count:UC_Monthly:V_F_UC_CASELOAD_FULL"],
    "dimensions": [["str:field:UC_Monthly:F_UC_DATE:DATE_NAME"]],
}

# Region -> main council for EPC band shares (England and Wales only).
EPC_COUNCILS: dict[str, str] = {
    "north-east": "Newcastle upon Tyne",
    "north-west": "Manchester",
    "yorkshire-and-the-humber": "Leeds",
    "east-midlands": "Nottingham",
    "west-midlands": "Birmingham",
    "east-of-england": "Cambridge",
    "london": "Westminster",
    "south-east": "Reading",
    "south-west": "Bristol, City of",
    "wales": "Cardiff",
}

REG_RE = re.compile(r"^[A-Z0-9]{2,8}$")


def _json(payload: str | dict[str, Any] | list[Any]) -> Any:
    return json.loads(payload) if isinstance(payload, str) else payload


def parse_ch_hits(payload: str | dict[str, Any]) -> int:
    data = _json(payload)
    if not isinstance(data, dict) or "hits" not in data:
        raise PayloadError("companieshouse: no hits field")
    return int(parse_number(data["hits"]))


def parse_epc_total(payload: str | dict[str, Any]) -> int:
    data = _json(payload)
    try:
        return int(parse_number(data["pagination"]["totalRecords"]))
    except (KeyError, TypeError) as exc:
        raise PayloadError("epc: no pagination.totalRecords") from exc


def parse_statxplore_table(payload: str | dict[str, Any]) -> list[tuple[date, float]]:
    """One-dimension table (month) -> (first of month, value). The 'Total' item is skipped."""
    data = _json(payload)
    try:
        cube = next(iter(data["cubes"].values()))["values"]
        items = data["fields"][0]["items"]
    except (KeyError, TypeError, StopIteration, IndexError) as exc:
        raise PayloadError("statxplore: unexpected table shape") from exc
    out: list[tuple[date, float]] = []
    for item, value in zip(items, cube, strict=False):
        label = str((item.get("labels") or [""])[0])
        try:
            day = datetime.strptime(label, "%B %Y").date()
        except ValueError:
            continue
        if value is None:
            continue
        out.append((day, parse_number(value)))
    if not out:
        raise PayloadError("statxplore: no monthly values")
    return out


def parse_adzuna_history(payload: str | dict[str, Any]) -> list[tuple[date, float]]:
    data = _json(payload)
    months = data.get("month") if isinstance(data, dict) else None
    if not isinstance(months, dict) or not months:
        raise PayloadError("adzuna: no month data")
    return sorted((date.fromisoformat(f"{k}-01"), parse_number(v)) for k, v in months.items())


def normalise_reg(reg: str) -> str:
    value = re.sub(r"\s+", "", reg or "").upper()
    if not REG_RE.match(value):
        raise PayloadError("invalid registration format")
    return value


MOT_RESULTS = frozenset({"PASSED", "FAILED"})


def validate_mot_history(data: Any, reg: str) -> dict[str, Any]:
    """Reject anything that is not an MOT history for this registration.

    Required: `registration` equal to the request, and either a `motTests` list (each item with a
    PASSED or FAILED `testResult`) or, for a vehicle with no test yet, a `motTestDueDate`.
    """
    if not isinstance(data, dict):
        raise PayloadError("dvsamot: payload is not an object")
    if normalise_reg(str(data.get("registration", ""))) != reg:
        raise PayloadError("dvsamot: registration missing or different")
    tests = data.get("motTests")
    if tests is None:
        if not data.get("motTestDueDate"):
            raise PayloadError("dvsamot: no motTests and no motTestDueDate")
        return data
    if not isinstance(tests, list):
        raise PayloadError("dvsamot: motTests is not a list")
    for t in tests:
        if not isinstance(t, dict) or str(t.get("testResult", "")).upper() not in MOT_RESULTS:
            raise PayloadError("dvsamot: MOT test without a PASSED or FAILED result")
    return data


class CompaniesHouseAdapter(Adapter):
    """Counts of companies in liquidation and in administration (employer insolvency events)."""

    source_id = "companieshouse"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = (
        ("companies-liquidation", None),
        ("companies-administration", None),
    )
    bounds: ClassVar[dict[str, tuple[float, float]]] = {
        "companies-liquidation": (0.0, 1e8),
        "companies-administration": (0.0, 1e8),
    }

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        status = {"companies-liquidation": "liquidation", "companies-administration": "administration"}.get(series_id)
        if status is None:
            raise PayloadError(f"companieshouse: unknown series {series_id}")
        resp = await self.get(
            COMPANIES_HOUSE_SEARCH_URL,
            {"company_status": status, "size": 1},
            auth=(self.key("COMPANIES_HOUSE_KEY"), ""),
        )
        return [self.obs(series_id, utcnow().date(), float(parse_ch_hits(resp.text)), "count")]


class EpcAdapter(Adapter):
    """Share of domestic certificates rated A to C in each region's main council (England and Wales)."""

    source_id = "epc"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = (("epc-abc-share", None),)
    bounds: ClassVar[dict[str, tuple[float, float]]] = {"epc-abc-share": (0.0, 100.0)}

    async def _count(self, council: str, bands: tuple[str, ...]) -> int:
        params: dict[str, Any] = {"council[]": council, "page_size": 1}
        if bands:
            params["efficiency_rating[]"] = list(bands)
        headers = {"Authorization": f"Bearer {self.key('EPC_KEY')}", "Accept": "application/json"}
        try:
            resp = await self.get(EPC_SEARCH_URL, params, headers=headers)
        except FetchError as exc:
            if "HTTP 404" in str(exc):  # the service answers 404 when nothing matches
                return 0
            raise
        return parse_epc_total(resp.text)

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        if series_id != "epc-abc-share":
            raise PayloadError(f"epc: unknown series {series_id}")
        today = utcnow().date()
        regions = [region] if region in EPC_COUNCILS else list(EPC_COUNCILS)
        out: list[Observation] = []
        for r in regions:
            assert r is not None
            total = await self._count(EPC_COUNCILS[r], ())
            if total <= 0:
                continue
            good = await self._count(EPC_COUNCILS[r], ("A", "B", "C"))
            out.append(self.obs(series_id, today, round(100.0 * good / total, 2), "percent", r))
        return out


class StatXploreAdapter(Adapter):
    source_id = "statxplore"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = (("uc-caseload", None),)
    bounds: ClassVar[dict[str, tuple[float, float]]] = {"uc-caseload": (0.0, 2e7)}

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        if series_id != "uc-caseload":
            raise PayloadError(f"statxplore: unknown series {series_id}")
        resp = await self.request(
            "POST",
            STATXPLORE_TABLE_URL,
            headers={"APIKey": self.key("DWP_STATXPLORE_KEY"), "Content-Type": "application/json"},
            json_body=STATXPLORE_UC_QUERY,
        )
        return [self.obs(series_id, d, v, "count") for d, v in parse_statxplore_table(resp.text)]


class AdzunaAdapter(Adapter):
    """Average advertised salary in UK job ads, by month."""

    source_id = "adzuna"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = (("advertised-salary", None),)
    bounds: ClassVar[dict[str, tuple[float, float]]] = {"advertised-salary": (5_000.0, 500_000.0)}

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        if series_id != "advertised-salary":
            raise PayloadError(f"adzuna: unknown series {series_id}")
        params = {
            "app_id": self.key("ADZUNA_APP_ID"),
            "app_key": self.key("ADZUNA_APP_KEY"),
            "months": 12,
            "content-type": "application/json",
        }
        resp = await self.get(ADZUNA_HISTORY_URL, params)
        return [self.obs(series_id, d, v, "gbp") for d, v in parse_adzuna_history(resp.text)]


class DvlaAdapter(Adapter):
    """Vehicle lookup by registration. Not a time series: no default series."""

    source_id = "dvla"

    async def vehicle(self, registration: str) -> dict[str, Any] | None:
        reg = normalise_reg(registration)
        try:
            resp = await self.request(
                "POST",
                DVLA_URL,
                headers={"x-api-key": self.key("DVLA_KEY"), "Content-Type": "application/json"},
                json_body={"registrationNumber": reg},
            )
        except FetchError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise
        data = _json(resp.text)
        if not isinstance(data, dict) or data.get("registrationNumber") != reg:
            raise PayloadError("dvla: unexpected payload")
        return data

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        data = await self.vehicle(series_id)
        if data is None or "yearOfManufacture" not in data:
            raise PayloadError("dvla: vehicle not found")
        year = int(parse_number(data["yearOfManufacture"]))
        return [self.obs(normalise_reg(series_id), date(year, 1, 1), float(year), "year")]


class DvsaMotAdapter(Adapter):
    """MOT history by registration. Not a time series: no default series."""

    source_id = "dvsamot"

    async def history(self, registration: str) -> dict[str, Any] | None:
        reg = normalise_reg(registration)
        headers = {"x-api-key": self.key("DVSA_MOT_KEY")}
        token = self.env.get("DVSA_MOT_TOKEN", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            resp = await self.get(DVSA_MOT_URL.format(reg=reg), headers=headers)
        except FetchError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise
        data: dict[str, Any] = validate_mot_history(_json(resp.text), reg)
        return data

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        data = await self.history(series_id)
        if data is None:
            raise PayloadError("dvsamot: vehicle not found")
        tests = data.get("motTests") or []
        failed = sum(1 for t in tests if str(t.get("testResult", "")).upper() == "FAILED")
        return [self.obs(normalise_reg(series_id), utcnow().date(), float(failed), "count")]
