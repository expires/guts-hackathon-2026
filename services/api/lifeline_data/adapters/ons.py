"""ONS time series JSON, e.g. /economy/inflationandpriceindices/timeseries/d7g7/mm23/data."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import zipfile
from datetime import date, datetime, timedelta
from typing import Any, ClassVar

from defusedxml import ElementTree as ET

from lifeline_contracts.observation import Observation
from lifeline_data.base import Adapter, PayloadError, parse_number
from lifeline_data.regions import region_from_code

ONS_BASE = "https://www.ons.gov.uk"
ONS_API = "https://api.beta.ons.gov.uk/v1"
# Index of Private Housing Rental Prices: regional y/y rent change, Jan 2006 to Dec 2023 (history).
IPHRP_DATASET = "index-private-housing-rental-prices"
# Price Index of Private Rents (PIPR) replaced IPHRP in 2024. Monthly xlsx release, Jan 2015 onwards.
PIPR_PAGE = "economy/inflationandpriceindices/datasets/priceindexofprivaterentsukmonthlypricestatistics"

# CDID -> (topic path, dataset id, unit)
ONS_SERIES: dict[str, tuple[str, str, str]] = {
    "D7G7": ("economy/inflationandpriceindices", "mm23", "percent"),  # CPI annual rate, all items
    "D7GT": ("economy/inflationandpriceindices", "mm23", "percent"),  # CPI annual rate 04.5 energy
    "D7IO": ("economy/inflationandpriceindices", "mm23", "percent"),  # CPI annual rate 07.2.2 fuels
}

_MONTH_NAMES = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
_MONTHS = {m: i for i, m in enumerate(_MONTH_NAMES, 1)}


def _parse_date(raw: str) -> date:
    parts = raw.strip().upper().split()
    try:
        if len(parts) == 1:
            return date(int(parts[0]), 7, 1)
        if len(parts) == 2 and parts[1] in _MONTHS:
            return date(int(parts[0]), _MONTHS[parts[1]], 1)
        if len(parts) == 2 and parts[1] in ("Q1", "Q2", "Q3", "Q4"):
            return date(int(parts[0]), (int(parts[1][1]) - 1) * 3 + 2, 1)
    except ValueError as exc:
        raise PayloadError(f"ons: bad date {raw!r}") from exc
    raise PayloadError(f"ons: bad date {raw!r}")


def parse_ons_json(payload: str | dict[str, Any]) -> list[tuple[date, float]]:
    """Use monthly points when present, else quarterly, else annual. Returns (date, value)."""
    data = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(data, dict):
        raise PayloadError("ons: payload is not an object")
    for freq in ("months", "quarters", "years"):
        points = data.get(freq) or []
        if points:
            return [
                (_parse_date(p["date"]), parse_number(p["value"]))
                for p in points
                if str(p.get("value", "")).strip()
            ]
    raise PayloadError("ons: no data points")


def parse_iphrp_csv(text: str) -> list[tuple[date, str | None, float]]:
    """IPHRP v4 CSV. Returns (month, region slug or None for UK, y/y percent). Blank cells are skipped."""
    reader = csv.reader(io.StringIO(text.strip()))
    header = next(reader, None)
    if not header or not header[0].startswith("v4_"):
        raise PayloadError("ons: unexpected IPHRP header")
    out: list[tuple[date, str | None, float]] = []
    for row in reader:
        if len(row) < 7 or row[6] != "year-on-year-change" or not row[0].strip():
            continue
        try:
            region = region_from_code(row[4])
        except KeyError:
            continue  # England, Great Britain
        try:
            day = datetime.strptime(row[2], "%b-%y").date()
        except ValueError as exc:
            raise PayloadError(f"ons: bad IPHRP month {row[2]!r}") from exc
        out.append((day, region, parse_number(row[0])))
    return out


_XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PIPR_SHEET = "Table 1"


def _col(ref: str) -> str:
    return "".join(ch for ch in ref if ch.isalpha())


def _root(book: zipfile.ZipFile, name: str) -> Any:
    root = ET.parse(book.open(name)).getroot()
    if root is None:
        raise PayloadError(f"ons: empty xlsx part {name}")
    return root


def parse_pipr_xlsx(content: bytes) -> list[tuple[date, str | None, float]]:
    """PIPR xlsx 'Table 1' -> (month, region slug or None for UK, annual change percent).

    Stdlib only (zipfile + iterparse). Keeps UK (K02000001) and the 12 region or country rows.
    Cells marked [x] (not available) are skipped.
    """
    try:
        book = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise PayloadError("ons: PIPR file is not an xlsx") from exc
    shared: list[str] = []
    if "xl/sharedStrings.xml" in book.namelist():
        root = _root(book, "xl/sharedStrings.xml")
        shared = ["".join(t.text or "" for t in si.iter(f"{_XLSX_NS}t")) for si in root]
    workbook = _root(book, "xl/workbook.xml")
    rels = _root(book, "xl/_rels/workbook.xml.rels")
    targets = {r.get("Id"): r.get("Target", "") for r in rels}
    sheet_path = None
    for sheet in workbook.iter(f"{_XLSX_NS}sheet"):
        if sheet.get("name") == _PIPR_SHEET:
            target = targets.get(sheet.get(f"{_REL_NS}id"), "")
            sheet_path = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
    if sheet_path is None or sheet_path not in book.namelist():
        raise PayloadError("ons: PIPR 'Table 1' sheet not found")

    cols: dict[str, str] = {}
    out: list[tuple[date, str | None, float]] = []
    for _, el in ET.iterparse(book.open(sheet_path)):
        if el.tag != f"{_XLSX_NS}row":
            continue
        cells: dict[str, str] = {}
        for c in el:
            v = c.find(f"{_XLSX_NS}v")
            if v is None or v.text is None:
                continue
            cells[_col(c.get("r", ""))] = shared[int(v.text)] if c.get("t") == "s" else v.text
        el.clear()
        if not cols:
            names = {text.strip(): col for col, text in cells.items()}
            if {"Time period", "Area code", "Annual change"} <= names.keys():
                cols = {k: names[k] for k in ("Time period", "Area code", "Annual change")}
            continue
        code = cells.get(cols["Area code"], "").strip()
        if code != "K02000001" and not code.startswith(("E12", "W92", "S92", "N92")):
            continue
        raw = cells.get(cols["Annual change"], "").strip()
        if not raw or raw.startswith("["):
            continue
        try:
            region = region_from_code(code)
            serial = int(float(cells[cols["Time period"]]))
        except (KeyError, ValueError) as exc:
            raise PayloadError(f"ons: bad PIPR row for {code}") from exc
        day = EXCEL_EPOCH + timedelta(days=serial)
        out.append((date(day.year, day.month, 1), region, parse_number(raw)))
    if not cols:
        raise PayloadError("ons: PIPR header not found")
    if not out:
        raise PayloadError("ons: PIPR has no regional rows")
    return out


EXCEL_EPOCH = date(1899, 12, 30)


class OnsAdapter(Adapter):
    source_id = "ons"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = (
        ("D7G7", None),
        ("D7GT", None),
        ("D7IO", None),
        ("IPHRP", None),
        ("PIPR", None),
    )
    bounds: ClassVar[dict[str, tuple[float, float]]] = {
        "D7G7": (-5.0, 30.0),
        "D7GT": (-60.0, 200.0),
        "D7IO": (-60.0, 100.0),
        "IPHRP": (-30.0, 50.0),
        "PIPR": (-30.0, 50.0),
    }

    async def _fetch_pipr(self) -> list[Observation]:
        page = json.loads(await self.get_text(f"{ONS_BASE}/{PIPR_PAGE}/data"))
        try:
            latest = page["datasets"][0]["uri"]
            release = json.loads(await self.get_text(f"{ONS_BASE}{latest}/data"))
            filename = release["downloads"][0]["file"]
        except (KeyError, IndexError, TypeError) as exc:
            raise PayloadError("ons: PIPR release not found") from exc
        resp = await self.get(f"{ONS_BASE}/file", {"uri": f"{latest}/{filename}"})
        rows = await asyncio.to_thread(parse_pipr_xlsx, resp.content)
        return [self.obs("PIPR", day, value, "percent", region) for day, region, value in rows]

    async def _fetch_iphrp(self) -> list[Observation]:
        meta = json.loads(await self.get_text(f"{ONS_API}/datasets/{IPHRP_DATASET}"))
        version = json.loads(await self.get_text(meta["links"]["latest_version"]["href"]))
        text = await self.get_text(version["downloads"]["csv"]["href"])
        return [self.obs("IPHRP", day, value, "percent", region) for day, region, value in parse_iphrp_csv(text)]

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        cdid = series_id.upper()
        if cdid == "IPHRP":
            return await self._fetch_iphrp()
        if cdid == "PIPR":
            return await self._fetch_pipr()
        if cdid not in ONS_SERIES:
            raise PayloadError(f"ons: unknown series {series_id}")
        topic, dataset, unit = ONS_SERIES[cdid]
        url = f"{ONS_BASE}/{topic}/timeseries/{cdid.lower()}/{dataset}/data"
        text = await self.get_text(url)
        return [self.obs(cdid, day, value, unit) for day, value in parse_ons_json(text)]
