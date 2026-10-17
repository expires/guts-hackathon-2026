import json

from playyourself.decision.friends import FriendCard, share_card

BAD_WORDS = ("pence", "amount", "balance", "value", "gbp", "£")


def test_schema_has_no_money_fields():
    schema = json.dumps(FriendCard.model_json_schema()).lower()
    for w in BAD_WORDS:
        assert w not in schema
    assert set(FriendCard.model_fields) == {
        "display_name",
        "overall_score",
        "factor_scores",
        "twr_index_final",
        "pie",
    }


async def test_pie_only_when_opted_in(snapshot_for):
    snap = await snapshot_for("steady_saver")
    assert share_card("Me", snap, False).pie is None
    pie = share_card("Me", snap, True).pie
    assert pie and abs(sum(pie.values()) - 100) < 0.5


async def test_card_contains_no_snapshot_amounts(snapshot_for):
    snap = await snapshot_for("steady_saver")
    text = share_card("Me", snap, True).model_dump_json()
    amounts = {str(abs(t.amount_pence)) for t in snap.transactions}
    amounts |= {str(h.value_pence) for h in snap.holdings}
    amounts |= {str(b.value_pence) for b in snap.balances}
    amounts |= {str(snap.liquid_cash_pence), str(snap.isa_value_pence)}
    digits = {n for n in amounts if len(n) >= 5}
    assert digits
    assert not [n for n in digits if n in text]
