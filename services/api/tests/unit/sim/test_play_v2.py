"""Direction V2 Play (ADR 0052, ADR 0059): student paths, Quick Life, Money Quiz bank, Same Decision."""

from __future__ import annotations

from urllib.parse import urlparse

import pytest

from lifeline_contracts.domain import Life
from lifeline_contracts.macro import MacroKey, MacroTable, MacroValue
from lifeline_engine import rules
from lifeline_sim import api
from lifeline_sim.decisions import PROMPT_IDS
from lifeline_sim.errors import SimError
from lifeline_sim.events.engine import templates_by_id
from lifeline_sim.index import load_weights
from lifeline_sim.paths import loan_plan_for, repayment, repayment_threshold, tuition_fee_cap
from lifeline_sim.presets import LEGACY_PRESET_IDS
from lifeline_sim.quick import plan
from lifeline_sim.quiz import BANK, QUIZ_OFFICIAL_DOMAINS, TOPICS, bank_size
from lifeline_sim.replay import replay, view_for

QUICK_PATHS = ("uni", "apprentice", "job18", "gap_year")


def _play_quick(life: Life, macro: MacroTable, pick: str = "default") -> tuple[Life, int, list[str]]:
    """Tap AGE until the Quick Life ends. Returns the life, the number of taps and the event template ids."""
    taps = 0
    templates: list[str] = []
    while not api.quick_finished(life):
        life = api.age(life, macro).life
        taps += 1
        assert len(life.pending_events) <= 1
        for ev in list(life.pending_events):
            templates.append(ev.template_id)
            if pick == "default":
                cid = next(c.id for c in ev.choices if c.is_default)
            else:
                cid = next(c.id for c in ev.choices if not c.is_default)
            life = api.choose(life, ev.id, cid, macro).life
        assert taps <= 6
    return life, taps, templates


# ---------- paths and presets ----------


def test_paths_list() -> None:
    ps = {x.id: x for x in api.paths()}
    assert set(ps) == {"uni", "apprentice", "job18", "gap_year", "masters"}
    assert all(ps[i].quick and ps[i].start_age == 18 for i in QUICK_PATHS)
    assert ps["masters"].start_age == 21


def test_offered_presets_drop_legacy_but_presets_still_load(macro: MacroTable) -> None:
    offered = {c.id for c in api.offered_presets(macro)}
    assert not offered & LEGACY_PRESET_IDS
    assert {f"path-{p}" for p in ("uni", "apprentice", "job18", "gap_year", "masters")} <= offered
    assert {c.id for c in api.presets()} >= LEGACY_PRESET_IDS


def test_path_character_pay_is_share_of_ashe_median(macro: MacroTable) -> None:
    mv = view_for(macro)
    c = next(c for c in api.offered_presets(macro, 2018) if c.id == "path-job18")
    median = mv.value(MacroKey.MEDIAN_PAY, 2018, c.region)
    assert c.annual_income == round(0.55 * median)
    assert c.birth_year == 2000


def test_unknown_path_and_bad_quick_inputs(macro: MacroTable) -> None:
    with pytest.raises(SimError) as e:
        api.new_path_life("x", "banker", 2018, 1, macro)
    assert e.value.code == "not_found"
    with pytest.raises(SimError):
        api.quick_life("x", path_id="masters", seed=1, macro=macro)
    with pytest.raises(SimError):
        api.quick_life("x", path_id="uni", seed=1, macro=macro, start_year=2021)


# ---------- student loan rules ----------


def test_loan_plan_by_course_start() -> None:
    assert loan_plan_for(2010) == "plan1"
    assert loan_plan_for(2012) == "plan2"
    assert loan_plan_for(2022) == "plan2"
    assert loan_plan_for(2023) == "plan5"
    assert tuition_fee_cap(2005) == 0
    assert tuition_fee_cap(2012) == 9000


def test_repayment_uses_rules_table(macro: MacroTable) -> None:
    mv = view_for(macro)
    t2 = rules.get("student_loan_plan2_threshold").value
    t5 = rules.get("student_loan_plan5_threshold").value
    assert repayment_threshold("plan2", 2026, mv) == pytest.approx(t2)
    assert repayment("plan2", 40_000, 2026, mv) == pytest.approx(0.09 * (40_000 - t2))
    assert repayment("plan5", 40_000, 2026, mv) == pytest.approx(0.09 * (40_000 - t5))
    assert repayment("plan2", t2 - 1, 2026, mv) == 0.0
    # Earlier years: the same threshold in that year's prices.
    assert repayment_threshold("plan2", 2018, mv) < t2


