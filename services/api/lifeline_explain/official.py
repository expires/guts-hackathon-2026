"""Official sources for rules questions (ADR 0058).

Rules questions (tax, National Insurance, student loans, ISAs, maintenance loans, council tax, Railcard, benefits):
1. facts_table first. Each source shows its official page and "checked <date>".
2. Not in the table: web search restricted to OFFICIAL_DOMAINS. A number counts only when it appears in the
   official text the search returned (citation text). Results from other domains are ignored.
3. No official page states it: Penny says so and gives no number.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlsplit

from lifeline_contracts.chat import ChatFact
from lifeline_contracts.domain import SourceRef
from lifeline_explain.chat_tools import ToolOutput, ToolSourceLink, source_key
from lifeline_explain.verifier import extract_numbers

OFFICIAL_DOMAINS: tuple[str, ...] = (
    "gov.uk",
    "saas.gov.uk",
    "studentfinancewales.co.uk",
    "studentfinanceni.co.uk",
    "railcard.co.uk",
    "16-25railcard.co.uk",
    "legislation.gov.uk",
    "bankofengland.co.uk",
)

NO_OFFICIAL_SOURCE_TEXT = (
    "I could not find an official source for that, so I will not give a number. "
    "GOV.UK or your student finance provider will have the exact figure."
)

_RULES = re.compile(
    r"\b(tax|taxes|taxed|income tax|council tax|tax code|personal allowance|national insurance|ni contributions?|"
    r"student loans?|loan repayments?|repay(ing|ment)? (my|the|a)? ?(student )?loan|plan [1-5]|postgraduate loan|"
    r"maintenance (loan|grant)|tuition fees?|student finance|saas|isas?|lisa|lifetime isa|junior isa|railcard|"
    r"benefits?|universal credit|minimum wage|living wage|bursary rules|sfe|slc|hmrc|repay\w*|thresholds?|"
    r"allowances?|tax code|payslip|pay ?slip|deduct\w*|take (money )?out of my (pay|wages|salary)|"
    r"student loans company|student finance england|national insurance number|vat|stamp duty|"
    r"self[- ]assessment|p60|p45|emergency tax)\b",
    re.IGNORECASE,
)

_HOST_NAMES = {
    "www.gov.uk": "gov.uk",
    "gov.uk": "gov.uk",
    "www.saas.gov.uk": "saas.gov.uk",
    "www.studentfinancewales.co.uk": "Student Finance Wales",
    "www.studentfinanceni.co.uk": "Student Finance NI",
    "www.16-25railcard.co.uk": "16-25 Railcard",
    "www.railcard.co.uk": "Railcard",
    "www.legislation.gov.uk": "legislation.gov.uk",
    "www.bankofengland.co.uk": "Bank of England",
}
_SKIP_SEGMENTS = frozenset({"government", "publications", "guidance", "full-time", "en", "cy"})
_KIND_UNIT: dict[str | None, Any] = {"gbp": "gbp", "percent": "percent", "months": "months", "years": "years"}


def today() -> date:
    """Retrieval date for web sources. Module function so tests can patch it."""
    return datetime.now(UTC).date()


def is_rules_question(message: str) -> bool:
    return bool(_RULES.search(message))


def is_official_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(host == d or host.endswith("." + d) for d in OFFICIAL_DOMAINS)


def nice_date(iso: str | date) -> str:
    """'2026-10-17' -> '17 Oct 2026'. Unknown formats come back unchanged."""
    try:
        d = iso if isinstance(iso, date) else date.fromisoformat(str(iso)[:10])
    except ValueError:
        return str(iso)
    return f"{d.day} {d.strftime('%b %Y')}"


def site_name(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return _HOST_NAMES.get(host, host.removeprefix("www."))


def page_name(url: str) -> str:
    """'https://www.gov.uk/repaying-your-student-loan/what-you-pay' -> 'Repaying your student loan'."""
    for seg in urlsplit(url).path.split("/"):
        if seg and seg not in _SKIP_SEGMENTS:
            words = seg.replace("-", " ").replace("_", " ").strip()
            words = re.sub(r"\b(isa|lisa|jisa|uk|ni|hmrc)(s?)\b", lambda m: m.group(1).upper() + m.group(2), words)
            return (words[:1].upper() + words[1:])[:60]
    return ""


def official_label(url: str, when: str, title: str = "") -> str:
    """'gov.uk · Repaying your student loan · checked 17 Oct 2026'."""
    name = re.sub(r"\s*[-|–]\s*(GOV\.UK|gov\.uk)\s*$", "", title).strip() or page_name(url)
    return " · ".join(p for p in (site_name(url), name[:60], when) if p)[:120]


# ---------- facts table (route 1) ----------


def rule_checked(fact_id: str) -> str | None:
    """Checked date of one facts-table entry: RuleFact.checked if W2 added it, else RuleFact.as_of, else AS_OF."""
    try:
        from lifeline_engine.tools import facts_table as ft
    except ImportError:  # pragma: no cover
        return None
    rf = ft.BY_ID.get(fact_id)
    if rf is None:
        return None
    checked = getattr(rf, "checked", None) or getattr(rf, "as_of", None) or getattr(ft, "AS_OF", None)
    return str(checked) if checked else None


def rule_url(fact_id: str) -> str | None:
    try:
        from lifeline_engine.tools import facts_table as ft
    except ImportError:  # pragma: no cover
        return None
    rf = ft.BY_ID.get(fact_id)
    return str(rf.url) if rf is not None else None


def with_official_sources(out: ToolOutput) -> ToolOutput:
    """facts_table output with one source per official page: url, human label and 'checked <date>'."""
    facts: list[ChatFact] = []
    sources: dict[str, SourceRef] = {}
    links: dict[str, ToolSourceLink] = {}
    for f in out.facts:
        url = rule_url(f.id)
        if url is None:
            facts.append(f)
            continue
        checked = rule_checked(f.id) or ""
        src = "govuk" if url.startswith("https://www.gov.uk/") else "official"
        ref = SourceRef(source=src, series_id=url, status="cached", note=f"checked {nice_date(checked)}")
        sid = source_key(ref)
        sources.setdefault(sid, ref)
        links.setdefault(sid, ToolSourceLink(url=url, updated_at=checked or None))
        facts.append(f.model_copy(update={"source_id": sid}))
    if not sources:
        return out
    refs = list(sources.values())
    return ToolOutput(result=out.result, facts=facts, sources=refs, links=[links[source_key(r)] for r in refs],
                      raw=out.raw)  # fmt: skip


# ---------- web search (route 2) ----------


def web_facts(url: str, cited_text: str, source_id: str, start: int) -> list[ChatFact]:
    """Numbers stated in official cited text become facts that Penny may quote."""
    out: list[ChatFact] = []
    for i, n in enumerate(extract_numbers(cited_text), start):
        if n.is_ratio:
            continue
        if n.kind in _KIND_UNIT:
            unit = _KIND_UNIT[n.kind]
        elif float(n.value).is_integer() and 1900 <= n.value <= 2100:
            unit = "date_year"
        else:
            unit = "count"
        out.append(ChatFact(id=f"web.{i}", value=n.value, unit=unit,
                            label=f"Stated on {site_name(url)}"[:120], source_id=source_id))  # fmt: skip
    return out
