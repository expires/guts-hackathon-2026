"""Bridge from the data hub (W1) and the money engine (W2) to the routes.

- `snapshot(state, sub)`: the caller's FinanceSnapshot, cached per subject for a short time.
- `meta(snap)`: FinanceMeta for every finance response. Mock data carries the label "Sample data".
- `today(snap)`: the reference day for engine calls. It is the snapshot's `as_of` day, so results
  are deterministic for one snapshot (the engine has no clock).
- `fill_personal(state, sub, lesson)`: Lesson.personal from the PersonalFact whose concept_id matches.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, date, datetime
from typing import Any, cast

from lifeline_api import onboarding
from lifeline_api.errors import ApiError
from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import AppState
from lifeline_api.store import StoreUnavailable
from lifeline_contracts.domain import CharacterSpec, DecisionProfile, Lesson
from lifeline_contracts.finance import (
    Account,
    AmountPart,
    Bill,
    FinanceMeta,
    FinanceOverview,
    FinanceProfile,
    FinanceSnapshot,
    PersonalFact,
    SpendPrediction,
    Subscription,
)
from lifeline_engine import money as money_engine
from lifeline_engine.money import ProfileHints
from lifeline_engine.money.profile import is_cash, months_of_cover

log = logging.getLogger(__name__)



def no_finance_data() -> ApiError:
    """Live mode (ADR 0027): the user has not connected or entered their own money data yet."""
    return ApiError(409, "no_finance_data", "Connect your money first.", source="data")


async def stored_snapshot(state: AppState, sub: str) -> FinanceSnapshot | None:
    """The data the user gave us (statement, manual entry, logged payments). Kept by the data hub (W1)."""
    hub: Any = state.hub
    snap: FinanceSnapshot | None = await hub.get_user_snapshot(sub)
    return snap


async def save_snapshot(state: AppState, sub: str, snap: FinanceSnapshot) -> None:
    """Replace the user's own data. Raises StoreUnavailable when it cannot be kept durably."""
    hub: Any = state.hub
    try:
        durable = await hub.set_user_snapshot(sub, snap)
    except Exception as exc:
        log.warning("user snapshot write failed: %s", type(exc).__name__)
        raise StoreUnavailable() from exc
    finally:
        forget(state, sub)
    try:
        await state.store.delete_doc(sub, "next_move")  # the stored next move was built from the old data
    except StoreUnavailable:
        log.warning("stale next move not cleared: store unavailable")
    if not durable and not state.settings.is_test and state.settings.database_url:
        raise StoreUnavailable()


async def delete_snapshot(state: AppState, sub: str) -> None:
    hub: Any = state.hub
    await hub.delete_user_snapshot(sub)
    forget(state, sub)


def forget(state: AppState, sub: str) -> None:
    """Drop every per-subject cache entry (after the user's data changes or is deleted)."""
    for key in [k for k in state.memo if len(k) > 1 and k[1] == sub]:
        state.memo.pop(key, None)


async def maybe_snapshot(state: AppState, sub: str) -> FinanceSnapshot | None:
    """The caller's own FinanceSnapshot, or None when they have not given us any money data.

    Both modes: no data of their own means None. The demo finance personas are never served (tests only).
    """
    stored = await stored_snapshot(state, sub)
    hub: Any = state.hub
    live_of = getattr(hub, "live_snapshot", None)
    live: FinanceSnapshot | None = await live_of(sub) if live_of is not None else None
    if live is not None:
        # Connected Monzo / Trading212: live data on top of what the user entered. Never sample data.
        return onboarding.merge_statement(stored, live)
    return stored


def fingerprint(snap: FinanceSnapshot) -> str:
    """Changes whenever the snapshot content changes. Keys the per-snapshot caches."""
    return hashlib.sha256(snap.model_dump_json().encode()).hexdigest()[:16]


async def snapshot(state: AppState, sub: str) -> FinanceSnapshot:
    """The caller's FinanceSnapshot. 409 no_finance_data when there is none."""
    snap = await maybe_snapshot(state, sub)
    if snap is None:
        raise no_finance_data()
    return snap


def meta(snap: FinanceSnapshot) -> FinanceMeta:
    return money_engine.finance_meta(snap)


def today(snap: FinanceSnapshot) -> date:
    return date.fromisoformat(snap.as_of)


async def personal_facts(state: AppState, sub: str) -> list[PersonalFact]:
    """Facts from the caller's own data only. Empty when the caller has none."""
    snap = await maybe_snapshot(state, sub)
    if snap is None:
        return []
    key = ("facts", sub)
    fp = fingerprint(snap)
    hit = state.memo.get(key)
    if hit is not None and hit[0] == fp:
        return cast(list[PersonalFact], hit[1])
    facts = await call_pure(money_engine.personal_facts, snap)
    state.memo[key] = (fp, facts)
    return facts


async def fill_personal(state: AppState, sub: str, lesson: Lesson | None) -> Lesson | None:
    """Return the lesson with `personal` set from a matching PersonalFact. Never fails the request."""
    if lesson is None or lesson.personal is not None:
        return lesson
    try:
        facts = await personal_facts(state, sub)
    except Exception as exc:
        log.warning("personal facts unavailable: %s", type(exc).__name__)
        return lesson
    match = next((f for f in facts if f.concept_id == lesson.concept_id), None)
    if match is None:
        return lesson
    return lesson.model_copy(update={"personal": match.text})