def test_uni_life_takes_loans_then_repays(macro: MacroTable) -> None:
    life = api.new_path_life("lf_uni", "uni", 2016, 7, macro)
    assert life.finances.student_loan > 0  # first year's tuition and maintenance
    first = life.finances.student_loan
    for _ in range(3):
        life = api.age(life, macro).life
        for ev in list(life.pending_events):
            life = api.choose(life, ev.id, next(c.id for c in ev.choices if c.is_default), macro).life
    assert life.finances.student_loan > first
    assert life.job is not None and life.job.title == "Graduate"
    assert any("graduated" in h.text for h in life.history)


def test_apprentice_has_no_student_loan(macro: MacroTable) -> None:
    life = api.new_path_life("lf_app", "apprentice", 2016, 7, macro)
    for _ in range(4):
        life = api.age(life, macro).life
        for ev in list(life.pending_events):
            life = api.choose(life, ev.id, next(c.id for c in ev.choices if c.is_default), macro).life
    assert life.finances.student_loan == 0
    assert life.job is not None and life.job.title == "Electrician"


def test_legacy_lives_unchanged_by_student_templates(macro: MacroTable) -> None:
    """Student templates need `on_path`, so a preset life never draws them."""
    nurse = next(c for c in api.presets() if c.id == "nurse-leeds")
    life = api.new_life("lf_n", nurse, "preset", 2006, 3, macro)
    for _ in range(15):
        life = api.age(life, macro).life
        for ev in list(life.pending_events):
            assert "quick" not in templates_by_id()[ev.template_id].t.tags
            life = api.choose(life, ev.id, next(c.id for c in ev.choices if c.is_default), macro).life


# ---------- Quick Life ----------


@pytest.mark.parametrize("seed", range(12))
def test_quick_plan_shape(seed: int) -> None:
    qp = plan(seed, 2018)
    assert len(qp.stops) in (5, 6)
    assert qp.end_year == 2025
    steps = [b - a for a, b in zip((2018, *qp.stops), qp.stops, strict=False)]
    assert all(s in (1, 2) for s in steps) and sum(steps) == 7
    assert len(qp.event_years) in (2, 3)
    assert set(qp.event_years) <= set(qp.stops[:-1])


@pytest.mark.parametrize("path_id", QUICK_PATHS)
@pytest.mark.parametrize("seed", (1, 22, 333))
def test_quick_life_round(path_id: str, seed: int, macro: MacroTable) -> None:
    life = api.quick_life("lf_q", path_id=path_id, seed=seed, macro=macro)
    assert life.age == 18 and api.is_quick(life)
    life, taps, templates = _play_quick(life, macro)
    assert 5 <= taps <= 6
    assert 2 <= len(templates) <= 3
    assert all("quick" in templates_by_id()[t].t.tags for t in templates)
    assert len(set(templates)) == len(templates)
    assert life.age == 25 and life.alive
    with pytest.raises(SimError) as e:
        api.age(life, macro)
    assert e.value.code == "finished"
    s = api.summary(life, macro)
    assert s.habit_score is not None and s.habit_score.overall is not None
    parts = s.habit_score.components.model_dump()
    assert set(parts) == {
        "savings_rate",
        "months_of_cover",
        "spend_stability",
        "discretionary_share",
        "subscription_creep",
        "debt_pressure",
    }
    assert all(v is None or 0 <= v <= 100 for v in parts.values())


def test_quick_life_same_seed_same_life_any_choices(macro: MacroTable) -> None:
    """A room plays the same life: same taps and events whatever each player picks."""
    a, ta, ea = _play_quick(api.quick_life("a", path_id="uni", seed=99, macro=macro), macro, "default")
    b, tb, eb = _play_quick(api.quick_life("b", path_id="uni", seed=99, macro=macro), macro, "other")
    c, tc, ec = _play_quick(api.quick_life("c", path_id="uni", seed=99, macro=macro), macro, "default")
    assert (ta, ea) == (tb, eb) == (tc, ec)
    assert [h.age for h in a.history if h.decision_id is None] == [h.age for h in b.history if h.decision_id is None]
    assert a.model_dump() == {**c.model_dump(), "id": "a"}


