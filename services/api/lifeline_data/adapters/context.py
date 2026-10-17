"""Context sources (ADR 0030): Guardian headlines and Bank of England MPC rate-decision dates.

Context only: never a decision input. Headlines are untrusted text (ADR 0034): they are cleaned, cut
to bounded lengths, and only https theguardian.com links are kept.

Guardian: we request and keep only headline, standfirst (first sentence), section, date and URL.
Article body text is never requested (copyright). The key travels in the `api-key` header, not the URL.
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
from datetime import date
from typing import Any, ClassVar
from urllib.parse import urlsplit

from lifeline_contracts.chat import NewsItem
from lifeline_contracts.observation import Observation
from lifeline_data.base import Adapter, PayloadError

GUARDIAN_SEARCH_URL = "https://content.guardianapis.com/search"
BOE_MPC_URL = "https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates"

MAX_NEWS_ITEMS = 50
MAX_TEXT = 300

# Topic id -> (Guardian query, sections). Free text topics use the business and money sections.
NEWS_TOPICS: dict[str, tuple[str, str]] = {
    "rates": ('"interest rates" OR "Bank of England"', "business|money"),
    "mortgages": ("mortgage OR mortgages", "business|money"),
    "housing": ('"house prices" OR "housing market" OR rents', "business|money|society"),
    "inflation": ("inflation OR \"cost of living\"", "business|money"),
    "energy": ('"energy bills" OR "price cap" OR Ofgem', "business|money"),
    "jobs": ("unemployment OR jobs OR wages", "business|money"),
    "markets": ('"FTSE" OR "stock market" OR shares', "business|money"),
    "economy": ("economy OR GDP OR recession", "business"),
}
TOPIC_RE = re.compile(r"^[A-Za-z0-9 '\-]{2,60}$")

_TAG_RE = re.compile(r"<[^>]+>")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'‘])")
_MONTHS = {m: i for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
     "november", "december"), 1)}


def clean_text(raw: Any, limit: int = MAX_TEXT) -> str:
    """Strip HTML and control characters, collapse spaces, cut to `limit` characters at a word."""
    text = html.unescape(_TAG_RE.sub(" ", str(raw or "")))
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in " ")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:")
        text = cut + "…"
    return text


def first_sentence(raw: Any, limit: int = MAX_TEXT) -> str | None:
    text = clean_text(raw, limit=10_000)
    if not text:
        return None
    return clean_text(_SENTENCE_END.split(text, maxsplit=1)[0], limit)


def guardian_query(topic: str) -> tuple[str, str]:
    """(q, section) for a topic id or a short free-text topic. Rejects anything else."""
    key = topic.strip().lower()
    if key in NEWS_TOPICS:
        return NEWS_TOPICS[key]
    if not TOPIC_RE.match(topic.strip()):
        raise PayloadError("guardian: topic must be 2-60 letters, digits, spaces, ' or -")
    return topic.strip(), "business|money"


def _safe_url(raw: Any) -> str | None:
    url = str(raw or "")
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.scheme != "https" or not (host == "www.theguardian.com" or host == "theguardian.com"):
        return None
    return url if len(url) <= 500 else None


def parse_guardian(payload: str | dict[str, Any]) -> list[NewsItem]:
    """Search response -> NewsItems. Items with a bad URL, date or empty headline are skipped."""
    data = json.loads(payload) if isinstance(payload, str) else payload
    try:
        response = data["response"]
        results = response["results"]
    except (KeyError, TypeError) as exc:
        raise PayloadError("guardian: unexpected shape") from exc
    if response.get("status") != "ok" or not isinstance(results, list):
        raise PayloadError("guardian: status not ok")
    items: list[NewsItem] = []
    for r in results[:MAX_NEWS_ITEMS]:
        if not isinstance(r, dict):
            continue
        raw_fields = r.get("fields")
        fields: dict[str, Any] = raw_fields if isinstance(raw_fields, dict) else {}
        headline = clean_text(fields.get("headline") or r.get("webTitle"))
        url = _safe_url(r.get("webUrl"))
        try:
            day = date.fromisoformat(str(r.get("webPublicationDate", ""))[:10])
        except ValueError:
            continue
        if not headline or url is None:
            continue
        items.append(
            NewsItem(
                id=clean_text(r.get("id") or url, 200),
                headline=headline,
                standfirst=first_sentence(fields.get("trailText")),
                section=clean_text(r.get("sectionName") or "News", 60),
                date=day.isoformat(),
                url=url,
            )
        )
    return items


def parse_mpc_dates(page: str) -> list[date]:
    """Dates under '<year> confirmed dates' (or 'provisional dates') headings on the BoE page."""
    text = html.unescape(_TAG_RE.sub(" ", re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S)))
    text = re.sub(r"\s+", " ", text)
    heads = list(re.finditer(r"\b(20\d\d) (?:confirmed|provisional) dates\b", text))
    if not heads:
        raise PayloadError("boe-mpc: no dates heading found")
    out: set[date] = set()
    for i, head in enumerate(heads):
        year = int(head.group(1))
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        block = text[head.end():end]
        for m in re.finditer(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday) (\d{1,2}) ([A-Z][a-z]+)\b", block):
            month = _MONTHS.get(m.group(2).lower())
            if month is None:
                continue
            try:
                out.add(date(year, month, int(m.group(1))))
            except ValueError:
                continue
    if not out:
        raise PayloadError("boe-mpc: no dates found")
    return sorted(out)


class GuardianAdapter(Adapter):
    source_id = "guardian"

    async def search(self, topic: str, start: date, end: date, limit: int = 20) -> list[NewsItem]:
        q, section = guardian_query(topic)
        params = {
            "q": q,
            "section": section,
            "from-date": start.isoformat(),
            "to-date": end.isoformat(),
            "show-fields": "headline,trailText",  # never body
            "order-by": "newest",
            "page-size": max(1, min(limit, MAX_NEWS_ITEMS)),
        }
        resp = await self.get(GUARDIAN_SEARCH_URL, params, headers={"api-key": self.key("GUARDIAN_API_KEY")})
        return parse_guardian(resp.text)

    async def search_guarded(self, topic: str, start: date, end: date, limit: int = 20) -> list[NewsItem]:
        return await self.guarded(lambda: self.search(topic, start, end, limit))

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        raise PayloadError("guardian: context source, not a series")


class BoeMpcAdapter(Adapter):
    source_id = "boe-mpc"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = ()

    async def dates(self) -> list[date]:
        return parse_mpc_dates(await self.get_text(BOE_MPC_URL))

    async def dates_guarded(self) -> list[date]:
        return await self.guarded(self.dates)

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        raise PayloadError("boe-mpc: context source, not a series")
