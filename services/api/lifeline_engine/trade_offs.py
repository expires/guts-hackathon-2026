"""Trade-offs for Next Move (ADR 0042): what the user gives up with each move. Pure: no I/O, no clock, no RNG.

The engine writes every trade-off. No LLM writes one. Rules:
- `summary` is one plain-English line of at most 90 characters, with no em dash.
- 1 to 4 points. Every number in a point's text is a value in its `facts` (same rule as EvidencePoint).
- Every number in the summary is a value in the facts of one of the points.
- Per-user values come first (rates, dates, balances, monthly costs). A typical range from TYPICAL is used only
  where no per-user value exists. Each TYPICAL entry names its source.
"""

from __future__ import annotations

from dataclasses import dataclass

from lifeline_contracts.domain import SourceRef
from lifeline_contracts.next_move import EvidencePoint, TradeOff
from lifeline_engine.money.text import gbp, money_value, pct, pct_value, unsupported_numbers

SUMMARY_MAX = 90


@dataclass(frozen=True)
class Typical:
    """A typical range used when there is no per-user value. `source` names where the range comes from."""

    low: float
    high: float
    source: str


# Typical ranges (labelled, not per-user). One table so the verifier and the docs can list them.
TYPICAL: dict[str, Typical] = {
    "mortgage_erc_pct": Typical(
        1.0, 5.0, "MoneyHelper, early repayment charges: usually 1% to 5% of the amount you owe"
    ),
    "mortgage_overpay_pct": Typical(
        10.0, 10.0, "MoneyHelper, overpaying your mortgage: most fixed deals let you overpay 10% a year with no fee"
    ),
    "savings_notice_days": Typical(
        30.0, 120.0, "MoneyHelper, savings accounts: notice accounts usually need 30 to 120 days' notice"
    ),
    "energy_exit_fee_gbp": Typical(
        25.0, 75.0, "Ofgem, fixed tariffs: exit fees are usually £25 to £75 per fuel (supplier tariff sheets)"
    ),
    "energy_free_exit_days": Typical(
        49.0, 49.0, "Ofgem supply licence: no exit fee to switch in the last 49 days of a fixed deal"
    ),
    "single_share_swing_pct": Typical(
        35.0, 35.0, "Typical yearly swing (standard deviation) of one large company's shares; labelled assumption"
    ),
    "broad_fund_swing_pct": Typical(
        15.0, 15.0, "Typical yearly swing (standard deviation) of a global index fund; labelled assumption"
    ),
}


def typical_ref(key: str) -> SourceRef:
    t = TYPICAL[key]
    return SourceRef(source="typical", series_id=key, status="cached", note=t.source)


def point(text: str, facts: dict[str, float], source: SourceRef | None = None) -> EvidencePoint:
    bad = unsupported_numbers(text, facts)
    if bad:
        raise ValueError(f"trade-off number not in facts: {bad} in {text!r}")
    return EvidencePoint(text=text, facts=facts, source=source)


def make(summary: str, points: list[EvidencePoint]) -> TradeOff:
    """Check the summary rules, then build the TradeOff."""
    if len(summary) > SUMMARY_MAX:
        raise ValueError(f"trade-off summary over {SUMMARY_MAX} characters: {summary!r}")
    if "—" in summary or any("—" in p.text for p in points):
        raise ValueError("em dash in trade-off text")
    all_facts = {f"{i}_{k}": v for i, p in enumerate(points) for k, v in p.facts.items()}
    bad = unsupported_numbers(summary, all_facts)
    if bad:
        raise ValueError(f"trade-off summary number not in facts: {bad} in {summary!r}")
    return TradeOff(summary=summary, points=points)


def _fit(name: str, room: int) -> str:
    """Shorten a display name so a summary stays within SUMMARY_MAX."""
    return name if len(name) <= room else name[: max(1, room - 3)].rstrip() + "..."


# ---------- mortgage ----------