def test_quick_life_is_quick_enough(macro: MacroTable) -> None:
    """A round is 5 or 6 AGE taps plus 2 or 3 choices; the server work for it is small."""
    import time

    t0 = time.perf_counter()
    _play_quick(api.quick_life("t", path_id="gap_year", seed=5, macro=macro), macro)
    assert time.perf_counter() - t0 < 10.0


def _want(template_id: str, choice_id: str) -> float:
    """The weekly wants change of a choice (first branch), for picking big-spending or frugal choices."""
    t = templates_by_id()[template_id].t
    c = next(c for c in t.choices if c.id == choice_id)
    e = c.branches[0].effects.get("want_weekly")
    return float(e.eval({})) if e is not None and not isinstance(e, str) else 0.0


def _play_style(path_id: str, seed: int, style: str, macro: MacroTable) -> Life:
    life = api.quick_life("s", path_id=path_id, seed=seed, macro=macro)
    while not api.quick_finished(life):
        life = api.age(life, macro).life
        for ev in list(life.pending_events):
            ranked = sorted(ev.choices, key=lambda c: _want(ev.template_id, c.id))
            pick = ranked[-1] if style == "big" else ranked[0]
            life = api.choose(life, ev.id, pick.id, macro).life
    return life


def _overall(life: Life, macro: MacroTable) -> int:
    h = api.habit_score(life, macro)
    assert h is not None and h.overall is not None
    return h.overall


def test_every_quick_event_moves_wants() -> None:
    """Every Quick Life event offers a choice that raises weekly wants and one that does not."""
    for lt in templates_by_id().values():
        if "quick" in lt.t.tags:
            wants = [_want(lt.t.id, c.id) for c in lt.t.choices]
            assert max(wants) > 0 and max(wants) > min(wants), lt.t.id


@pytest.mark.parametrize("path_id", QUICK_PATHS)
def test_big_spending_scores_clearly_lower(path_id: str, macro: MacroTable) -> None:
    """W-F-1: on the same path and seed, the big-spending choice set scores at least 25 points lower than the
    frugal set (seed 2), and lower on every seed 0 to 7 (mean gap at least 20)."""
    gaps = []
    for seed in range(8):
        big = _overall(_play_style(path_id, seed, "big", macro), macro)
        frugal = _overall(_play_style(path_id, seed, "frugal", macro), macro)
        gaps.append(frugal - big)
    assert gaps[2] >= 25, gaps
    assert min(gaps) >= 5, gaps
    assert sum(gaps) / len(gaps) >= 20, gaps


@pytest.mark.parametrize("path_id", QUICK_PATHS)
def test_savings_at_25_stay_realistic(path_id: str, macro: MacroTable) -> None:
    """W-F-1 bounds on cash + savings at 25 (game money, demo macro table), seeds 0 to 7:
    default choices at most £35,000; frugal choices at most £55,000; big spending at most the frugal amount.
    Apprentice and job-at-18 lives also never save more than 45% of take-home pay over the life."""
    for seed in range(8):
        default, _, _ = _play_quick(api.quick_life("d", path_id=path_id, seed=seed, macro=macro), macro)
        frugal = _play_style(path_id, seed, "frugal", macro)
        big = _play_style(path_id, seed, "big", macro)
        liquid = {k: v.finances.cash + v.finances.savings for k, v in (("d", default), ("f", frugal), ("b", big))}
        assert 0 <= liquid["d"] <= 35_000, (seed, liquid)
        assert liquid["f"] <= 55_000, (seed, liquid)
        assert liquid["b"] <= liquid["f"], (seed, liquid)
        if path_id in ("apprentice", "job18"):
            s = replay(api._spec(default), api._decisions(default), default.year, view_for(macro), load_weights())
            take_home = sum(r[1] for r in s.ledger)
            spending = sum(r[2] for r in s.ledger)
            assert (take_home - spending) / take_home <= 0.45, (seed, take_home, spending)


