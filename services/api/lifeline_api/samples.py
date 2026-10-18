"""Built-in sample statements (ADR 0047). Loading and parsing are W1's (lifeline_data.statements.samples);
this module adds what the API needs on top: the debt accounts and the import result for the import screen."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import ValidationError

from lifeline_contracts.account import SamplesResponse
from lifeline_contracts.finance import Account, BudgetLimit, CreateGoalRequest, FinanceSnapshot
from lifeline_data.statements import samples as data_samples

# Debts a statement cannot show as a balance. An overdraft already shows as a negative current account.
DEBT_ACCOUNTS: dict[str, tuple[Any, str]] = {
    "card": ("credit", "Credit card"),
    "bnpl": ("credit", "Buy now, pay later"),
    "loan": ("loan", "Loan"),
}


def listing() -> SamplesResponse:
    return SamplesResponse(samples=data_samples.list_samples())  # the 10 student profiles (ADR 0070)


def hints(sample_id: str) -> dict[str, Any] | None:
    try:
        return data_samples.sample_hints(sample_id)
    except KeyError:
        return None


def load(sample_id: str) -> FinanceSnapshot | None:
    """The sample as the user's data: W1's parse of the PDF (it carries the running balance) plus hints,
    labelled "Sample data", with debt accounts. None when the sample or its file is missing.
    Raises SampleWithoutBalance when no balance could be read (never import a £0 sample, V1)."""
    try:
        snap = data_samples.load_sample(sample_id)
    except (KeyError, FileNotFoundError, ValueError):
        return None
    if not any(a.balance != 0 for a in snap.accounts):
        raise SampleWithoutBalance(sample_id)
    housing = (hints(sample_id) or {}).get("housing")
    if housing and snap.housing is None:
        snap = snap.model_copy(update={"housing": housing})
    return with_debt_accounts(snap)


class SampleWithoutBalance(Exception):
    """The sample statement gave no balance, so it would show £0."""


def with_debt_accounts(snap: FinanceSnapshot) -> FinanceSnapshot:
    accounts = list(snap.accounts)
    have = {a.id for a in accounts}
    for debt in snap.debts:
        if debt.balance <= 0 or debt.kind not in DEBT_ACCOUNTS:
            continue
        kind, name = DEBT_ACCOUNTS[debt.kind]
        acc_id = f"acc_debt_{debt.id}"[:40]
        if acc_id not in have:
            accounts.append(Account(id=acc_id, name=name, kind=kind, provider="sample",
                                    balance=-round(debt.balance, 2)))
    return snap.model_copy(update={"accounts": accounts})


def months_covered(snap: FinanceSnapshot) -> float:
    days = [t.date for t in snap.transactions]
    if not days:
        return 0.0
    first, last = date.fromisoformat(min(days)), date.fromisoformat(max(days))
    return round(((last - first).days + 1) / 30.44, 1)


# ---------- budgets and savings goals that come with a sample (ADR 0070) ----------

SAMPLE_GOAL_PREFIX = "gl_sample_"


def plan(hint: dict[str, Any]) -> tuple[list[BudgetLimit], list[tuple[str, CreateGoalRequest]]]:
    """The sample's budget limits and (id, goal) pairs from its hints. Items that fail the contract are skipped.
    Goal ids are stable (gl_sample_<sample>_<n>), so a re-import replaces them instead of adding copies."""
    budgets: list[BudgetLimit] = []
    for b in hint.get("budgets") or []:
        try:
            budgets.append(BudgetLimit.model_validate(b))
        except ValidationError:
            continue
    goals: list[tuple[str, CreateGoalRequest]] = []
    for g in hint.get("goals") or []:
        gid = str(g.get("id", "")) if isinstance(g, dict) else ""
        if not gid.startswith(SAMPLE_GOAL_PREFIX):
            continue
        try:
            goals.append((gid, CreateGoalRequest.model_validate({k: v for k, v in g.items() if k != "id"})))
        except ValidationError:
            continue
    return budgets, goals
