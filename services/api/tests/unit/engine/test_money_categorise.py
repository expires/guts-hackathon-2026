from __future__ import annotations

import pytest

from lifeline_engine.money.categorise import categorise, merchant_key

from .finance_builders import tx


@pytest.mark.parametrize(
    ("amount", "description", "merchant", "expected"),
    [
        (-23.10, "TESCO STORES 2231", "Tesco", "groceries"),
        (-12.99, "NETFLIX.COM", None, "subscriptions"),
        (-8.99, "AMAZON PRIME", "Amazon Prime", "subscriptions"),
        (-31.50, "AMAZON.CO.UK MKTP", "Amazon", "shopping"),
        (-14.20, "UBER EATS", None, "eating_out"),
        (-9.80, "UBER TRIP", None, "transport"),
        (-822.03, "NATIONWIDE MORTGAGE", "Nationwide", "housing"),
        (-1650.0, "J SMITH LETTINGS RENT", None, "housing"),
        (-142.0, "OCTOPUS ENERGY", None, "bills"),
        (-22.0, "EE LIMITED", "EE", "bills"),
        (-360.0, "BARCLAYCARD PAYMENT", "Barclaycard", "transfers"),
        (-200.0, "TO EVERYDAY SAVER", None, "savings"),
        (-40.0, "CASH WITHDRAWAL LINK ATM", None, "cash"),
        (-15.0, "INTEREST CHARGED", None, "fees"),
        (2486.32, "NORTHGATE MEDIA LTD SALARY", None, "income"),
        (7.12, "INTEREST PAID", None, "income"),
        (360.0, "PAYMENT RECEIVED - THANK YOU", None, "transfers"),
        (200.0, "FROM CURRENT ACCOUNT", None, "transfers"),
        (19.99, "ASOS REFUND", "ASOS", "shopping"),
        (-5.0, "SOMETHING UNKNOWN", None, "other"),
    ],
)
def test_categorise(amount: float, description: str, merchant: str | None, expected: str) -> None:
    assert categorise(tx("2026-10-01", amount, description, merchant)) == expected


def test_provider_category_used_last() -> None:
    t = tx("2026-10-01", -5.0, "ZZ UNKNOWN")
    t = t.model_copy(update={"provider_category": "EATING_OUT"})
    assert categorise(t) == "eating_out"


def test_merchant_key_ignores_refs_and_digits() -> None:
    a = tx("2026-10-01", -1, "NETFLIX.COM 12345")
    b = tx("2026-11-01", -1, "NETFLIX.COM 99881")
    assert merchant_key(a) == merchant_key(b) == "netflix"


def test_brand_names_with_number_words_keep_their_name() -> None:
    """The mobile network "Three" showed as "this payee" (PENNY_V3_BUILD.md C7). Exact brand matches only."""
    from lifeline_engine.money.categorise import display_name

    assert display_name(tx("2026-10-01", -12.0, "THREE MOBILE", merchant="Three")) == "Three"
    assert display_name(tx("2026-10-01", -10.0, "O2 UK", merchant="O2")) == "O2"
    assert display_name(tx("2026-10-01", -5.0, "SHOP", merchant="Three hundred pounds")) != "Three hundred pounds"
