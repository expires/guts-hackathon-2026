"""Built-in sample statements (ADR 0047). Files come from tools/gen_statements.py into demo/statements/.

- `samples_dir()`: env `LIFELINE_SAMPLES_DIR`, else the package data folder `statements/samples/`
  (shipped in the API image; demo/statements/ at the repo root is an identical copy for judges).
- `list_samples(team=None)`: SampleStatement entries from index.json (empty list when the folder is missing).
  The index holds the 10 student profiles only; `team` is always false (contract field kept). The `team` filter
  stays so old callers keep working: team=True gives an empty list.
- `sample_hints(sample_id)`: the `hints` dict (name, is_student, age, housing, student_loan_plan, income_sources,
  debts, monthly_costs, accounts, budgets, goals). `name` is the account holder, given name first (rooms show the
  first word). `accounts` holds closing balances: current account and savings pots. `budgets` (BudgetLimit shape) and
  `goals` (CreateGoalRequest shape plus a stable `gl_sample_` id) are what the API sets up on import (ADR 0070).
- `load_sample(sample_id, fmt="pdf")`: parse the file with the normal statement parser, then add the hints the
  statement cannot show (age, housing, loan plan, future payment dates, balances owed, account balances).
  Status "mock", source "sample", persona = sample id, so the app labels it "Sample data".
  Raises KeyError for an unknown id and FileNotFoundError when the files are missing.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from lifeline_contracts.account import SampleStatement
from lifeline_contracts.finance import Account, DebtItem, FinanceSnapshot, IncomeSource
from lifeline_data.statements.parse import parse_statement, to_snapshot

SNAPSHOT_FIELDS = ("is_student", "age", "student_loan_plan", "monthly_costs", "housing")


def samples_dir() -> Path:
    env = os.environ.get("LIFELINE_SAMPLES_DIR")
    return Path(env) if env else Path(__file__).resolve().parent / "samples"


def _index(directory: Path | None = None) -> list[dict[str, Any]]:
    path = (directory or samples_dir()) / "index.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("samples", []))


def list_samples(team: bool | None = None, directory: Path | None = None) -> list[SampleStatement]:
    out = []
    for entry in _index(directory):
        item = SampleStatement.model_validate({k: v for k, v in entry.items() if k != "hints"})
        if team is None or item.team == team:
            out.append(item)
    return out


def sample_hints(sample_id: str, directory: Path | None = None) -> dict[str, Any]:
    for entry in _index(directory):
        if entry.get("id") == sample_id:
            return dict(entry.get("hints") or {})
    raise KeyError(sample_id)


def _merge_income(found: list[IncomeSource], hinted: list[IncomeSource]) -> list[IncomeSource]:
    out = list(found)
    for h in hinted:
        same = [k for k, s in enumerate(out) if s.kind == h.kind]
        if not same:
            out.append(h)
            continue
        i = min(same, key=lambda k: abs(out[k].amount - h.amount))  # closest amount: allowance, not a top-up
        s = out[i]
        dates = sorted({*s.dates, *h.dates})[-60:]
        out[i] = s.model_copy(update={"dates": dates, "next_date": h.next_date,
                                      "schedule": h.schedule})
    return out[:20]


def _merge_accounts(found: list[Account], hinted: list[Account]) -> list[Account]:
    """Hinted closing balances win (a Monzo CSV has none); hinted accounts not in the file are added."""
    out = list(found)
    for h in hinted:
        i = next((k for k, a in enumerate(out) if a.id == h.id), None)
        if i is None:
            out.append(h)
        else:
            out[i] = out[i].model_copy(update={"balance": h.balance})
    return out


def _merge_debts(found: list[DebtItem], hinted: list[DebtItem]) -> list[DebtItem]:
    out = list(found)
    for h in hinted:
        i = next((k for k, d in enumerate(out) if d.kind == h.kind), None)
        if i is None:
            out.append(h)
            continue
        d = out[i]
        out[i] = d.model_copy(update={
            "balance": d.balance if d.balance > 0 else h.balance,
            "rate_pct": d.rate_pct if d.rate_pct is not None else h.rate_pct,
            "due_date": d.due_date or h.due_date,
            "free_limit": d.free_limit if d.free_limit is not None else h.free_limit,
        })
    return out[:20]


def load_sample(sample_id: str, fmt: Literal["pdf", "csv"] = "pdf", directory: Path | None = None) -> FinanceSnapshot:
    hints = sample_hints(sample_id, directory)
    path = (directory or samples_dir()) / f"{sample_id}.{fmt}"
    parsed = parse_statement(path.read_bytes(), path.name)
    if parsed.status == "failed":
        raise ValueError(f"sample {sample_id} could not be parsed: {parsed.warnings}")
    snap = to_snapshot(parsed)
    update: dict[str, Any] = {"status": "mock", "source": "sample", "persona": sample_id}
    for key in SNAPSHOT_FIELDS:
        if getattr(snap, key) is None and hints.get(key) is not None:
            update[key] = hints[key]
    update["income_sources"] = _merge_income(
        snap.income_sources, [IncomeSource.model_validate(s) for s in hints.get("income_sources", [])])
    update["accounts"] = _merge_accounts(snap.accounts,
                                         [Account.model_validate(a) for a in hints.get("accounts", [])])
    update["debts"] = _merge_debts(snap.debts, [DebtItem.model_validate(d) for d in hints.get("debts", [])])
    return FinanceSnapshot.model_validate(snap.model_copy(update=update).model_dump())