def mortgage(
    option: str,
    balance: float,
    rate_pct: float,
    deal_start_year: int,
    fix_years: int | None,
    one_point_extra_monthly: float,
    stress_text: str,
    stress_facts: dict[str, float],
    stress_bank_from: float | None,
    stress_bank_to: float | None,
) -> TradeOff:
    """fix_mortgage, remortgage. A fix gives up flexibility (early repayment charge) and any gain if rates fall.
    A tracker gives up payment certainty."""
    erc = TYPICAL["mortgage_erc_pct"]
    lo, hi = balance * erc.low / 100, balance * erc.high / 100
    erc_facts = {
        "erc_low_pct": erc.low,
        "erc_high_pct": erc.high,
        "erc_low": money_value(lo),
        "erc_high": money_value(hi),
        "balance": money_value(balance),
    }
    if fix_years is not None:
        until = deal_start_year + fix_years
        over = TYPICAL["mortgage_overpay_pct"]
        points = [
            point(
                f"Leaving before {until} usually costs {erc.low:g}% to {erc.high:g}% of what you owe: "
                f"{gbp(lo)} to {gbp(hi)} on {gbp(balance)}.",
                {"until_year": float(until), **erc_facts},
                typical_ref("mortgage_erc_pct"),
            ),
            point(
                f"If rates fall, you still pay {pct(rate_pct)} until {until}.",
                {"fixed_rate": pct_value(rate_pct), "until_year": float(until)},
            ),
            point(
                f"Most fixed deals let you overpay up to {over.low:g}% a year with no fee.",
                {"overpay_pct": over.low},
                typical_ref("mortgage_overpay_pct"),
            ),
        ]
        return make(f"Fixed until {until}: a fee to leave early, and no gain if rates fall", points)
    points = [
        point(
            f"Your rate moves with Bank Rate. A rise of 1 point adds about {gbp(one_point_extra_monthly)} a month.",
            {"rise_points": 1.0, "extra_monthly": money_value(one_point_extra_monthly)},
        ),
    ]
    if stress_bank_from is not None and stress_bank_to is not None:
        points.append(
            point(
                f"In {stress_text}, Bank Rate went from {pct(stress_bank_from)} to {pct(stress_bank_to)}.",
                {"bank_from": pct_value(stress_bank_from), "bank_to": pct_value(stress_bank_to), **stress_facts},
            )
        )
    points.append(
        point(
            f"Some trackers charge {erc.low:g}% to {erc.high:g}% of what you owe if you leave early.",
            {"erc_low_pct": erc.low, "erc_high_pct": erc.high},
            typical_ref("mortgage_erc_pct"),
        )
    )
    return make("Your payment goes up if Bank Rate goes up", points)


# ---------- savings ----------


def move_savings(best_rate_now: float, fall: tuple[int, float, float] | None) -> TradeOff:
    """The new rate can change, and higher rates often need notice or a fixed term.
    `fall`: (year, rate before, rate after) of the largest past one-year fall in top easy-access rates."""
    notice = TYPICAL["savings_notice_days"]
    first = f"The {pct(best_rate_now)} rate is not fixed. The bank can cut it at any time."
    facts: dict[str, float] = {"best_rate": pct_value(best_rate_now)}
    if fall is not None:
        year, before, after = fall
        first += f" In {year}, top easy-access rates fell from {pct(before)} to {pct(after)}."
        facts |= {"fall_year": float(year), "from_rate": pct_value(before), "to_rate": pct_value(after)}
    points = [
        point(first, facts),
        point(
            f"Some higher rates need notice to take money out, usually {notice.low:g} to {notice.high:g} days, "
            "or lock it away for a fixed term.",
            {"notice_low_days": notice.low, "notice_high_days": notice.high},
            typical_ref("savings_notice_days"),
        ),
        point("Some top-rate accounts limit how often you can take money out each year.", {}),
    ]
    return make("The rate can change, and some top rates need notice to take money out", points)


# ---------- subscriptions ----------


def cancel_subscription(name: str, amount: float, per: str, new_price: float | None) -> TradeOff:
    points = [
        point(
            f"You stop paying {gbp(amount, True)} {per}, and you lose {name}.",
            {"amount": money_value(amount, True)},
        )
    ]
    if new_price is not None and money_value(new_price, True) != money_value(amount, True):
        points.append(
            point(
                f"If you join again later, you pay the new price of {gbp(new_price, True)} {per}.",
                {"new_price": money_value(new_price, True)},
            )
        )
    points.append(point("Some services delete your saved items or history after you cancel.", {}))
    return make(f"You lose {_fit(name, SUMMARY_MAX - 30)} and anything saved in it", points)


def switch_subscription(name: str, saving_monthly: float) -> TradeOff:
    points = [
        point(
            f"The cheaper plan saves {gbp(saving_monthly, True)} a month, but it has fewer features or adds ads.",
            {"saving_monthly": money_value(saving_monthly, True)},
        ),
        point("You may lose extras such as offline use, more screens or better quality.", {}),
    ]
    return make(f"Fewer features on the cheaper {_fit(name, SUMMARY_MAX - 30)} plan", points)


# ---------- energy ----------


def switch_energy(monthly_cost: float, fell: int, periods: int) -> TradeOff:
    fee = TYPICAL["energy_exit_fee_gbp"]
    free = TYPICAL["energy_free_exit_days"]
    points = [
        point(
            f"Leaving a fixed deal early usually costs {gbp(fee.low)} to {gbp(fee.high)} per fuel. "
            f"There is no fee in the last {free.low:g} days of the deal.",
            {"fee_low": fee.low, "fee_high": fee.high, "free_days": free.low},
            typical_ref("energy_exit_fee_gbp"),
        ),
        point(
            f"If prices fall, you still pay about {gbp(monthly_cost)} a month until the fix ends.",
            {"monthly": money_value(monthly_cost)},
        ),
    ]
    if fell > 0:
        points.append(
            point(
                f"Prices fell in {fell} of {periods} similar past years.",
                {"fell": float(fell), "periods": float(periods)},
            )
        )
    return make("A fee if you leave early, and no saving if prices fall", points)


