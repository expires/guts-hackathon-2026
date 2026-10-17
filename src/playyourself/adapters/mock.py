"""Deterministic mock adapter driven by persona parameter files.

Balance kinds: by default the adapter named "trading212" exposes only ``isa_cash`` balances and
every other name exposes ``current``/``pot`` balances. Override with ``balance_kinds``.
"""

import asyncio
import json
import random
import time
import zlib
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from playyourself.adapters.base import (
    Capability,
    SourceError,
    SourceHealth,
    UnsupportedCapability,
    parse_records,
)
from playyourself.domain.models import Balance, Holding, Transaction

PERSONA_DIR = Path(__file__).resolve().parents[3] / "data" / "mock" / "personas"
MONTHS = 13

_GROCERS = ["TESCO", "SAINSBURYS", "ALDI", "LIDL", "WAITROSE"]
_TRANSPORT = ["TFL TRAVEL", "TRAINLINE", "UBER", "SHELL"]
_EATING = ["PRET A MANGER", "NANDOS", "DELIVEROO", "WAGAMAMA", "COSTA"]
_SHOPPING = ["AMAZON", "ASOS", "ZARA", "ARGOS"]
_FUN = ["ODEON CINEMAS", "STEAM", "TICKETMASTER"]


def list_personas() -> list[str]:
    return sorted(p.stem for p in PERSONA_DIR.glob("*.json"))


def _load_persona(persona: str) -> dict[str, Any]:
    path = PERSONA_DIR / f"{persona}.json"
    if not path.exists():
        raise ValueError(f"unknown persona {persona!r}; available: {list_personas()}")
    return json.loads(path.read_text())


