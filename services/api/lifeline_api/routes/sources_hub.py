"""GET /v1/sources/hub: "Where Penny's data comes from" (ADR 0073).

One card per student-facing source, in a fixed order: your statement, official facts, then the live UK sources.
Status and fetch time come from the source registry (the same as GET /v1/sources). Latest values come from the
MacroTable (and the MPC dates from the data hub). No homeowner sources. Works without sign-in: the data is public,
and the statement card never shows the user's own numbers.
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from typing import Any, Literal

from fastapi import APIRouter, Query, Request

from lifeline_api import macro, money
from lifeline_api.auth import OptionalSubject
from lifeline_api.state import AppState, get_state
from lifeline_contracts.macro import MacroKey, MacroTable
from lifeline_contracts.observation import SourceStatus, Status
from lifeline_contracts.sources_hub import HubSource, HubValue, SourcesHub
from lifeline_engine import rules
from lifeline_explain import hub_text
from lifeline_explain.i18n import Lang, lang_of

router = APIRouter(tags=["meta"])

Language = Literal["en", "fr", "es", "pt", "it", "zh-Hans", "hi", "ne"]

# (card id, registry id, name or None for a translated name, used_in screen keys, official url)
LIVE_CARDS: tuple[tuple[str, str, str | None, tuple[str, ...], str], ...] = (
    ("boe", "boe", "Bank of England", ("helps", "maths"), "https://www.bankofengland.co.uk/boeapps/database/"),
    ("ons", "ons", "ONS", ("maths",), "https://www.ons.gov.uk/economy/inflationandpriceindices"),
    ("nomis", "nomis", "Nomis", ("penny", "learn"), "https://www.nomisweb.co.uk/"),
    ("octopus", "octopus", "Octopus Energy", ("bills", "penny"), "https://octopus.energy/"),
    ("frankfurter", "frankfurter", "Frankfurter", ("penny",), "https://frankfurter.dev/"),
    ("boe-mpc", "boe-mpc", None, ("penny", "learn"),
     "https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates"),
)  # fmt: skip
HOMEOWNER_SOURCES = frozenset({"landregistry", "epc", "police", "environmentagency", "companieshouse",
                               "carbonintensity", "statxplore", "coingecko", "yahoo", "fred"})  # fmt: skip
OFFICIAL_URL = "https://www.gov.uk/student-finance"

# card id -> (label key, MacroKey, format)
MACRO_VALUES: dict[str, tuple[tuple[str, MacroKey, str], ...]] = {
    "boe": (("bank_rate", MacroKey.BANK_RATE, "pct"), ("savings_rate", MacroKey.SAVINGS_RATE, "pct")),
    "ons": (("cpi", MacroKey.CPI_INFLATION, "pct"),),
    "nomis": (("median_pay", MacroKey.MEDIAN_PAY, "gbp_year"),),
    "octopus": (("energy", MacroKey.ENERGY_TARIFF, "gbp_year"),),
    "frankfurter": (("gbp_usd", MacroKey.GBP_USD, "fx"),),
}
OFFICIAL_VALUES: tuple[tuple[str, str], ...] = (
    ("plan2_threshold", "rule.student_loan_plan2_threshold"),
    ("isa_allowance", "rule.isa_allowance"),
)


def _fmt(value: float, kind: str, lang: Lang) -> str:
    if kind == "pct":
        return f"{round(value, 2):g}%"
    if kind == "fx":
        return f"£1 = ${value:.2f}"
    return f"£{round(value):,} {hub_text.A_YEAR[lang]}"


def _latest(table: MacroTable, key: MacroKey, year: int) -> tuple[int, float] | None:
    years = [y for y in table.years(key) if y <= year] or table.years(key)
    if not years:
        return None
    try:
        return years[-1], table.get(key, years[-1]).value
    except KeyError:
        return None


def _when(d: str) -> datetime:
    return datetime.combine(datetime.fromisoformat(d).date(), time(), tzinfo=UTC)


async def _next_decision(hub: Any) -> str | None:
    fn = getattr(hub, "rate_decisions", None)
    if fn is None:
        return None
    try:
        res = await fn()
    except Exception:
        return None
    nxt = getattr(res, "next_decision", None)
    return str(nxt) if nxt else None


@router.get("/v1/sources/hub", response_model=SourcesHub, response_model_exclude_none=True)
async def get_sources_hub(request: Request, sub: OptionalSubject,
                          language: Language = Query(default="en")) -> SourcesHub:  # fmt: skip
    return await build_hub(get_state(request), sub, lang_of(language))


async def build_hub(state: AppState, sub: str | None, lang: Lang = "en") -> SourcesHub:
    """The hub for one caller (also used by the demo trace, ADR 0075)."""
    statuses: dict[str, SourceStatus] = {s.id: s for s in await state.hub.statuses()}
    table, _fresh = await macro.table_fast(state)
    today = datetime.now(UTC).date()

    def screens(keys: tuple[str, ...]) -> list[str]:
        return [hub_text.SCREENS[k][lang] for k in keys]

    # Your statement: generic text only. Status from the caller's own data, if any.
    snap = await money.maybe_snapshot(state, sub) if sub else None
    statement_status: Status = snap.status if snap is not None else "unavailable"
    cards = [HubSource(
        id="statement", name=hub_text.NAMES["statement"][lang], kind="statement", status=statement_status,
        updated_at=_when(snap.as_of) if snap is not None and snap.as_of else None,
        gives=hub_text.GIVES["statement"][lang], used_in=screens(("forecast", "spending", "bills")),
    )]  # fmt: skip

    facts = {f.id: f for f in rules.FACTS}
    official_latest = [
        HubValue(label=hub_text.LABELS[label][lang], value=_fmt(facts[fid].value, "gbp_year", lang),
                 as_of=facts[fid].checked)
        for label, fid in OFFICIAL_VALUES if fid in facts
    ]  # fmt: skip
    checked = max((f.checked for f in rules.FACTS), default=None)
    cards.append(HubSource(
        id="official_facts", name=hub_text.NAMES["official"][lang], kind="official_facts", status="cached",
        updated_at=_when(checked) if checked else None, gives=hub_text.GIVES["official"][lang],
        used_in=screens(("penny", "learn", "maths")), latest=official_latest, url=OFFICIAL_URL,
    ))  # fmt: skip

    for card_id, reg_id, name, used, url in LIVE_CARDS:
        reg = statuses.get(reg_id)
        latest: list[HubValue] = []
        for label, key, kind in MACRO_VALUES.get(card_id, ()):
            got = _latest(table, key, today.year)
            if got is not None:
                latest.append(HubValue(label=hub_text.LABELS[label][lang], value=_fmt(got[1], kind, lang),
                                       as_of=str(got[0])))  # fmt: skip
        if card_id == "boe-mpc":
            nxt = await _next_decision(state.hub)
            if nxt is not None:
                latest.append(HubValue(label=hub_text.LABELS["next_decision"][lang], value=nxt, as_of=nxt))
        cards.append(HubSource(
            id=card_id, name=name or hub_text.NAMES[card_id][lang], kind="live",
            status=reg.status if reg is not None else "unavailable",
            updated_at=reg.fetched_at if reg is not None else None,
            gives=hub_text.GIVES[card_id][lang], used_in=screens(used), latest=latest, url=url,
        ))  # fmt: skip

    live_count = sum(1 for c in cards if c.kind != "statement")
    return SourcesHub(summary=hub_text.SUMMARY[lang].format(n=live_count), live_count=live_count, sources=cards)
