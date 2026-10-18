"""Under 14 days to the next money, Penny and the trace give the total until that date, like the app card."""

from __future__ import annotations

from tests.unit.explain.test_chat_v3_penny import _forecast_tools


def test_short_window_gives_the_total_until_the_date_not_a_week() -> None:
    from lifeline_explain.forecast_tool import forecast_output, until_text

    _, fc = _forecast_tools()
    short = fc.model_copy(update={"budget_period": "until_next_money", "to_spend": round(fc.per_day * fc.days, 2)})
    out = forecast_output(short)
    facts = {f.id: f for f in out.facts}
    assert "forecast.per_week" not in facts
    assert facts["forecast.to_spend"].value == round(short.to_spend, 2)
    assert facts["forecast.to_spend"].label.endswith(f"until {until_text(short)}")
    assert "per_week" not in out.result and out.result["budget_period"] == "until_next_money"


def test_a_long_window_keeps_the_weekly_figure() -> None:
    from lifeline_explain.forecast_tool import forecast_output

    _, fc = _forecast_tools()
    out = forecast_output(fc.model_copy(update={"budget_period": "week"}))
    assert "forecast.per_week" in {f.id for f in out.facts}