def _month_start(today: date, months_back: int) -> date:
    idx = today.year * 12 + (today.month - 1) - months_back
    return date(idx // 12, idx % 12 + 1, 1)


class MockAdapter:
    mode = "demo"

    def __init__(
        self,
        name: str,
        persona: str,
        capabilities: frozenset[Capability] | None = None,
        latency_ms: int = 0,
        fail_rate: float = 0.0,
        corrupt_rate: float = 0.0,
        seed: int = 0,
        today: date | None = None,
        balance_kinds: frozenset[str] | None = None,
    ):
        self.name = name
        self.persona = persona
        self._params = _load_persona(persona)
        self.capabilities = capabilities if capabilities is not None else frozenset(Capability)
        self.latency_ms = latency_ms
        self.fail_rate = fail_rate
        self.corrupt_rate = corrupt_rate
        self.seed = seed
        self.today = today or date.today()
        if balance_kinds is None:
            balance_kinds = (
                frozenset({"isa_cash"}) if name == "trading212" else frozenset({"current", "pot"})
            )
        self.balance_kinds = balance_kinds
        self.last_dropped = 0
        self._pid = zlib.crc32(persona.encode())
        self._fault_rng = random.Random(seed + self._pid + 1)

    @property
    def cache_key(self) -> str:
        return f"{self.name}-mock-{self.persona}"

    # ---- helpers -------------------------------------------------------------------------
    async def _pre(self, cap: Capability) -> None:
        if cap not in self.capabilities:
            raise UnsupportedCapability(f"{self.name} does not support {cap.value}")
        if self.latency_ms:
            await asyncio.sleep(self.latency_ms / 1000)
        if self.fail_rate and self._fault_rng.random() < self.fail_rate:
            raise SourceError("unavailable", f"{self.name} mock failure", retryable=True)

    def _corrupt(self, raw: list[dict]) -> list[dict]:
        out = []
        for rec in raw:
            rec = dict(rec)
            if self._fault_rng.random() < self.corrupt_rate:
                mode = self._fault_rng.randrange(3)
                keys = list(rec)
                money = [k for k in keys if k.endswith("_pence")]
                if mode == 0:
                    rec.pop(keys[0])
                elif mode == 1 and money:
                    rec[money[0]] = "abc"
                elif "ts" in rec:
                    rec["ts"] = str(rec["ts"]).replace("+00:00", "").replace("Z", "")
                else:
                    rec.pop(keys[0])
            out.append(rec)
        return out

    def _generate_transactions(self) -> list[Transaction]:
        p = self._params
        rng = random.Random(self.seed + self._pid)
        vol = p["volatility"]
        txs: list[dict] = []
        n = 0

        def add(d: date, amount: int, merchant: str, category: str, transfer: bool = False):
            nonlocal n
            if d > self.today or amount == 0:
                return
            ts = datetime(d.year, d.month, d.day, 9, 0, tzinfo=UTC) + timedelta(
                minutes=rng.randrange(0, 600)
            )
            n += 1
            txs.append(
                dict(
                    id=f"{self.persona}-{self.seed}-{n:05d}",
                    ts=ts.isoformat(),
                    amount_pence=amount,
                    merchant=merchant,
                    category=category,
                    is_transfer=transfer,
                )
            )

        def noisy(base: int, parts: int) -> int:
            f = max(0.2, 1 + vol * rng.gauss(0, 1))
            return int(round(base / parts * f))

        def spread(m0: date, base: int, parts: int, merchants: list[str], cat: str):
            for _ in range(parts):
                d = m0 + timedelta(days=rng.randrange(0, 28))
                add(d, -noisy(base, parts), rng.choice(merchants), cat)

        for i in range(MONTHS):
            m0 = _month_start(self.today, MONTHS - 1 - i)
            add(m0 + timedelta(days=24), p["salary_pence"], p["salary_merchant"], "income")
            add(m0, -p["rent_pence"], "LANDLORD RENT", "bills")
            spread(m0, p["groceries_pence"], 4, _GROCERS, "groceries")
            spread(m0, p["transport_pence"], 5, _TRANSPORT, "transport")
            spread(m0, p["eating_out_pence"], 4, _EATING, "eating_out")
            spread(m0, p["discretionary_pence"] * 2 // 3, 2, _SHOPPING, "shopping")
            spread(m0, p["discretionary_pence"] // 3, 1, _FUN, "entertainment")
            for j, s in enumerate(p["subscriptions"]):
                if i >= s["start_month_offset"]:
                    add(
                        m0 + timedelta(days=4 + 2 * j),
                        -s["amount_pence"],
                        s["merchant"],
                        s.get("category", "entertainment"),
                    )
            add(
                m0 + timedelta(days=25),
                -p["isa_contribution_pence"],
                "TRADING 212 ISA",
                "savings",
                transfer=True,
            )
        txs.sort(key=lambda t: t["ts"])
        valid, dropped = parse_records(self._maybe_corrupt(txs), Transaction, self.name)
        self.last_dropped = dropped
        return valid

    def _maybe_corrupt(self, raw: list[dict]) -> list[dict]:
        return self._corrupt(raw) if self.corrupt_rate > 0 else raw

    # ---- FinanceAdapter ------------------------------------------------------------------
    async def get_balances(self) -> list[Balance]:
        await self._pre(Capability.BALANCES)
        p = self._params
        raw = [
            dict(account_id="current-main", kind="current", value_pence=p["current_balance_pence"]),
            dict(account_id="pot-savings", kind="pot", value_pence=p["pot_balance_pence"]),
            dict(account_id="isa-cash", kind="isa_cash", value_pence=p["isa_cash_pence"]),
        ]
        raw = [r for r in raw if r["kind"] in self.balance_kinds]
        valid, self.last_dropped = parse_records(self._maybe_corrupt(raw), Balance, self.name)
        return valid

    async def get_transactions(self, since: date) -> list[Transaction]:
        await self._pre(Capability.TRANSACTIONS)
        return [t for t in self._generate_transactions() if t.ts.date() >= since]

    async def get_holdings(self) -> list[Holding]:
        await self._pre(Capability.HOLDINGS)
        raw = [dict(h) for h in self._params["holdings"]]
        valid, self.last_dropped = parse_records(self._maybe_corrupt(raw), Holding, self.name)
        return valid

    async def health(self) -> SourceHealth:
        start = time.perf_counter()
        if self.latency_ms:
            await asyncio.sleep(self.latency_ms / 1000)
        return SourceHealth(
            name=self.name,
            ok=True,
            latency_ms=(time.perf_counter() - start) * 1000,
            detail=f"mock persona {self.persona}",
        )