def test_non_path_life_has_no_habit_score(macro: MacroTable) -> None:
    nurse = next(c for c in api.presets() if c.id == "nurse-leeds")
    life = api.age(api.new_life("n", nurse, "preset", 2006, 1, macro), macro).life
    assert api.summary(life, macro).habit_score is None


# ---------- Money Quiz ----------


def test_quiz_bank_size_and_shape() -> None:
    assert len(BANK) >= 40
    for t in TOPICS:
        assert bank_size(t) >= 15, t
    for raw in BANK:
        assert 2 <= len(raw.choices) <= 4
        assert len(set(raw.choices)) == len(raw.choices), raw.id
        assert raw.source_label and len(raw.explanation) <= 200
        assert (raw.fact_id is None) != (raw.concept_id is None)


def test_rule_questions_cite_official_pages() -> None:
    rule_qs = [r for r in BANK if r.fact_id is not None]
    assert len(rule_qs) >= 35
    for r in rule_qs:
        assert r.fact_id is not None
        fact = rules.get(r.fact_id)
        assert r.source_url == fact.url
        assert urlparse(fact.url).netloc in rules.OFFICIAL_DOMAINS
        assert fact.checked in r.source_label


@pytest.mark.parametrize("topic", TOPICS)
def test_quiz_questions_deterministic(topic: str) -> None:
    a = api.quiz_questions(42, topic=topic, n=10)  # type: ignore[arg-type]
    b = api.quiz_questions(42, topic=topic, n=10)  # type: ignore[arg-type]
    assert [x.model_dump() for x in a] == [x.model_dump() for x in b]
    assert len(a) == 10 and len({x.question.id for x in a}) == 10
    assert [x.question.index for x in a] == list(range(10))
    for item in a:
        ids = [c.id for c in item.question.choices]
        assert item.correct_choice_id in ids
        assert topic == "mixed" or topic in item.topics
    c = api.quiz_questions(43, topic=topic, n=10)  # type: ignore[arg-type]
    assert [x.question.id for x in a] != [x.question.id for x in c]


def test_quiz_correct_answer_is_the_rule_value() -> None:
    for item in api.quiz_questions(1, topic="tax", n=15):
        if item.fact_id is None:
            continue
        fact = rules.get(item.fact_id)
        right = next(c.text for c in item.question.choices if c.id == item.correct_choice_id)
        assert right.replace("£", "").replace(",", "").replace("%", "") == f"{fact.value:g}"


# ---------- Same Decision ----------


def test_decision_prompts(macro: MacroTable) -> None:
    assert len(PROMPT_IDS) >= 12
    prompts = api.decision_prompts(5, n=20, macro=macro)
    assert len(prompts) == len(PROMPT_IDS)
    for pr in prompts:
        assert 2 <= len(pr.options) <= 4
        assert 1990 <= pr.year <= 2026
        outs = api.decision_outcomes(pr.id, macro=macro)
        assert [o.option_id for o in outs] == [o.id for o in pr.options]
        assert all(len(o.note) <= 160 for o in outs)
    assert [p.id for p in api.decision_prompts(5, n=20, macro=macro)] == [p.id for p in prompts]
    assert [p.id for p in api.decision_prompts(6, n=20, macro=macro)] != [p.id for p in prompts]
    near = api.decision_prompts(5, n=2, macro=macro, year=2022)
    assert {p.year for p in near} == {2022}
    assert api.decision_prompts(5, n=1, macro=macro, year=2008)[0].id == "sd-2008-crash"


def test_decision_outcomes_follow_macro_data(macro: MacroTable) -> None:
    base = api.decision_outcome("sd-2008-crash", option_id="shares", macro=macro)
    stock = macro.value(MacroKey.STOCK_RETURN, 2008)
    assert base.game_money_change == round(1000 * stock / 100)
    values = dict(macro.values)
    k = MacroTable.make_key(MacroKey.STOCK_RETURN, 2008, None)
    values[k] = MacroValue(**{**values[k].model_dump(), "value": 12.0})
    changed = api.decision_outcome("sd-2008-crash", option_id="shares", macro=MacroTable(values=values))
    assert changed.game_money_change == 120
    assert api.decision_outcome("sd-2009-rate-cut", option_id="clear", macro=macro).game_money_change == 0
    with pytest.raises(SimError):
        api.decision_outcome("sd-2008-crash", option_id="nope", macro=macro)
    with pytest.raises(SimError):
        api.decision_outcomes("nope", macro=macro)


