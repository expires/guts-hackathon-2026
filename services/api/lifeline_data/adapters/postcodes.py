"""postcodes.io lookup: postcode -> region slug and town."""

from __future__ import annotations

import json
import re
from typing import Any

from lifeline_data.base import Adapter, FetchError, PayloadError
from lifeline_data.regions import region_from_name

POSTCODES_URL = "https://api.postcodes.io/postcodes/{pc}"
POSTCODES_REVERSE_URL = "https://api.postcodes.io/postcodes"
# UK bounding box for reverse lookups (covers Scilly, Shetland and Northern Ireland).
LAT_RANGE = (49.0, 61.5)
LON_RANGE = (-8.7, 2.0)

# UK postcode shape, including GIR 0AA. Validates format only.
POSTCODE_RE = re.compile(r"^(GIR ?0AA|[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2})$")


def normalise_postcode(raw: str) -> str | None:
    """Uppercase, single space before the inward code. None if the format is invalid."""
    compact = re.sub(r"\s+", "", raw or "").upper()
    if len(compact) < 5 or len(compact) > 7:
        return None
    pc = f"{compact[:-3]} {compact[-3:]}"
    return pc if POSTCODE_RE.match(pc) else None


def parse_postcode_result(payload: str | dict[str, Any]) -> dict[str, str]:
    """Parse a 200 response. A missing or empty `result` is a bad payload; only HTTP 404 means not found."""
    data = json.loads(payload) if isinstance(payload, str) else payload
    result = data.get("result") if isinstance(data, dict) else None
    if not isinstance(result, dict) or not result:
        raise PayloadError("postcodes: no result in response")
    name = result.get("region") or result.get("country")
    try:
        region = region_from_name(name)
    except KeyError as exc:
        raise PayloadError(f"postcodes: unknown region {name!r}") from exc
    if region is None:
        raise PayloadError("postcodes: no region")
    town = result.get("admin_district") or result.get("parish") or ""
    return {"region": region, "town": str(town), "postcode": str(result.get("postcode", ""))}


class PostcodesAdapter(Adapter):
    source_id = "postcodes"

    async def lookup(self, postcode: str) -> dict[str, str] | None:
        """None when the format is invalid or postcodes.io returns 404. Network errors raise FetchError."""
        pc = normalise_postcode(postcode)
        if pc is None:
            return None
        if not self.breaker.allow():
            raise FetchError("postcodes: circuit open")
        try:
            resp = await self.get(POSTCODES_URL.format(pc=pc.replace(" ", "")))
        except FetchError as exc:
            if "HTTP 404" in str(exc):
                self.breaker.record_success()
                return None
            self.breaker.record_failure()
            raise
        try:
            out = parse_postcode_result(resp.text)
        except (PayloadError, ValueError) as exc:
            self.breaker.record_failure()
            raise PayloadError(str(exc)) from exc
        self.breaker.record_success()
        return out

    async def reverse(self, lat: float, lon: float) -> dict[str, str] | None:
        """Nearest postcode to a point. None when outside the UK box or nothing is near (sea).
        Network errors raise FetchError; a bad payload raises PayloadError. Uses the breaker."""
        if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]):
            return None

        async def run() -> dict[str, str] | None:
            resp = await self.get(POSTCODES_REVERSE_URL, {"lon": round(lon, 6), "lat": round(lat, 6), "limit": 1})
            data = json.loads(resp.text)
            if not isinstance(data, dict) or "result" not in data:
                raise PayloadError("postcodes: unexpected reverse payload")
            result = data["result"]
            if result is None or result == []:
                return None
            if not isinstance(result, list) or not isinstance(result[0], dict):
                raise PayloadError("postcodes: unexpected reverse result")
            return parse_postcode_result({"result": result[0]})

        return await self.guarded(run)
