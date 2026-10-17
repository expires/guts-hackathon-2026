from types import SimpleNamespace

import pytest

from playyourself.decision.explain import SCENARIO_LABEL, explain, numbers_grounded
from playyourself.settings import Settings

RESULTS = {
    "habit_vector": {"scores": {"saving_rate": 62, "discretionary_share": 0.18}},
    "backtest": {"twr": 0.084, "max_drawdown": -0.12},
    "scenarios": {"scenarios": [{"name": "2008-like", "p10": -0.2, "p50": 0.03}]},
    "spending": {
        "insights": [
            "Eating out is up 34% vs the previous 6 months",
            "3 unusual transactions this period",
        ],
        "top_categories": [{"category": "eating_out", "share_pct": 21.5}],
    },
}


class FakeClient:
    def __init__(self, text=None, exc=None):
        self.calls = 0
        self.kwargs = None
        self.messages = self
        self._text, self._exc = text, exc

    def create(self, **kw):
        self.calls += 1
        self.kwargs = kw
        if self._exc:
            raise self._exc
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self._text)])


@pytest.mark.parametrize("kind", list(RESULTS))
def test_templates(kind):
    e = explain(kind, RESULTS[kind], settings=Settings(anthropic_api_key="", _env_file=None))
    assert e.source == "template" and e.model is None and e.text
    assert numbers_grounded(e.text, RESULTS[kind])


def test_scenarios_label_and_missing_keys():
    assert SCENARIO_LABEL in explain("scenarios", RESULTS["scenarios"]).text
    for kind in RESULTS:
        assert explain(kind, {}).text


def test_llm_grounded():
    c = FakeClient("Your saving rate is 62 and the discretionary share is 18%.")
    e = explain("habit_vector", RESULTS["habit_vector"], client=c)
    assert e.source == "llm" and e.model and c.calls == 1
    assert c.kwargs["max_tokens"] == 400 and c.kwargs["messages"][0]["role"] == "user"


def test_llm_scenario_label_enforced():
    c = FakeClient("A modelled scenario shows 3% in the middle case.")
    e = explain("scenarios", RESULTS["scenarios"], client=c)
    assert e.source == "llm" and SCENARIO_LABEL in e.text


def test_llm_ungrounded_falls_back():
    c = FakeClient("Your saving rate is 99.")
    e = explain("habit_vector", RESULTS["habit_vector"], client=c)
    assert e.source == "template"


def test_llm_exception_falls_back():
    e = explain("backtest", RESULTS["backtest"], client=FakeClient(exc=RuntimeError("boom")))
    assert e.source == "template"


def test_no_key_no_call(monkeypatch):
    import anthropic

    def boom(*a, **k):
        raise AssertionError("must not construct a client")

    monkeypatch.setattr(anthropic, "Anthropic", boom)
    e = explain(
        "backtest", RESULTS["backtest"], settings=Settings(anthropic_api_key="", _env_file=None)
    )
    assert e.source == "template"


def test_numbers_grounded():
    r = {"a": 0.084, "b": 1234.5}
    assert numbers_grounded("Return of 8.4% and £1,234.5", r)
    assert numbers_grounded("about 8%", r)
    assert not numbers_grounded("about 9%", r)


def test_spending_template_uses_insights_and_categories():
    text = explain("spending", RESULTS["spending"]).text
    assert "Eating out is up 34% vs the previous 6 months." in text
    assert "eating out 21.5%" in text
