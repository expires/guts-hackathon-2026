"""Sample students: spending categories and the budgets and goals that come with each sample (ADR 0070)."""

from __future__ import annotations

from datetime import date

import pytest

from lifeline_contracts.finance import BudgetLimit, CreateGoalRequest
from lifeline_data.statements.samples import list_samples, load_sample, sample_hints
from lifeline_engine.money import spending_response
from lifeline_engine.money.spending import by_category

IDS = [s.id for s in list_samples()]
FULL_MONTHS = ("2026-08", "2026-09")  # whole calendar months inside every statement
OTHER_MAX = 0.15

pytestmark = pytest.mark.skipif(not IDS, reason="sample statements not generated")


def _other_share(cats: dict[str, tuple[float, int]]) -> float:
    total = sum(v for v, _ in cats.values())
    return cats.get("other", (0.0, 0))[0] / total if total > 0 else 0.0


@pytest.mark.parametrize("fmt", ["pdf", "csv"])
def test_other_is_under_15_percent_for_every_sample(fmt: str) -> None:
    assert len(IDS) == 10
    for sid in IDS:
        snap = load_sample(sid, fmt)  # type: ignore[arg-type]
        months = sorted({t.date[:7] for t in snap.transactions})
        for m in months:
            share = _other_share(by_category(snap.transactions, m))  # type: ignore[arg-type]
            assert share < OTHER_MAX, f"{sid} {fmt} {m}: Other is {share:.0%} of spending"
        whole: dict[str, tuple[float, int]] = {}
        for m in months:
            for c, (v, n) in by_category(snap.transactions, m).items():
                pv, pn = whole.get(c, (0.0, 0))
                whole[c] = (pv + v, pn + n)
        assert _other_share(whole) < OTHER_MAX, f"{sid} {fmt}: Other is {_other_share(whole):.0%} over the statement"


def test_money_in_is_never_spending() -> None:
    """Loan, grant, bursary, family money and pay are income, not a refund of a shop (e.g. "GBP" is not BP)."""
    for sid in IDS:
        snap = load_sample(sid)
        resp = spending_response(snap)
        assert resp.total > 0, sid
        for m in sorted({t.date[:7] for t in snap.transactions}):
            assert all(v >= 0 for v, _ in by_category(snap.transactions, m).values())


def test_spending_omits_zero_categories() -> None:
    for sid in IDS:
        for c in spending_response(load_sample(sid)).categories:
            assert c.amount > 0 or c.transactions > 0, f"{sid}: {c.category} at £0 with no rows"


def test_every_sample_has_a_budget_and_a_goal_that_fit_its_statement() -> None:
    for sid in IDS:
        hints = sample_hints(sid)
        snap = load_sample(sid)
        budgets = [BudgetLimit.model_validate(b) for b in hints["budgets"]]
        assert budgets, f"{sid}: no budget"
        for b in budgets:
            avg = sum(by_category(snap.transactions, m).get(b.category, (0.0, 0))[0] for m in FULL_MONTHS) / 2
            assert avg > 0, f"{sid}: budget on {b.category} with no spending"
            assert 0.5 * avg <= b.limit <= 1.5 * avg, f"{sid}: {b.category} limit {b.limit} vs average {avg:.0f}"
        goals = hints["goals"]
        assert goals, f"{sid}: no savings goal"
        pots = sum(a["balance"] for a in hints["accounts"] if a["kind"] == "savings")
        for i, g in enumerate(goals, start=1):
            assert g["id"] == f"gl_sample_{sid}_{i}"
            req = CreateGoalRequest.model_validate({k: v for k, v in g.items() if k != "id"})
            assert req.saved < req.target
            assert req.saved in (0.0, round(pots, 2)), f"{sid}: saved must be 0 or the pot balance"
            assert req.target_date is not None and date.fromisoformat(req.target_date) > date.fromisoformat(
                snap.as_of)