# ---------- debt ----------


def pay_off_debt(
    mode: str,
    amount: float,
    monthly: float,
    savings_left: float,
    months_left: float | None,
    savings_rate: float,
    card_rate: float,
    savings_rate_known: bool = True,
    word: str = "spending",
    target: str = "your card",
) -> TradeOff:
    """`word`: 'spending' or 'regular costs' (ADR 0057). `target`: 'your card', 'your overdraft' (F-V2-3).
    mode: 'savings' (lump sum from savings), 'surplus' (monthly spare money) or 'cut' (cut spending).
    `months_left` is None when monthly costs are not known (ADR 0053 bug 5): that point is left out.
    `savings_rate_known` False: the rate is the UK average and the text says so (ADR 0053 bug 6)."""
    if mode == "savings":
        lost = amount * savings_rate / 100
        rate_text = (
            f"You lose about {pct(savings_rate)} interest on {gbp(amount)}: {gbp(lost)} a year."
            if savings_rate_known
            else f"At the UK average savings rate of {pct(savings_rate)}, {gbp(amount)} earns about {gbp(lost)} a year."
        )
        points = []
        if months_left is not None:
            points.append(
                point(
                    f"Your savings drop to {gbp(savings_left)}, about {months_left:g} months of {word}.",
                    {"savings_left": money_value(savings_left), "months_left": months_left},
                )
            )
        points += [
            point(
                rate_text,
                {"savings_rate": pct_value(savings_rate), "amount": money_value(amount), "lost": money_value(lost)},
            ),
            point(
                f"If a surprise bill comes, you may need to borrow again at about {pct(card_rate)}.",
                {"card_rate": pct_value(card_rate)},
            ),
        ]
        return make(f"Less cash on hand: your savings drop to {gbp(savings_left)}", points)
    points = [
        point(
            f"{gbp(monthly)} a month goes to {target}, so it does not go to savings or spending.",
            {"monthly": money_value(monthly)},
        ),
    ]
    if months_left is not None:
        points.append(
            point(
                f"Your cash and savings cover about {months_left:g} months of {word} while you pay it down."
                if months_left >= 0.5
                else "You have almost no cash to fall back on while you pay it down.",
                {"months_left": months_left} if months_left >= 0.5 else {},
            )
        )
    return make(f"{gbp(monthly)} a month less to spend or save", points)


# ---------- emergency fund ----------


def emergency_fund(
    amount: float,
    savings_rate: float,
    stock_return: float | None,
    first_year: int | None,
    last_year: int | None,
    savings_rate_known: bool = True,
    invests: bool = True,
) -> TradeOff:
    """Cash kept for emergencies is not invested, so its expected growth is lower. `savings_rate_known` False:
    the rate is the UK average and the text says so (ADR 0053 bug 6). `invests` False (most students, ADR 0070):
    the trade-off is less to spend while the safety net builds, never investing words."""
    points = [
        point(
            f"{gbp(amount)} kept as cash earns about {pct(savings_rate)} a year."
            if savings_rate_known
            else f"{gbp(amount)} kept as cash earns about {pct(savings_rate)} a year at the UK average savings rate.",
            {"amount": money_value(amount), "savings_rate": pct_value(savings_rate)},
        )
    ]
    if not invests:
        points += [
            point("While you build it, nights out and treats get less of each week's money.", {}),
            point("Keep it in a separate savings account, so it does not get spent by mistake.", {}),
        ]
        return make(f"{gbp(amount)} less to spend while you build it", points)
    if stock_return is not None and first_year is not None and last_year is not None:
        points.append(
            point(
                f"UK shares returned {pct(stock_return)} a year on average from {first_year} to {last_year}, "
                "but they can fall just when you need the money.",
                {"stock_return": pct_value(stock_return), "first_year": float(first_year),
                 "last_year": float(last_year)},
            )
        )
        gap = amount * (stock_return - savings_rate) / 100
        if gap > 0:
            points.append(
                point(
                    f"On {gbp(amount)}, that is about {gbp(gap)} a year less growth on average.",
                    {"amount": money_value(amount), "gap": money_value(gap)},
                )
            )
    return make("Less money invested, so lower expected growth", points)


# ---------- budget ----------


