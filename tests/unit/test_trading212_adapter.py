import base64

import httpx
import pytest

from playyourself.adapters import trading212
from playyourself.adapters.base import FinanceAdapter, SourceError
from playyourself.adapters.trading212 import Trading212Adapter
from playyourself.settings import Settings

KEY, SECRET = "key_SECRET456", "sec_VERYSECRET"
BASIC = "Basic " + base64.b64encode(f"{KEY}:{SECRET}".encode()).decode()


@pytest.fixture(autouse=True)
def _clear_cache():
    trading212._reset_cache()
    yield
    trading212._reset_cache()


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def make(handler, key=KEY, secret=SECRET, clock=None) -> Trading212Adapter:
    s = Settings(t212_base_url="https://t212.test/api/v0", _env_file=None)
    kw = {"clock": clock} if clock else {}
    return Trading212Adapter(
        s,
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        api_key=key,
        api_secret=secret,
        **kw,
    )


def pos(ticker, isin, qty, cur_price, value, wallet_ccy="GBP", inst_ccy="GBP"):
    return {
        "averagePricePaid": 1.0,
        "currentPrice": cur_price,
        "createdAt": "2024-01-01T00:00:00Z",
        "instrument": {
            "currency": inst_ccy,
            "isin": isin,
            "name": f"{ticker} name",
            "ticker": ticker,
        },
        "quantity": qty,
        "walletImpact": {"currency": wallet_ccy, "currentValue": value},
    }


SUMMARY = {
    "id": 42,
    "currency": "GBP",
    "cash": {"availableToTrade": 100.10, "inPies": 23.356, "reservedForOrders": 50.0},
    "totalValue": 1000,
}


def ok_handler(positions=None, summary=None, calls=None):
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["Authorization"] == BASIC
        p = req.url.path
        if calls is not None:
            calls.append(p)
        if p == "/api/v0/equity/positions":
            return httpx.Response(200, json=positions if positions is not None else [])
        if p == "/api/v0/equity/account/summary":
            return httpx.Response(200, json=summary if summary is not None else SUMMARY)
        return httpx.Response(404)

    return handler


async def test_holdings_use_wallet_value_and_drop_non_gbp():
    pf = [
        pos("VUSA_EQ", "IE00B3XXRP09", 10.5, 80.25, 842.63),
        pos("VAGS_EQ", "IE00BG47KB92", 2, 25.0, 50.0),
        # USD instrument: currentPrice is USD, wallet value is the GBP figure.
        pos("AAPL_US_EQ", "US0378331005", 3, 200.0, 450.0, inst_ccy="USD"),
        pos("BAD_EQ", "XX1", 1, 1.0, 10.0, wallet_ccy="EUR"),
        "garbage",
    ]
    a = make(ok_handler(pf))
    assert isinstance(a, FinanceAdapter)
    out = await a.get_holdings()
    assert a.last_dropped == 2
    by = {h.instrument_id: h for h in out}
    assert by["IE00B3XXRP09"].value_pence == 84263
    assert by["IE00B3XXRP09"].region == "US" and by["IE00B3XXRP09"].asset_class == "equity"
    assert by["IE00BG47KB92"].asset_class == "bond" and by["IE00BG47KB92"].value_pence == 5000
    assert by["US0378331005"].value_pence == 45000  # not 3 * 200 * 100
    assert by["US0378331005"].name == "AAPL_US_EQ name"
    assert "XX1" not in by


async def test_positions_as_items_object():
    a = make(ok_handler({"items": [pos("VUSA_EQ", "IE1", 1, 1.0, 5.0)]}))
    out = await a.get_holdings()
    assert len(out) == 1 and out[0].value_pence == 500


async def test_cash_balance():
    bals = await make(ok_handler()).get_balances()
    assert len(bals) == 1 and bals[0].kind == "isa_cash" and bals[0].account_id == "42"
    assert bals[0].value_pence == round((100.10 + 23.356) * 100)


