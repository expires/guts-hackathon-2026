"""Bank of England Interactive Database (IADB) CSV.

IUMBEDR = Bank Rate. IUMBV34 = 2-year fix, 75% LTV. IUMBV42 = 5-year fix, 75% LTV.
IUMBV37 is the 3-year fix, not the 5-year fix.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import ClassVar

from lifeline_contracts.observation import Observation
from lifeline_data.base import Adapter, PayloadError, parse_number

BOE_URL = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"
# IUMB6VJ = instant-access deposits incl. bonuses (households). IUMCCTL = credit card rate (households).
# One invalid code makes the IADB return an HTML error page for the whole request.
BOE_SERIES = ("IUMBEDR", "IUMBV34", "IUMBV42", "IUMB6VJ", "IUMCCTL")


def parse_boe_csv(text: str) -> list[tuple[str, date, float]]:
    """Parse IADB CSV (CSVF=TN). Returns (series_id, date, value). Blank cells are skipped."""
    reader = csv.reader(io.StringIO(text.strip()))
    try:
        header = [h.strip() for h in next(reader)]
    except StopIteration as exc:
        raise PayloadError("boe: empty CSV") from exc
    if not header or header[0].upper() != "DATE" or len(header) < 2:
        raise PayloadError(f"boe: unexpected header {header[:3]}")
    out: list[tuple[str, date, float]] = []
    for row in reader:
        if not row or not row[0].strip():
            continue
        try:
            day = datetime.strptime(row[0].strip(), "%d %b %Y").date()
        except ValueError as exc:
            raise PayloadError(f"boe: bad date {row[0]!r}") from exc
        for code, cell in zip(header[1:], row[1:], strict=False):
            if cell.strip() == "":
                continue
            out.append((code, day, parse_number(cell)))
    return out


class BoEAdapter(Adapter):
    source_id = "boe"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = tuple((s, None) for s in BOE_SERIES)
    bounds: ClassVar[dict[str, tuple[float, float]]] = {s: (-1.0, 25.0) for s in BOE_SERIES} | {
        "IUMCCTL": (0.0, 60.0)
    }

    def params(self) -> dict[str, str]:
        return {
            "csv.x": "yes",
            "Datefrom": "01/Jan/1990",
            "Dateto": "now",
            "SeriesCodes": ",".join(BOE_SERIES),
            "CSVF": "TN",
            "UsingCodes": "Y",
            "VPD": "Y",
            "VFD": "N",
        }

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        code = series_id.upper()
        text = await self.get_text(BOE_URL, self.params())
        rows = parse_boe_csv(text)
        return [self.obs(code, day, value, "percent") for s, day, value in rows if s == code]