def engine_profile(snap: FinanceSnapshot, hints_: ProfileHints | None) -> tuple[DecisionProfile, CharacterSpec]:
    """The same profile for /v1/finance/profile, the next move and Test it (ADR 0018)."""
    profile, character = money_engine.profile(snap, today(snap), hints_)
    return profile, character


# ---------- shown totals and known dates (ADR 0053 bugs 2 and 3) ----------


def _shown(a: Account) -> bool:
    """An account the user gave us a balance for. The manual-entry current account has no entered balance."""
    return not (a.name == onboarding.UNENTERED_CURRENT and a.balance == 0)


def overview(snap: FinanceSnapshot) -> FinanceOverview:
    """The engine overview plus the parts behind 'In your account' and 'Net worth', from entered data only.
    The parts add up to the totals; Why? shows them as the calculation."""
    ov = money_engine.overview(snap)
    balance_parts = [AmountPart(label=a.name, amount=round(a.balance, 2))
                     for a in snap.accounts if is_cash(a) and _shown(a)]
    worth_parts = [AmountPart(label=a.name, amount=round(a.balance, 2)) for a in snap.accounts if _shown(a)]
    m = snap.mortgage
    if m is not None:
        worth_parts.append(AmountPart(label="Home value you entered" if snap.source == "manual" else "Home value",
                                      amount=round(m.property_value, 2)))
        if not any(a.kind == "mortgage" for a in snap.accounts):
            worth_parts.append(AmountPart(label="Mortgage", amount=-round(m.balance, 2)))
    return ov.model_copy(update={"balance_parts": balance_parts, "net_worth_parts": worth_parts})


def without_guessed_dates_bills(snap: FinanceSnapshot, items: list[Bill]) -> list[Bill]:
    """Drop bills whose due date we would be guessing (costs entered as monthly amounts)."""
    guessed = onboarding.synthetic_merchants(snap)
    return [b for b in items if b.name.lower() not in guessed]


def without_guessed_dates_subs(snap: FinanceSnapshot, items: list[Subscription]) -> list[Subscription]:
    guessed = onboarding.synthetic_merchants(snap)
    return [s.model_copy(update={"next_payment": None}) if s.merchant.lower() in guessed else s for s in items]


def without_guessed_payday(snap: FinanceSnapshot, pred: SpendPrediction) -> SpendPrediction:
    """No 'payday in N days' and no payday reason unless an income date is known."""
    if onboarding.payday_known(snap):
        return pred
    return pred.model_copy(update={"days_to_payday": None,
                                   "reasons": [r for r in pred.reasons if r.feature != "payday"]})


# ---------- what the user said at onboarding (ADR 0053 bug 7) ----------

DOC_ONBOARDING = "onboarding_profile"


async def save_onboarding(state: AppState, sub: str, *, is_student: bool | None, housing: str,
                          age: int | None) -> None:
    await state.store.put_doc(sub, DOC_ONBOARDING, {"is_student": is_student, "housing": housing, "age": age})


PAYMENTS_PER_YEAR = {"weekly": 52, "fortnightly": 26, "monthly": 12, "termly": 3, "yearly": 1, "one_off": 1}


def yearly_income(snap: FinanceSnapshot) -> float | None:
    """Income per year from the entered or detected income sources (scholarship, bursary, loan, family, pay),
    by schedule. None when there are no income sources."""
    if not snap.income_sources:
        return None
    return round(sum(s.amount * PAYMENTS_PER_YEAR[s.schedule] for s in snap.income_sources), 2)


async def with_onboarding(state: AppState, sub: str, prof: FinanceProfile,
                          snap: FinanceSnapshot | None = None) -> FinanceProfile:
    """The You tab line must match onboarding: age, student or working, housing. Entered values win over
    values the engine inferred from transactions. Birth year follows the known age, and income comes from
    the income sources when there are any (a student's scholarship is income, not salary)."""
    try:
        doc = await state.store.get_doc(sub, DOC_ONBOARDING)
    except StoreUnavailable:
        doc = None
    doc = doc or {}
    p_upd: dict[str, Any] = {}
    c_upd: dict[str, Any] = {}
    top: dict[str, Any] = {}
    if doc.get("housing"):
        p_upd["housing"] = c_upd["housing"] = doc["housing"]
    if "is_student" in doc:
        top["is_student"] = doc.get("is_student")
    elif snap is not None and snap.is_student is not None:
        top["is_student"] = snap.is_student
    age = doc.get("age") if doc.get("age") is not None else (snap.age if snap is not None else None)
    if age is not None:
        p_upd["age"] = age
        as_of_year = date.fromisoformat(snap.as_of).year if snap is not None else datetime.now(UTC).year
        c_upd["birth_year"] = as_of_year - int(age)
    if top.get("is_student") is True:
        c_upd["occupation"] = "Student"
    income = yearly_income(snap) if snap is not None else None
    if income is not None:
        p_upd["annual_income"] = c_upd["annual_income"] = min(income, 10_000_000)
    # "Their profile" (ADR 0069): the user's own income sources, debts, cover and rent. Rent is the regular rent
    # payment found in the statement (manual entry adds rent rows, so it is found there too).
    if (p_upd.get("housing") or prof.profile.housing) == "rent":
        top["monthly_rent"] = prof.profile.monthly_rent
    if snap is not None:
        top["income_sources"] = list(snap.income_sources)
        top["debts"] = list(snap.debts)
        top["months_of_cover"] = months_of_cover(snap, today(snap))
    return prof.model_copy(update={**top, "profile": prof.profile.model_copy(update=p_upd),
                                   "character": prof.character.model_copy(update=c_upd)})