def cut_budget(category: str, excess: float, average: float, over: int, history: int) -> TradeOff:
    points = [
        point(
            f"You spend {gbp(excess)} a month less on {category}, back to {gbp(average)}.",
            {"excess": money_value(excess), "average": money_value(average)},
        ),
        point(
            f"You spent more than that in {over} of the last {history} months.",
            {"over": float(over), "history": float(history)},
        ),
    ]
    return make(f"{gbp(excess)} a month less to spend on {_fit(category, SUMMARY_MAX - 40)}", points)


# ---------- student moves (ADR 0046) ----------


def weekly_budget(
    safe_weekly: float, pace: float, bills: float, day_text: str, day_facts: dict[str, float]
) -> TradeOff:
    cut = max(0.0, pace - safe_weekly)
    points = [
        point(
            f"You spend {gbp(cut)} a week less than your recent pace until {day_text}.",
            {"cut": money_value(cut), **day_facts},
        ),
    ]
    if bills > 0:
        points.append(point(f"{gbp(bills)} for regular bills is kept aside first.", {"bills": money_value(bills)}))
    points.append(point("Nights out and treats need to fit inside the weekly amount.", {}))
    return make(f"{gbp(cut)} a week less to spend until {day_text}", points)


def keep_buffer(cash: float) -> TradeOff:
    """The nothing-urgent fallback: keep the safety net. No investing words (ADR 0070)."""
    points = [
        point(f"Your {gbp(cash)} of cash stays your safety net.", {"cash": money_value(cash)}),
        point("Money kept for emergencies is not for nights out or treats.", {}),
    ]
    return make("Money in your safety net is not for everyday spending", points)


def on_track(spare: float, pace: float, day_text: str, day_facts: dict[str, float]) -> TradeOff:
    """No shortfall before the next payment (ADR 0070): the move keeps the usual pace and saves what is spare."""
    points = [
        point(f"You keep to about {gbp(pace)} a week until {day_text}.", {"pace": money_value(pace), **day_facts}),
        point("A big night out or a trip has to fit inside that, or come out of the spare money.", {}),
    ]
    if spare > 0:
        points.append(point(f"{gbp(spare)} moves out of your current account, so it is not there to spend on a "
                            "whim. You can move it back the same day.", {"spare": money_value(spare)}))
        return make(f"{gbp(spare)} less in your current account until {day_text}", points)
    return make(f"No more than about {gbp(pace)} a week until {day_text}", points)


def shortfall(short: float, bills: float, day_text: str, day_facts: dict[str, float]) -> TradeOff:
    """Bills alone take all the cash before the next payment: there is nothing safe to spend."""
    points = [
        point(
            f"{gbp(bills)} of regular bills come first, so nothing is left to spend safely until {day_text}.",
            {"bills": money_value(bills), **day_facts},
        ),
        point(
            f"Borrowing the {gbp(short)} on an overdraft or card costs interest. Family or your university's "
            "hardship fund cost nothing.",
            {"short": money_value(short)},
        ),
    ]
    return make(f"Nothing safe to spend until {day_text}: bills come first", points)


def lifetime_isa(contribution: float, bonus: float, loss: float, charge_pct: float, house_limit: float,
                 free_age: float) -> TradeOff:
    back = contribution + bonus - (contribution + bonus) * charge_pct / 100
    points = [
        point(
            f"Taking money out for anything but a first home costs {charge_pct:g}%. On {gbp(contribution)} paid in "
            f"you would get back {gbp(back)}, {gbp(loss)} less than you put in.",
            {"charge_pct": charge_pct, "contribution": money_value(contribution), "back": money_value(back),
             "loss": money_value(loss)},
        ),
        point(
            f"The money is for a first home costing up to {gbp(house_limit)}, or for after age {free_age:g}.",
            {"house_limit": money_value(house_limit), "free_age": free_age},
        ),
        point("Money in it is not there for emergencies.", {}),
    ]
    return make(f"A {charge_pct:g}% charge if you take it out for anything but a first home", points)


def keep_cash(savings: float, rate: float, cpi: float, year: int, invests: bool = True) -> TradeOff:
    real = savings * (cpi - rate) / 100
    if real > 0:
        first = point(
            f"Prices rose {pct(cpi)} in {year}. Your rate is {pct(rate)}, so your {gbp(savings)} buys about "
            f"{gbp(real)} less after a year.",
            {"cpi": pct_value(cpi), "year": float(year), "rate": pct_value(rate), "savings": money_value(savings),
             "real_loss": money_value(real)},
        )
    else:
        first = point(
            f"Prices rose {pct(cpi)} in {year}, less than your {pct(rate)} rate. A rate cut can change that.",
            {"cpi": pct_value(cpi), "year": float(year), "rate": pct_value(rate)},
        )
    later = (point("Over many years, cash usually grows less than money invested.", {}) if invests
             else point("Check your rate each term: banks often cut it without telling you.", {}))
    points = [first, later]
    return make("Rising prices can make your cash worth less over time", points)