# ---------- official tables (ADR 0058, BOSS fact check 2) ----------


def test_official_tables_values_and_sources(macro: MacroTable) -> None:
    from lifeline_sim import params
    from lifeline_sim.paths import PG_LOAN_MAX, TUITION_FEE_CAP, pg_loan_max

    assert tuition_fee_cap(2025) == 9535
    assert tuition_fee_cap(2026) == 9790
    assert tuition_fee_cap(2027) == 10050
    mv = view_for(macro)
    assert [pg_loan_max(y, mv) for y in (2024, 2025, 2026, 2027)] == [12_471, 12_858, 13_206, 13_206]
    assert pg_loan_max(2020, mv) < 12_471
    for row in (*TUITION_FEE_CAP, *PG_LOAN_MAX):
        assert urlparse(row.url).netloc in rules.OFFICIAL_DOMAINS
        assert row.checked == "2026-10-17"
    assert params.STUDENT_LOAN_THRESHOLD == rules.get("student_loan_plan2_threshold").value == 29_385
    assert params.STUDENT_LOAN_RATE == 0.09


def test_every_quiz_question_is_on_topic_with_official_source() -> None:
    """V1 O2: student or young-adult money topics only; every question has a source label and official URL."""
    allowed = {"student_finance", "saving", "debt", "tax"}
    for raw in BANK:
        assert raw.topics and set(raw.topics) <= allowed, raw.id
        assert raw.source_label, raw.id
        assert raw.source_url is not None, raw.id
        assert urlparse(raw.source_url).scheme == "https", raw.id
        assert urlparse(raw.source_url).netloc in QUIZ_OFFICIAL_DOMAINS, raw.id
        assert "car" not in raw.text.lower().split(), raw.id
        if raw.fact_id is not None:
            assert raw.source_url == rules.get(raw.fact_id).url
    assert "q.concept.car-costs" not in {r.id for r in BANK}


# ---------- ADR 0061 amendment: credit cap and neutral defaults ----------


def test_quick_defaults_are_neutral() -> None:
    """The default of every Quick Life event changes weekly wants by 0; a frugal and a big option stay."""
    for lt in templates_by_id().values():
        if "quick" not in lt.t.tags:
            continue
        default = next(c for c in lt.t.choices if c.default)
        assert _want(lt.t.id, default.id) == 0, lt.t.id
        wants = [_want(lt.t.id, c.id) for c in lt.t.choices]
        assert min(wants) < 0 < max(wants), lt.t.id


@pytest.mark.parametrize("path_id", QUICK_PATHS)
def test_quick_card_debt_never_above_cap(path_id: str, macro: MacroTable) -> None:
    from lifeline_sim import params

    for seed in range(8):
        default, _, _ = _play_quick(api.quick_life("d", path_id=path_id, seed=seed, macro=macro), macro)
        big = _play_style(path_id, seed, "big", macro)
        assert default.finances.other_debt <= params.QUICK_CREDIT_LIMIT_MAX
        assert default.finances.other_debt == 0, (seed, default.finances.other_debt)
        assert big.finances.other_debt <= params.QUICK_CREDIT_LIMIT_MAX


def test_gap_year_bristol_defaults_no_debt_spiral(macro: MacroTable) -> None:
    """The case that used to end with about £29,000 of card debt (gap year, Bristol, seed 4, defaults)."""
    life, _, _ = _play_quick(api.quick_life("g", path_id="gap_year", seed=4, macro=macro), macro)
    assert life.character.town == "Bristol"
    assert life.finances.other_debt == 0
    assert life.index.missed_payments <= 2
    h = api.habit_score(life, macro)
    assert h is not None and h.overall is not None and h.overall >= 60


def test_big_spender_over_the_limit_gets_missed_payments(macro: MacroTable) -> None:
    big = _play_style("gap_year", 4, "big", macro)
    assert big.index.missed_payments > 0
    h = api.habit_score(big, macro)
    assert h is not None and h.components.debt_pressure is not None and h.components.debt_pressure < 50
