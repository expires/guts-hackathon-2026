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
- `load_sample(sample_id, fmt="csv", today=None)`: parse the statement with the normal statement parser, then add
  the hints the statement cannot show (age, housing, loan plan, future payment dates, balances owed, account
  balances, bank, town and region from the card). Status "mock", source "sample", persona = sample id.
  `today=None` reads the demo file (built for seed.REF_DAY). With `today`, the statement is built by
  `statements.seed` from 1 July 2026 to the day before `today` (PENNY_V3_BUILD A1.3: never stale); the import uses
  this. The current account is the student's own bank account (no Monzo, A1.5).
  Raises KeyError for an unknown id and FileNotFoundError when the files are missing.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

from lifeline_contracts.account import SampleStatement
from lifeline_contracts.finance import Account, AccountHolder, DebtItem, FinanceSnapshot, IncomeSource
from lifeline_data.statements import seed
from lifeline_data.statements.parse import parse_statement, to_snapshot

SNAPSHOT_FIELDS = ("is_student", "age", "student_loan_plan", "monthly_costs", "housing")

# Card city -> region slug (lifeline_contracts.observation.REGIONS). The card is the source of the student's place:
# without it the profile fell back to Manchester / north-west for every sample (SEED_AUDIT location bug).
CITY_REGION: dict[str, str] = {
    "sheffield": "yorkshire-and-the-humber",
    "leeds": "yorkshire-and-the-humber",
    "edinburgh": "scotland",
    "bolton": "north-west",
    "manchester": "north-west",
    "newcastle": "north-east",
    "birmingham": "west-midlands",
    "coventry": "west-midlands",
    "exeter": "south-west",
    "london": "london",
}


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


def sample_entry(sample_id: str, directory: Path | None = None) -> dict[str, Any]:
    for entry in _index(directory):
        if entry.get("id") == sample_id:
            return dict(entry)
    raise KeyError(sample_id)


def place(entry: dict[str, Any]) -> tuple[str | None, str | None]:
    """(region slug, town) from the card: `hints.region`/`hints.town` when set, else the card city."""
    hints = entry.get("hints") or {}
    town = hints.get("town") or entry.get("city")
    region = hints.get("region") or (CITY_REGION.get(str(town).lower()) if town else None)
    return region, (str(town) if town else None)


def _holder(entry: dict[str, Any], snap: FinanceSnapshot) -> AccountHolder | None:
    region, town = place(entry)
    hints = entry.get("hints") or {}
    name = str(hints.get("name") or entry.get("name") or "")[:40]
    age = hints.get("age") or entry.get("age")
    if not name or not isinstance(age, int) or region is None:
        return None
    last = max((t.date for t in snap.transactions), default=snap.as_of)
    return AccountHolder(name=name, birth_year=int(last[:4]) - age, region=region, town=town)


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
        out[i] = s.model_copy(update={"dates": dates, "next_date": h.next_date, "schedule": h.schedule,
                                      "amount": h.amount})  # the hint knows the funding amount
    return out[:20]


def _merge_accounts(found: list[Account], hinted: list[Account]) -> list[Account]:
    """Hinted closing balances win (a CSV export has none); hinted accounts not in the file are added."""
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


def _rebank(snap: FinanceSnapshot, hinted: list[Account]) -> FinanceSnapshot:
    """The parsed file account (CSV layout or PDF) becomes the student's own bank account from the hints."""
    current = next((a for a in hinted if a.kind == "current"), None)
    if current is None:
        return snap
    old = {a.id for a in snap.accounts if a.kind == "current"}
    txs = [t.model_copy(update={"account_id": current.id}) if t.account_id in old else t
           for t in snap.transactions]
    kept = [a for a in snap.accounts if a.id not in old]
    return snap.model_copy(update={"transactions": txs, "accounts": [*kept]})


def load_sample(sample_id: str, fmt: Literal["pdf", "csv"] = "csv", directory: Path | None = None,
                today: date | None = None) -> FinanceSnapshot:
    entry = sample_entry(sample_id, directory)
    hints = dict(entry.get("hints") or {})
    if today is not None and sample_id in seed.IDS:
        end = max(today - timedelta(days=1), date(2026, 7, 31))
        p, rows, _ = seed.statement(sample_id, end)
        content, name = seed.to_csv(p, rows), f"{sample_id}.csv"
        hints.update(seed.hints(p, rows, end))
    else:
        path = (directory or samples_dir()) / f"{sample_id}.{fmt}"
        content, name = path.read_bytes(), path.name
    parsed = parse_statement(content, name)
    if parsed.status == "failed":
        raise ValueError(f"sample {sample_id} could not be parsed: {parsed.warnings}")
    snap = to_snapshot(parsed, as_of=hints.get("as_of"))
    hinted_accounts = [Account.model_validate(a) for a in hints.get("accounts", [])]
    snap = _rebank(snap, hinted_accounts)
    update: dict[str, Any] = {"status": "mock", "source": "sample", "persona": sample_id}
    for key in SNAPSHOT_FIELDS:
        if getattr(snap, key) is None and hints.get(key) is not None:
            update[key] = hints[key]
    update["income_sources"] = _merge_income(
        snap.income_sources, [IncomeSource.model_validate(s) for s in hints.get("income_sources", [])])
    update["accounts"] = _merge_accounts(snap.accounts, hinted_accounts)
    holder = snap.holder or _holder({**entry, "hints": hints}, snap)
    if holder is not None:
        update["holder"] = holder
        update["region"] = snap.region or holder.region
    update["debts"] = _merge_debts(snap.debts, [DebtItem.model_validate(d) for d in hints.get("debts", [])])
    return FinanceSnapshot.model_validate(snap.model_copy(update=update).model_dump())
