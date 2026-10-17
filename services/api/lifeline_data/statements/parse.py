"""Monzo and Revolut CSV parsers. See the package docstring for the rules."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

from lifeline_contracts.finance import Account, AccountHolder, FinanceSnapshot, Transaction
from lifeline_data.base import PayloadError, parse_number

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 20_000
MAX_WARNINGS = 20
MAX_AMOUNT = 1_000_000.0

Provider = Literal["monzo", "revolut", "pdf", "unknown"]
ImportStatus = Literal["done", "partial", "failed"]

PDF_WARNING = (
    "PDF statements are not supported yet. Export a CSV from your bank app (Monzo or Revolut) and upload that."
)

# Header columns that identify each export. Matching is case-insensitive.
MONZO_REQUIRED = {"transaction id", "date", "name", "amount", "currency"}
REVOLUT_REQUIRED = {"type", "product", "started date", "completed date", "description", "amount", "currency", "state"}


@dataclass
class ParsedStatement:
    provider: Provider
    status: ImportStatus
    accounts: list[Account] = field(default_factory=list)
    transactions: list[Transaction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rows_read: int = 0
    rows_rejected: int = 0
    balance_known: bool = False

    @property
    def first_date(self) -> str | None:
        return min((t.date for t in self.transactions), default=None)

    @property
    def last_date(self) -> str | None:
        return max((t.date for t in self.transactions), default=None)

    @property
    def months_covered(self) -> float:
        if not self.transactions:
            return 0.0
        first, last = date.fromisoformat(self.first_date or ""), date.fromisoformat(self.last_date or "")
        return round(((last - first).days + 1) / 30.44, 1)


class _Warnings:
    """Collects up to MAX_WARNINGS messages and counts the rest."""

    def __init__(self) -> None:
        self.items: list[str] = []
        self.extra = 0

    def add(self, text: str) -> None:
        if len(self.items) < MAX_WARNINGS - 1:
            self.items.append(text)
        else:
            self.extra += 1

    def done(self) -> list[str]:
        return self.items + ([f"{self.extra} more rows had problems and were skipped."] if self.extra else [])


def clean(raw: object, limit: int) -> str:
    """Untrusted text: drop control and format characters, collapse spaces, cut to `limit`."""
    text = "".join(ch if unicodedata.category(ch)[0] != "C" else " " for ch in str(raw or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


FORMULA_START = ("=", "+", "-", "@")


def text_cell(raw: object, limit: int) -> str:
    """`clean`, then defuse spreadsheet formulas: a value starting with = + - @ gets a leading
    apostrophe, so a later CSV or spreadsheet export shows it as text (OWASP CSV injection)."""
    text = clean(raw, limit)
    if text.startswith(FORMULA_START):
        text = ("'" + text)[:limit]
    return text


def _amount(raw: str) -> float:
    value = parse_number(raw.replace("£", ""))
    if abs(value) > MAX_AMOUNT:
        raise PayloadError("amount out of range")
    return round(value, 2)


def _tx_id(provider: str, *parts: object) -> str:
    digest = hashlib.sha256("|".join(map(str, (provider, *parts))).encode()).hexdigest()[:20]
    return f"{provider[:3]}_{digest}"


def _decode(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PayloadError("The file is not UTF-8 text. Export it again as CSV.") from exc


def _parse_monzo(rows: list[dict[str, str]], warn: _Warnings) -> ParsedStatement:
    out = ParsedStatement(provider="monzo", status="done")
    seen: set[str] = set()
    for n, row in enumerate(rows, start=2):
        out.rows_read += 1
        try:
            currency = (row.get("currency") or "").strip().upper()
            if currency != "GBP":
                raise PayloadError(f"currency {clean(currency, 5) or 'missing'} is not GBP")
            day = datetime.strptime((row.get("date") or "").strip(), "%d/%m/%Y").date()
            amount = _amount(row.get("amount") or "")
            name = text_cell(row.get("name"), 80)
            desc = text_cell(row.get("description") or name, 200) or name
            if not (name or desc):
                raise PayloadError("no name or description")
            native_id = clean(row.get("transaction id"), 64)
            tx_id = _tx_id("monzo", native_id or n)
            if tx_id in seen:
                raise PayloadError("duplicate transaction id")
            seen.add(tx_id)
            category = text_cell(row.get("category") or row.get("type"), 60) or None
            out.transactions.append(
                Transaction(
                    id=tx_id, account_id="monzo_current", date=day.isoformat(), amount=amount,
                    description=desc or name, merchant=name or None, provider_category=category,
                )
            )
        except (PayloadError, ValueError) as exc:
            out.rows_rejected += 1
            warn.add(f"Row {n} skipped: {clean(exc, 120)}.")
    out.accounts = [Account(id="monzo_current", name="Monzo Current Account", kind="current", provider="Monzo",
                            balance=0.0)]
    if out.transactions:
        warn.add("Monzo exports do not include your balance. Add it on the next screen.")
    return out


_REVOLUT_PRODUCTS = {"current": ("current", "Revolut Current Account"), "savings": ("savings", "Revolut Savings"),
                     "deposit": ("savings", "Revolut Savings")}


def _parse_revolut(rows: list[dict[str, str]], warn: _Warnings) -> ParsedStatement:
    out = ParsedStatement(provider="revolut", status="done")
    balances: dict[str, tuple[datetime, float]] = {}
    for n, row in enumerate(rows, start=2):
        out.rows_read += 1
        try:
            state = (row.get("state") or "").strip().upper()
            if state != "COMPLETED":
                raise PayloadError(f"state {clean(state, 20) or 'missing'} is not COMPLETED")
            currency = (row.get("currency") or "").strip().upper()
            if currency != "GBP":
                raise PayloadError(f"currency {clean(currency, 5) or 'missing'} is not GBP")
            stamp_raw = (row.get("completed date") or row.get("started date") or "").strip()
            stamp = datetime.strptime(stamp_raw[:19], "%Y-%m-%d %H:%M:%S")
            fee_raw = (row.get("fee") or "").strip()
            fee = _amount(fee_raw) if fee_raw else 0.0
            amount = round(_amount(row.get("amount") or "") - abs(fee), 2)
            product = clean(row.get("product"), 20).lower() or "current"
            kind, _ = _REVOLUT_PRODUCTS.get(product, ("current", "Revolut Current Account"))
            account_id = f"revolut_{kind}"
            desc = text_cell(row.get("description"), 200)
            if not desc:
                raise PayloadError("no description")
            tx_type = text_cell(row.get("type"), 60) or None
            out.transactions.append(
                Transaction(
                    id=_tx_id("revolut", n, stamp.isoformat(), amount, desc), account_id=account_id,
                    date=stamp.date().isoformat(), amount=amount, description=desc, merchant=text_cell(desc, 80),
                    provider_category=tx_type,
                )
            )
            bal_raw = (row.get("balance") or "").strip()
            if bal_raw:
                bal = _amount(bal_raw)
                if account_id not in balances or stamp >= balances[account_id][0]:
                    balances[account_id] = (stamp, bal)
        except (PayloadError, ValueError) as exc:
            out.rows_rejected += 1
            warn.add(f"Row {n} skipped: {clean(exc, 120)}.")
    used = sorted({t.account_id for t in out.transactions})
    for account_id in used:
        kind = "savings" if account_id.endswith("savings") else "current"
        name = "Revolut Savings" if kind == "savings" else "Revolut Current Account"
        latest = balances.get(account_id)
        out.accounts.append(Account(id=account_id, name=name, kind=kind, provider="Revolut",
                                    balance=latest[1] if latest else 0.0))
    out.balance_known = bool(used) and all(a in balances for a in used)
    return out


_PARSERS: dict[str, tuple[set[str], Callable[[list[dict[str, str]], _Warnings], ParsedStatement]]] = {
    "monzo": (MONZO_REQUIRED, _parse_monzo),
    "revolut": (REVOLUT_REQUIRED, _parse_revolut),
}


def _failed(provider: Provider, message: str) -> ParsedStatement:
    return ParsedStatement(provider=provider, status="failed", warnings=[message])


def parse_statement(content: bytes, filename: str | None = None) -> ParsedStatement:
    """Detect the provider and parse. Never raises: problems become warnings or status "failed"."""
    try:
        if len(content) > MAX_BYTES:
            return _failed("unknown", "The file is larger than 5 MB.")
        if content[:5] == b"%PDF-" or (filename or "").lower().endswith(".pdf"):
            return _failed("pdf", PDF_WARNING)
        if not content.strip():
            return _failed("unknown", "The file is empty.")
        text = _decode(content)
        reader = csv.DictReader(io.StringIO(text, newline=""))
        header = {clean(h, 60).lower() for h in (reader.fieldnames or [])}
        provider = next((p for p, (req, _) in _PARSERS.items() if req <= header), None)
        if provider is None:
            return _failed("unknown", "This does not look like a Monzo or Revolut CSV export.")
        rows: list[dict[str, str]] = []
        for raw in reader:
            if len(rows) >= MAX_ROWS:
                return _failed(provider, f"The file has more than {MAX_ROWS:,} rows.")  # type: ignore[arg-type]
            rows.append({clean(k, 60).lower(): (v if isinstance(v, str) else "") for k, v in raw.items() if k})
        warn = _Warnings()
        parsed = _PARSERS[provider][1](rows, warn)
        parsed.warnings = warn.done()
        parsed.transactions.sort(key=lambda t: (t.date, t.id))
        if not parsed.transactions:
            parsed.status = "failed"
            if not parsed.warnings:
                parsed.warnings = ["The file has no transactions."]
        elif parsed.rows_rejected:
            parsed.status = "partial"
        return parsed
    except PayloadError as exc:
        return _failed("unknown", str(exc))
    except (csv.Error, UnicodeError) as exc:
        return _failed("unknown", f"The file could not be read as CSV ({type(exc).__name__}).")


def to_snapshot(
    parsed: ParsedStatement,
    as_of: str | None = None,
    *,
    region: str | None = None,
    postcode: str | None = None,
    holder: AccountHolder | None = None,
) -> FinanceSnapshot:
    """FinanceSnapshot from a parsed statement: status "live", source "statement"."""
    if parsed.status == "failed":
        raise ValueError("cannot build a snapshot from a failed import")
    return FinanceSnapshot(
        status="live",
        source="statement",
        persona=None,
        as_of=as_of or parsed.last_date or date.today().isoformat(),
        accounts=parsed.accounts,
        transactions=parsed.transactions,
        region=region,
        postcode=postcode,
        holder=holder,
    )
