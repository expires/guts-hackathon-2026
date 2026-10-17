"""Market sources: Frankfurter (FX), CoinGecko (crypto), Yahoo chart (FTSE All-Share), FRED (10y gilt)."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, date, datetime
from typing import Any, ClassVar

from lifeline_contracts.observation import Observation
from lifeline_data.base import Adapter, PayloadError, parse_number

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/{start}.."
FRANKFURTER_LATEST_URL = "https://api.frankfurter.dev/v1/latest"
# Currencies with ECB reference rates (Frankfurter /currencies, recorded 2026-10-17). A pair outside this set is
# never fetched, so a bad request cannot mark the source as down.
FX_CURRENCIES = frozenset({
    "AUD", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR", "GBP", "HKD", "HUF", "IDR", "ILS", "INR", "ISK",
    "JPY", "KRW", "MXN", "MYR", "NOK", "NZD", "PHP", "PLN", "RON", "SEK", "SGD", "THB", "TRY", "USD", "ZAR",
})
FX_UNIT = "fx"  # units of `quote` per 1 `base`; no shared unit bound (IDR per GBP is about 20,000)
COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def _json(payload: str | dict[str, Any], source: str) -> dict[str, Any]:
    data = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(data, dict):
        raise PayloadError(f"{source}: payload is not an object")
    return data


def parse_frankfurter(payload: str | dict[str, Any], quote: str = "USD") -> list[tuple[date, float]]:
    data = _json(payload, "frankfurter")
    rates = data.get("rates")
    if not isinstance(rates, dict) or not rates:
        raise PayloadError("frankfurter: no rates")
    return sorted((date.fromisoformat(day), parse_number(row[quote])) for day, row in rates.items())


def fx_pair(base: str, quote: str) -> str | None:
    """Series id for a supported pair, e.g. ('cny', 'GBP') -> 'CNYGBP'. None when either code is unsupported."""
    b, q = base.strip().upper(), quote.strip().upper()
    if b not in FX_CURRENCIES or q not in FX_CURRENCIES or b == q:
        return None
    return b + q


def parse_frankfurter_latest(payload: str | dict[str, Any], base: str, quote: str) -> tuple[date, float]:
    """/latest?from=BASE&to=QUOTE -> (ECB reference date, rate). The rate must be positive."""
    data = _json(payload, "frankfurter")
    if str(data.get("base", "")).upper() != base:
        raise PayloadError("frankfurter: wrong base currency")
    rates = data.get("rates")
    if not isinstance(rates, dict) or quote not in rates:
        raise PayloadError("frankfurter: no rate")
    value = parse_number(rates[quote])
    if value <= 0:
        raise PayloadError("frankfurter: rate must be positive")
    try:
        day = date.fromisoformat(str(data.get("date")))
    except ValueError as exc:
        raise PayloadError("frankfurter: bad date") from exc
    return day, value


def parse_coingecko(payload: str | dict[str, Any]) -> list[tuple[date, float]]:
    """market_chart prices [[ms, price], ...] -> one (date, price) per day (last price of the day)."""
    data = _json(payload, "coingecko")
    prices = data.get("prices")
    if not isinstance(prices, list) or len(prices) < 2:
        raise PayloadError("coingecko: no prices")
    by_day: dict[date, float] = {}
    for item in prices:
        ms, price = item[0], item[1]
        by_day[datetime.fromtimestamp(parse_number(ms) / 1000, UTC).date()] = parse_number(price)
    return sorted(by_day.items())


def yoy_from_series(points: list[tuple[date, float]], min_days: int = 330) -> tuple[date, float]:
    """Percent change from the first point to the last point. The span must be about a year."""
    if len(points) < 2:
        raise PayloadError("not enough points for a y/y change")
    (d0, v0), (d1, v1) = points[0], points[-1]
    if (d1 - d0).days < min_days or v0 <= 0:
        raise PayloadError("span too short for a y/y change")
    return d1, round((v1 / v0 - 1.0) * 100.0, 2)


def parse_yahoo_chart(payload: str | dict[str, Any]) -> list[tuple[date, float]]:
    """Monthly closes from the v8 chart endpoint. Null closes are skipped."""
    data = _json(payload, "yahoo")
    try:
        result = data["chart"]["result"][0]
        stamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError) as exc:
        raise PayloadError("yahoo: unexpected chart shape") from exc
    out: dict[tuple[int, int], tuple[date, float]] = {}
    for ts, close in zip(stamps, closes, strict=False):
        if close is None:
            continue
        day = datetime.fromtimestamp(int(ts), UTC).date()
        out[(day.year, day.month)] = (date(day.year, day.month, 1), parse_number(close))
    if not out:
        raise PayloadError("yahoo: no closes")
    return [out[k] for k in sorted(out)]


def monthly_yoy(points: list[tuple[date, float]]) -> list[tuple[date, float]]:
    """Month-on-same-month-last-year percent change."""
    by_month = {(d.year, d.month): v for d, v in points}
    out: list[tuple[date, float]] = []
    for d, v in points:
        prev = by_month.get((d.year - 1, d.month))
        if prev is not None and prev > 0:
            out.append((d, round((v / prev - 1.0) * 100.0, 2)))
    return out


def parse_fred_csv(text: str, series_id: str) -> list[tuple[date, float]]:
    reader = csv.reader(io.StringIO(text.strip()))
    header = next(reader, None)
    if not header or len(header) < 2 or header[1].strip() != series_id:
        raise PayloadError("fred: unexpected header")
    out: list[tuple[date, float]] = []
    for row in reader:
        if len(row) < 2 or row[1].strip() in ("", "."):
            continue
        try:
            day = date.fromisoformat(row[0].strip())
        except ValueError as exc:
            raise PayloadError(f"fred: bad date {row[0]!r}") from exc
        out.append((day, parse_number(row[1])))
    return out


class FrankfurterAdapter(Adapter):
    source_id = "frankfurter"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = (("GBPUSD", None),)
    bounds: ClassVar[dict[str, tuple[float, float]]] = {"GBPUSD": (0.5, 3.0)}

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        """GBPUSD: daily history since 1999 (MacroTable). Any other supported pair (e.g. CNYGBP): latest rate."""
        sid = series_id.upper()
        if sid == "GBPUSD":
            text = await self.get_text(FRANKFURTER_URL.format(start="1999-01-04"), {"from": "GBP", "to": "USD"})
            return [self.obs("GBPUSD", d, v, "rate") for d, v in parse_frankfurter(text)]
        pair = fx_pair(sid[:3], sid[3:]) if len(sid) == 6 else None
        if pair is None:
            raise PayloadError(f"frankfurter: unknown series {series_id}")
        base, quote = pair[:3], pair[3:]
        text = await self.get_text(FRANKFURTER_LATEST_URL, {"from": base, "to": quote})
        day, value = parse_frankfurter_latest(text, base, quote)
        return [self.obs(pair, day, value, FX_UNIT)]


class CoinGeckoAdapter(Adapter):
    """Free API gives 365 days. Emits the GBP price per day and one y/y return for the latest day."""

    source_id = "coingecko"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = (("bitcoin", None),)
    bounds: ClassVar[dict[str, tuple[float, float]]] = {"bitcoin": (-100.0, 2_000.0), "bitcoin-gbp": (0.0, 1e7)}

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        coin = series_id.removesuffix("-gbp")
        if coin != "bitcoin":
            raise PayloadError(f"coingecko: unknown series {series_id}")
        text = await self.get_text(
            COINGECKO_URL.format(coin=coin), {"vs_currency": "gbp", "days": "365", "interval": "daily"}
        )
        prices = parse_coingecko(text)
        if series_id.endswith("-gbp"):
            return [self.obs(series_id, d, v, "gbp") for d, v in prices]
        day, change = yoy_from_series(prices)
        return [self.obs("bitcoin", day, change, "percent")]


class YahooAdapter(Adapter):
    """Unofficial endpoint; often answers 429. The hub then serves cached or mock data."""

    source_id = "yahoo"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = (("^FTAS", None),)
    bounds: ClassVar[dict[str, tuple[float, float]]] = {"^FTAS": (-80.0, 150.0)}

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        text = await self.get_text(YAHOO_URL.format(symbol=series_id), {"range": "max", "interval": "1mo"})
        closes = parse_yahoo_chart(text)
        return [self.obs(series_id, d, v, "percent") for d, v in monthly_yoy(closes)]


class FredAdapter(Adapter):
    source_id = "fred"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = (("IRLTLT01GBM156N", None),)
    bounds: ClassVar[dict[str, tuple[float, float]]] = {"IRLTLT01GBM156N": (-2.0, 20.0)}

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        text = await self.get_text(FRED_URL, {"id": series_id})
        return [self.obs(series_id, d, v, "percent") for d, v in parse_fred_csv(text, series_id)]