async def test_non_gbp_summary_dropped():
    a = make(ok_handler(summary={**SUMMARY, "currency": "USD"}))
    assert await a.get_balances() == []
    assert a.last_dropped == 1


async def test_health():
    h = await make(ok_handler()).health()
    assert h.ok and h.latency_ms is not None


async def test_basic_auth_header():
    seen = {}

    def handler(req):
        seen["auth"] = req.headers["Authorization"]
        return httpx.Response(200, json=SUMMARY)

    assert (await make(handler, key="k1", secret="s1").health()).ok
    assert seen["auth"] == "Basic " + base64.b64encode(b"k1:s1").decode()


@pytest.mark.parametrize(("key", "secret"), [(KEY, ""), ("", SECRET), ("", "")])
async def test_missing_credentials(key, secret):
    called = []
    a = make(lambda req: called.append(1) or httpx.Response(200, json=[]), key=key, secret=secret)
    with pytest.raises(SourceError) as ei:
        await a.get_holdings()
    assert ei.value.code == "auth" and not called
    for v in (KEY, SECRET):
        assert v not in str(ei.value)


async def test_positions_cached_within_one_second():
    calls, clock = [], Clock()
    a = make(ok_handler([pos("VUSA_EQ", "IE1", 1, 1.0, 5.0)], calls=calls), clock=clock)
    await a.get_holdings()
    clock.t += 0.5
    await a.get_holdings()
    assert len(calls) == 1
    clock.t += 0.6
    await a.get_holdings()
    assert len(calls) == 2


async def test_summary_shared_by_balances_and_health():
    calls, clock = [], Clock()
    a = make(ok_handler(calls=calls), clock=clock)
    await a.get_balances()
    clock.t += 4
    assert (await a.health()).ok
    assert len(calls) == 1
    clock.t += 1.1
    await a.get_balances()
    assert len(calls) == 2


async def test_cache_shared_across_instances_not_across_keys():
    calls, clock = [], Clock()
    await make(ok_handler(calls=calls), clock=clock).get_balances()
    await make(ok_handler(calls=calls), clock=clock).get_balances()
    assert len(calls) == 1
    assert all(KEY not in repr(k) and SECRET not in repr(k) for k in trading212._CACHE)

    def other(req):
        calls.append("other")
        return httpx.Response(200, json=SUMMARY)

    await make(other, key="k2", secret="s2", clock=clock).get_balances()
    assert calls[-1] == "other"


@pytest.mark.parametrize(
    ("resp", "code", "retryable"),
    [
        (httpx.Response(401), "auth", False),
        (httpx.Response(500), "unavailable", True),
        (httpx.Response(200, content=b"<html>"), "bad_data", False),
        (httpx.Response(200, json={"not": "a list"}), "bad_data", False),
    ],
)
async def test_errors(resp, code, retryable):
    with pytest.raises(SourceError) as ei:
        await make(lambda req: resp).get_holdings()
    assert ei.value.code == code and ei.value.retryable is retryable
    for v in (KEY, SECRET, BASIC):
        assert v not in str(ei.value)


async def test_rate_limited_retry_after_header():
    a = make(lambda req: httpx.Response(429, headers={"Retry-After": "2.5"}))
    with pytest.raises(SourceError) as ei:
        await a.get_balances()
    assert ei.value.code == "rate_limited" and ei.value.retryable
    assert ei.value.retry_after == 2.5


@pytest.mark.parametrize(("reset", "expected"), [("3", 3.0), ("1700000010", 10.0), ("x", None)])
async def test_rate_limited_reset_header(reset, expected):
    a = make(lambda req: httpx.Response(429, headers={"x-ratelimit-reset": reset}))
    a._wall_clock = lambda: 1_700_000_000.0
    with pytest.raises(SourceError) as ei:
        await a.get_balances()
    assert ei.value.code == "rate_limited" and ei.value.retry_after == expected


async def test_health_reports_error_code():
    h = await make(lambda req: httpx.Response(401), key="bad", secret="bad").health()
    assert not h.ok and h.error_code == "auth"
