"""Build contracts/openapi.yaml. BOSS-owned.

Run: make contract   (or: cd services/api && uv run python ../../contracts/build_openapi.py)

Schemas come from lifeline_contracts (single source of truth for wire shapes).
Examples are model instances, so each example is valid against its schema by construction.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "services" / "api"))

from lifeline_contracts import api_models as A  # noqa: E402
from lifeline_contracts import accounts as ACC  # noqa: E402
from lifeline_contracts import domain as D  # noqa: E402
from lifeline_contracts import finance as F  # noqa: E402
from lifeline_contracts import friends as FR  # noqa: E402
from lifeline_contracts import habits as H  # noqa: E402
from lifeline_contracts import insights as INS  # noqa: E402
from lifeline_contracts import investing as I  # noqa: E402,E741
from lifeline_contracts import next_move as N  # noqa: E402
from lifeline_contracts.observation import Observation, SourceStatus  # noqa: E402

MODELS: list[type[BaseModel]] = [
    A.Error,
    A.Health,
    A.SourcesResponse,
    A.CharactersResponse,
    A.CreateLifeRequest,
    A.ChoiceRequest,
    A.ActionRequest,
    A.RewindRequest,
    A.ConceptsResponse,
    A.ChallengesResponse,
    A.DecisionRequest,
    A.CreateRoomRequest,
    A.Room,
    A.Player,
    A.BankAuthLink,
    A.BankSummary,
    A.PurchaseVerifyRequest,
    A.PurchaseVerifyResponse,
    A.AppleSignInRequest,
    A.DemoSignInRequest,
    A.Token,
    A.WsClientMessage,
    A.WsServerMessage,
    D.Life,
    D.AgeResult,
    D.ChoiceResult,
    D.ActionResult,
    D.RewindResult,
    D.LifeSummary,
    D.Decision,
    D.Evaluation,
    Observation,
    SourceStatus,
    F.FinanceOverview,
    F.SpendingResponse,
    INS.SpendingInsights,
    F.SubscriptionsResponse,
    F.BillsResponse,
    F.BudgetsResponse,
    F.UpdateBudgetsRequest,
    F.GoalsResponse,
    F.SavingsGoal,
    F.CreateGoalRequest,
    F.FinanceProfile,
    F.LivesResponse,
    F.SpendPrediction,
    F.GuessRequest,
    F.GuessesResponse,
    F.PredictionEvaluation,
    N.NextMoveResponse,
    N.TestMoveRequest,
    N.TestMoveResult,
    N.AddPlanItemRequest,
    N.PlanItem,
    N.PlanResponse,
    ACC.ConnectionsResponse,
    ACC.ProviderConnection,
    ACC.Trading212ConnectRequest,
    ACC.MonzoTokenRequest,
    ACC.HistoryStatus,
    F.InvestmentsResponse,
    H.HabitFactors,
    I.IsaBacktestQuery,
    I.IsaBacktestResponse,
    I.IsaScenariosQuery,
    I.IsaScenariosResult,
    I.IsaPeriodsResponse,
    FR.FriendCard,
    FR.LeaderboardEntry,
    FR.Leaderboard,
    FR.InviteCode,
    FR.JoinFriendRequest,
    FR.ShareSettings,
]


def _clean(node: Any) -> Any:
    """Make pydantic JSON Schema friendly to swift-openapi-generator.

    - Drop `title` noise.
    - Turn `anyOf: [X, {type: null}]` into X. Optional fields are already absent from `required`,
      and the server omits None values (response_model_exclude_none).
    """
    if isinstance(node, dict):
        if "anyOf" in node:
            non_null = [s for s in node["anyOf"] if s != {"type": "null"}]
            if len(non_null) == 1 and len(non_null) < len(node["anyOf"]):
                merged = {k: v for k, v in node.items() if k not in ("anyOf", "default")}
                merged.update(non_null[0])
                node = merged
        out = {}
        for k, v in node.items():
            if k == "title" and isinstance(v, str):
                continue
            if k == "default" and v is None:
                continue
            out[k] = _clean(v)
        return out
    if isinstance(node, list):
        return [_clean(x) for x in node]
    return node


def schemas() -> dict[str, Any]:
    _, top = models_json_schema([(m, "serialization") for m in MODELS], ref_template="#/components/schemas/{model}")
    defs = top["$defs"]
    return {k: _clean(v) for k, v in sorted(defs.items())}


def ex(model: BaseModel) -> Any:
    return model.model_dump(mode="json", exclude_none=True)


# ---------------- examples ----------------

NURSE = D.CharacterSpec(
    id="nurse-leeds",
    name="Amira",
    emoji="👩🏽‍⚕️",
    sex="female",
    occupation="nurse",
    region="yorkshire-and-the-humber",
    town="Leeds",
    birth_year=1982,
    annual_income=24800,
    savings=3200,
    debt=1500,
    housing="rent",
    blurb="NHS nurse renting in Leeds.",
)
BANKER = D.CharacterSpec(
    id="banker-london",
    name="Tom",
    emoji="👨🏻‍💼",
    sex="male",
    occupation="banker",
    region="london",
    town="London",
    birth_year=1979,
    annual_income=92000,
    savings=41000,
    housing="mortgage",
    property_value=410000,
    mortgage_balance=290000,
    blurb="Investment banker with a flat in Canary Wharf.",
)
SRC_BOE = D.SourceRef(source="boe", series_id="IUMBEDR", status="live")
SRC_HPI = D.SourceRef(source="landregistry", series_id="ukhpi/yorkshire-and-the-humber", status="cached")
EVENT = D.Event(
    id="ev-2008-1",
    template_id="home.rent_rise",
    area="home",
    year=2008,
    age=26,
    emoji="🏠",
    title="Your rent is going up",
    text="Your landlord wants £45 more a month. Rents in your area rose 4.1% this year.",
    choices=[
        D.Choice(id="accept", label="Pay it", emoji="💷", hint="-£540 a year", is_default=True),
        D.Choice(id="move", label="Move somewhere cheaper", emoji="📦", hint="-£600 once, then -£360 a year"),
    ],
    facts={"rent_increase_monthly": 45, "rent_change_pct": 4.1},
    sources=[D.SourceRef(source="ons", series_id="IPHRP", status="cached", note="UK average used")],
    concept_id="inflation",
)
LESSON = D.Lesson(
    concept_id="inflation",
    title="Prices creep up",
    chart=D.Chart(
        kind="line",
        title="Rent change per year",
        x_label="Year",
        y_label="%",
        points=[D.ChartPoint(x=2006, y=3.2), D.ChartPoint(x=2007, y=3.9), D.ChartPoint(x=2008, y=4.1)],
        source=D.SourceRef(source="ons", series_id="IPHRP", status="cached"),
    ),
    sentences=["When prices rise, the same money buys less.", "Your rent rose faster than your pay this year."],
    quiz=D.Quiz(
        question="If rent rises 4% and pay rises 2%, are you better off?", options=["Yes", "No", "Same"], answer_index=1
    ),
)
STATS = D.Stats(happiness=72, health=88, smarts=64, money=41)
FIN = D.Finances(
    cash=1200,
    savings=3200,
    investments=0,
    crypto=0,
    pension=4100,
    property_value=0,
    mortgage_balance=0,
    other_debt=1500,
    student_loan=18000,
    annual_income=24800,
    monthly_costs=1450,
    net_worth=-11000,
)
LIFE = D.Life(
    id="lf_8f3a2c",
    seed=424242,
    mode="preset",
    character=NURSE,
    start_year=2006,
    year=2008,
    age=26,
    alive=True,
    stats=STATS,
    finances=FIN,
    index=D.IndexState(value=101.4, r_player=-0.36, r_autopilot=-0.40, missed_payments=0, max_drawdown=0.05),
    job=D.Job(
        title="Staff nurse",
        employer="Leeds Teaching Hospitals",
        annual_income=24800,
        years_in_role=2,
        employer_status="active",
    ),
    assets=[D.Asset(id="as1", kind="pension", name="NHS pension", value=4100)],
    relationships=[D.Relationship(id="rl1", kind="parent", name="Mum", emoji="👩🏽", closeness=80)],
    pending_events=[EVENT],
    available_actions=[
        D.AvailableAction(tab="job", id="ask_raise", label="Ask for a pay rise", emoji="🙋"),
        D.AvailableAction(
            tab="money", id="open_isa", label="Open a savings account", emoji="🏦", hint="Tax-free savings"
        ),
    ],
    history=[
        D.YearLog(
            year=2007,
            age=25,
            text="You started at Leeds General.",
            net_worth=-12500,
            autopilot_net_worth=-12500,
            index=100.0,
        )
    ],
    ribbons=[],
    concepts_unlocked=["compound-interest"],
    rewind=D.RewindState(free_left=1, has_pass=False),
)
OUTCOME = D.Outcome(
    event_id="ev-2008-1",
    choice_id="move",
    text="You moved to a cheaper flat in Headingley.",
    deltas=D.Deltas(money=-600, happiness=-3),
    facts={"one_off_cost": 600},
    good=True,
)
NOW = "2026-10-17T12:00:00Z"


def examples() -> dict[str, Any]:
    from datetime import UTC, datetime

    fetched = datetime(2026, 10, 17, 11, 0, 0, tzinfo=UTC)
    room = A.Room(
        code="K7Q2ZP",
        mode="duel",
        seed=777001,
        preset_id="nurse-leeds",
        start_year=2021,
        max_players=2,
        players=[A.Player(id="p1", name="Ash", is_host=True)],
        join_url="lifeline://join/K7Q2ZP",
        qr_png_base64="iVBORw0KGgo=",
        status="lobby",
    )
    profile = D.DecisionProfile(
        age=34,
        region="yorkshire-and-the-humber",
        annual_income=38000,
        savings=9000,
        housing="mortgage",
        property_value=240000,
        mortgage_balance=180000,
        mortgage_years_left=25,
        deal_ends_in_months=3,
    )
    return {
        "Health": A.Health(
            status="ok", version="0.1.0", product="Lifeline", time=NOW, checks={"postgres": "ok", "redis": "ok"}
        ),
        "Sources": A.SourcesResponse(
            sources=[
                SourceStatus(
                    id="boe",
                    name="Bank of England IADB",
                    status="live",
                    fetched_at=fetched,
                    ttl_seconds=86400,
                    coverage="UK",
                    attribution="Bank of England",
                    licence="Bank of England terms",
                ),
                SourceStatus(
                    id="companieshouse",
                    name="Companies House",
                    status="mock",
                    ttl_seconds=86400,
                    coverage="UK",
                    attribution="Companies House",
                    licence="OGL v3.0",
                    needs_key=True,
                    last_error="COMPANIES_HOUSE_KEY not set",
                ),
            ]
        ),
        "Characters": A.CharactersResponse(
            presets=[NURSE, BANKER],
            random=NURSE.model_copy(
                update={"id": "random-424242", "name": "Jordan", "occupation": "plumber", "town": "Bradford"}
            ),
        ),
        "CreateLife": A.CreateLifeRequest(mode="preset", preset_id="nurse-leeds", start_year=2006, seed=424242),
        "CreateLifeSelf": A.CreateLifeRequest(
            mode="self",
            start_year=2026,
            character=NURSE.model_copy(update={"id": None, "name": "Me", "birth_year": 1992, "annual_income": 38000}),
        ),
        "Life": LIFE,
        "AgeResult": D.AgeResult(life=LIFE, events=[EVENT]),
        "Choice": A.ChoiceRequest(event_id="ev-2008-1", choice_id="move"),
        "ChoiceResult": D.ChoiceResult(
            life=LIFE.model_copy(update={"pending_events": []}),
            outcome=OUTCOME,
            lesson=LESSON,
            concept_unlocked="inflation",
        ),
        "ChoiceDefault": A.ChoiceRequest(event_id="ev-2008-1", choice_id="accept"),
        "ChoiceResultDefault": D.ChoiceResult(
            life=LIFE.model_copy(update={"pending_events": []}),
            outcome=D.Outcome(
                event_id="ev-2008-1",
                choice_id="accept",
                text="You paid the higher rent.",
                deltas=D.Deltas(money=-540, happiness=-1),
                facts={"yearly_cost": 540},
                good=False,
            ),
        ),
        "Action": A.ActionRequest(tab="money", action_id="open_isa", params={"amount": 1000}),
        "ActionResult": D.ActionResult(
            life=LIFE,
            outcome=OUTCOME.model_copy(
                update={"event_id": "action", "choice_id": "open_isa", "text": "You opened a savings account."}
            ),
        ),
        "Rewind": A.RewindRequest(decision_id="ev-2008-1"),
        "RewindResult": D.RewindResult(life=LIFE, abandoned_index=96.2, abandoned_net_worth=-12100),
        "Summary": D.LifeSummary(
            life_id="lf_8f3a2c",
            name="Amira",
            born=1982,
            died=2061,
            age=79,
            cause_of_death="Old age",
            final_index=118.5,
            net_worth=312000,
            autopilot_net_worth=241000,
            ribbons=[D.Ribbon(id="steady", title="Steady Hand", emoji="🎗️", reason="No missed payments in 2008")],
            key_moments=[D.KeyMoment(year=2008, age=26, emoji="📉", text="Kept saving through the crash")],
            concepts_unlocked=14,
            timeline=LIFE.history,
        ),
        "Concepts": A.ConceptsResponse(
            concepts=[
                D.Concept(
                    id="inflation",
                    title="Inflation",
                    emoji="🎈",
                    area="money",
                    summary="Prices rise over time.",
                    lesson=LESSON,
                ),
                D.Concept(
                    id="fixed-vs-variable",
                    title="Fixed or variable",
                    emoji="🔒",
                    area="home",
                    summary="A fix keeps your payment the same. A variable rate moves with Bank Rate.",
                    lesson=D.Lesson(
                        concept_id="fixed-vs-variable",
                        title="Lock it or let it move",
                        chart=D.Chart(
                            kind="line",
                            title="Bank Rate at year end",
                            x_label="Year",
                            y_label="%",
                            points=[
                                D.ChartPoint(x=2021, y=0.25),
                                D.ChartPoint(x=2022, y=3.5),
                                D.ChartPoint(x=2023, y=5.25),
                            ],
                            source=D.SourceRef(source="boe", series_id="IUMBEDR", status="live"),
                        ),
                        sentences=[
                            "A fixed rate costs a little more when rates fall but protects you when they rise.",
                            "In 2022 Bank Rate rose from 0.25% to 3.5%, so variable payments jumped.",
                        ],
                        quiz=D.Quiz(
                            question="Rates are about to rise fast. Which payment stays the same?",
                            options=["Fixed", "Variable", "Tracker"],
                            answer_index=0,
                        ),
                        personal="Your deal ends in 165 days.",
                    ),
                ),
                D.Concept(
                    id="subscriptions",
                    title="Subscriptions",
                    emoji="📺",
                    area="money",
                    summary="Small monthly payments add up.",
                    lesson=D.Lesson(
                        concept_id="subscriptions",
                        title="The quiet spend",
                        chart=D.Chart(
                            kind="bar",
                            title="Your subscriptions per month",
                            x_label="Month",
                            y_label="£",
                            points=[D.ChartPoint(x=1, y=41), D.ChartPoint(x=2, y=44), D.ChartPoint(x=3, y=47)],
                        ),
                        sentences=[
                            "Each one looks small, but together they are a bill.",
                            "Prices rise quietly, so check them once a year.",
                        ],
                        quiz=D.Quiz(
                            question="You pay £13 a month for something you never use. What does it cost a year?",
                            options=["£13", "£156", "£52"],
                            answer_index=1,
                        ),
                        personal="You spend £47 a month on 6 subscriptions.",
                    ),
                ),
            ]
        ),
        "Challenges": A.ChallengesResponse(
            challenges=[
                D.Challenge(
                    id="home-by-30",
                    title="Own a home by 30",
                    emoji="🏡",
                    description="Buy any home before you turn 30.",
                    character_id="nurse-leeds",
                    start_year=2006,
                    goal={"type": "own_home_by_age", "age": 30},
                )
            ]
        ),
        "DecisionRequest": A.DecisionRequest(profile=profile),
        "Decision": D.Decision(
            question="Your mortgage deal ends in 3 months. Fix for 2 or 5 years?",
            headline="Fix for 5 years.",
            action="fix_5y",
            reasons=[
                "Your payment stays at £1,050 a month until 2031.",
                "Rates in similar past periods rose more often than they fell.",
            ],
            evidence=D.Evidence(
                twins_count=40,
                periods=["1989-1991", "2006-2008", "2022-2024"],
                success_rate=0.7,
                sentence="7 in 10 twins in similar past periods did better.",
            ),
            alternatives=[
                D.Alternative(action="fix_2y", score=0.41, success_rate=0.3),
                D.Alternative(action="tracker", score=0.22, success_rate=0.2),
            ],
            sources=[SRC_BOE, D.SourceRef(source="boe", series_id="IUMBV42", status="live"), SRC_HPI],
            disclaimer="Education, not financial advice. Check with a regulated adviser.",
            generated_at=NOW,
        ),
        "Evaluation": D.Evaluation(
            method="Leave-one-period-out backtest, k-NN on standardised macro state",
            n=24,
            hit_rate=0.67,
            baseline_hit_rate=0.5,
            baseline="always fix 2 years",
            periods=[D.BacktestPeriod(start=2006, end=2011, recommended="fix_5y", realised_best="fix_5y", hit=True)],
            generated_at=NOW,
        ),
        "CreateRoom": A.CreateRoomRequest(mode="duel", host_name="Ash", preset_id="nurse-leeds", start_year=2021),
        "Room": room,
        "BankAuthLink": A.BankAuthLink(
            url="https://auth.monzo.com/?client_id=oauth2client_demo&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fv1%2Fbank%2Fcallback&response_type=code&state=abc",
            state="abc",
            provider="monzo",
            status="live",
        ),
        "BankSummary": A.BankSummary(status="live", provider="monzo", profile=profile, accounts=2),
        **connection_examples(),
        "PurchaseVerify": A.PurchaseVerifyRequest(product_id="lifeline.rewindpass", demo=True),
        "PurchaseVerifyResponse": A.PurchaseVerifyResponse(
            product_id="lifeline.rewindpass", entitlement="rewind_pass", active=True, demo=True, label="Demo payment"
        ),
        "AppleSignIn": A.AppleSignInRequest(identity_token="eyJraWQiOiJXNldjT0tCIiwiYWxnIjoiUlMyNTYifQ.demo"),  # noqa: S106 (fake example token)
        "DemoSignIn": A.DemoSignInRequest(device_id="3F2A9C1E-7B4D-4E8A"),
        "Token": A.Token(access_token="eyJhbGciOiJIUzI1NiJ9.demo.sig", token_type="bearer", expires_in=86400),  # noqa: S106 (fake example token)
        **finance_examples(),
        **friends_examples(),
        **next_move_examples(),
    }


def next_move_examples() -> dict[str, Any]:
    meta = F.FinanceMeta(data_status="mock", source="fixtures", as_of="2026-10-17", label="Sample data")
    boe5 = D.SourceRef(source="boe", series_id="IUMBV42", status="live")
    boe2 = D.SourceRef(source="boe", series_id="IUMBV34", status="live")
    bank = D.SourceRef(source="boe", series_id="IUMBEDR", status="live")
    period = N.TestPeriod(start=2021, end=2023, label="2021-2023 rate shock")
    fix = N.Move(
        id="mv_fix_mortgage",
        kind="fix_mortgage",
        action="Fix for 5 years",
        headline="Your deal ends in 165 days",
        impact_per_year=1240.0,
        worst_case_per_year=-310.0,
        confidence=0.7,
        confidence_label="7 in 10 twins in similar past periods did better",
        evidence=[
            N.EvidencePoint(
                text="5-year fixes are 4.21% today, 2-year fixes 4.38%.",
                facts={"fix_5y_pct": 4.21, "fix_2y_pct": 4.38},
                source=boe5,
            ),
            N.EvidencePoint(
                text="In 2021-2023, Bank Rate rose from 0.1% to 5.25%.",
                facts={"bank_rate_start": 0.1, "bank_rate_end": 5.25},
                source=bank,
            ),
            N.EvidencePoint(
                text="Your payment would be £1,050 a month on a £180,000 balance.",
                facts={"monthly_payment": 1050, "balance": 180000},
            ),
        ],
        sources=[boe5, boe2, bank],
        options=[
            N.MoveOption(id="fix_5y", label="Fix for 5 years", is_recommended=True),
            N.MoveOption(id="fix_2y", label="Fix for 2 years"),
            N.MoveOption(id="tracker", label="Tracker"),
        ],
        deadline="2027-03-31",
        days_left=165,
        testable=True,
        test_period=period,
        concept_id="fixed-vs-variable",
    )
    subs = N.Move(
        id="mv_cancel_subs",
        kind="cancel_subscription",
        action="Cancel 2 unused subscriptions",
        headline="You pay £22 a month for 2 services you have not used since July",
        impact_per_year=264.0,
        worst_case_per_year=264.0,
        confidence=0.9,
        confidence_label="Based on your own payments",
        evidence=[
            N.EvidencePoint(text="Netflix rose from £10.99 to £12.99 in June.", facts={"from": 10.99, "to": 12.99}),
            N.EvidencePoint(text="No activity with these merchants for 3 months.", facts={"months": 3}),
            N.EvidencePoint(text="You spend £47 a month on 6 subscriptions.", facts={"monthly": 47, "count": 6}),
        ],
        sources=[],
        options=[
            N.MoveOption(id="cancel", label="Cancel both", is_recommended=True),
            N.MoveOption(id="keep", label="Keep them"),
        ],
        testable=False,
        concept_id="subscriptions",
    )
    me = D.CharacterSpec(
        name="You",
        emoji="🙂",
        occupation="analyst",
        region="yorkshire-and-the-humber",
        town="Leeds",
        birth_year=1992,
        annual_income=38000,
        savings=6200,
        housing="mortgage",
        property_value=240000,
        mortgage_balance=180000,
    )
    return {
        "NextMove": N.NextMoveResponse(
            meta=meta,
            top=fix,
            runners_up=[subs],
            backtest=N.NextMoveBacktest(
                method="Walk-forward over past deal-end dates, 1995-2023",
                n=58,
                hit_rate=0.69,
                baseline="Always fix for 2 years",
                baseline_hit_rate=0.41,
            ),
            generated_at=NOW,
        ),
        "TestMove": N.TestMoveRequest(move_id="mv_fix_mortgage"),
        "TestMoveResult": N.TestMoveResult(
            move_id="mv_fix_mortgage",
            period=period,
            character=me,
            outcomes=[
                N.OptionOutcome(
                    option_id="fix_5y",
                    label="Fix for 5 years",
                    is_recommended=True,
                    life_id="lf_t5y001",
                    net_worth_path=[
                        F.Point(date="2021-12-31", value=66000),
                        F.Point(date="2022-12-31", value=71200),
                        F.Point(date="2023-12-31", value=77900),
                    ],
                    end_net_worth=77900,
                    total_cost=37800,
                    missed_payments=0,
                    worst_year=2022,
                    worst_year_change=5200,
                    index=104.2,
                ),
                N.OptionOutcome(
                    option_id="fix_2y",
                    label="Fix for 2 years",
                    is_recommended=False,
                    life_id="lf_t2y001",
                    net_worth_path=[
                        F.Point(date="2021-12-31", value=66000),
                        F.Point(date="2022-12-31", value=70100),
                        F.Point(date="2023-12-31", value=73720),
                    ],
                    end_net_worth=73720,
                    total_cost=41980,
                    missed_payments=0,
                    worst_year=2023,
                    worst_year_change=3620,
                    index=100.0,
                ),
            ],
            summary="Fixing for 5 years left you £4,180 better off by 2023.",
            evidence_sentence="7 in 10 twins in similar past periods did better.",
            sources=[boe5, boe2, bank],
        ),
        "AddPlanItem": N.AddPlanItemRequest(move_id="mv_fix_mortgage"),
        "PlanItem": N.PlanItem(
            id="pl_1",
            move_id="mv_fix_mortgage",
            kind="fix_mortgage",
            action="Fix for 5 years",
            impact_per_year=1240.0,
            added_at=NOW,
        ),
        "Plan": N.PlanResponse(
            items=[
                N.PlanItem(
                    id="pl_1",
                    move_id="mv_fix_mortgage",
                    kind="fix_mortgage",
                    action="Fix for 5 years",
                    impact_per_year=1240.0,
                    added_at=NOW,
                )
            ],
            total_impact_per_year=1240.0,
        ),
    }


def connection_examples() -> dict[str, Any]:
    """Connected accounts, investments, habits and the ISA replay. No example holds a secret."""
    meta = F.FinanceMeta(data_status="live", source="monzo+trading212", as_of="2026-10-17")
    monzo = ACC.ProviderConnection(
        provider="monzo",
        connected=True,
        data_status="live",
        hint="…a1b2",
        oauth_available=True,
        history=ACC.HistoryStatus(synced=True, oldest="2024-10-18", count=1342),
    )
    t212 = ACC.ProviderConnection(provider="trading212", connected=False, data_status="mock", oauth_available=False)
    holdings = [
        ACC.Holding(instrument_id="VUSAl_EQ", name="Vanguard S&P 500", quantity=10, value=900.0, asset_class="equity",
                    region="US"),
        ACC.Holding(instrument_id="VGOV_EQ", name="Vanguard UK Gilts", quantity=20, value=380.5, asset_class="bond",
                    region="UK"),
    ]
    factor = H.HabitFactor(
        id="savings_rate",
        label="Money you keep",
        explainer="The share of what you earn that you do not spend.",
        raw=0.18,
        score=70,
    )
    result = I.IsaBacktestResult(
        period="gfc_2008",
        label="the 2008 financial crisis",
        months=["2007-09", "2007-10", "2007-11"],
        index=[100.0, 101.2, 99.5],
        metrics=I.IsaBacktestMetrics(cagr=0.042, volatility=0.13, max_drawdown=0.31, months_to_recover=38,
                                     worst_12m=-0.27),
        contributed=3600.0,
        final_value=4310.4,
        money_weighted_return=0.051,
    )
    strategy = I.IsaStrategy(weights={"global_equity": 0.8, "gilts": 0.2})
    return {
        "Connections": ACC.ConnectionsResponse(providers=[monzo, t212]),
        "ProviderConnection": monzo,
        "Trading212Connect": ACC.Trading212ConnectRequest(api_key="your-trading212-key", api_secret="your-secret"),  # noqa: S106
        "MonzoToken": ACC.MonzoTokenRequest(access_token="your-monzo-playground-token"),  # noqa: S106
        "HistoryStatus": ACC.HistoryStatus(synced=False, count=0, last_error="auth"),
        "Investments": F.InvestmentsResponse(
            meta=meta, holdings=holdings, total_value=1280.5, cash=42.0, allocation={"bond": 29.71, "equity": 70.29}
        ),
        "HabitFactors": H.HabitFactors(
            window=H.HabitWindow(months=6, end="2026-09-30"), factors=[factor], overall=70
        ),
        "IsaBacktestQuery": I.IsaBacktestQuery(strategies=[strategy], monthly_contribution=150.0),
        "IsaBacktestResponse": I.IsaBacktestResponse(
            results=[result], monthly_contribution=150.0, contribution_source="request"
        ),
        "IsaScenariosQuery": I.IsaScenariosQuery(strategy=strategy, horizon_months=36),
        "IsaScenarios": I.IsaScenariosResult(
            paths=[I.ScenarioPath(start_month="2009-03", index=[100.0, 101.5, 103.2])],
            fan=I.ScenarioFan(p10=[100.0, 98.0, 97.1], p50=[100.0, 101.5, 103.2], p90=[100.0, 104.0, 107.9]),
            horizon_months=2,
        ),
        "IsaPeriods": I.IsaPeriodsResponse(
            periods=[I.IsaPeriod(id="gfc_2008", label="The 2008 financial crisis", start="2007-10", end="2012-12")],
            assets=list(I.ASSETS),
        ),
    }


def finance_examples() -> dict[str, Any]:
    meta = F.FinanceMeta(data_status="mock", source="fixtures", as_of="2026-10-17", label="Sample data")
    accounts = [
        F.Account(id="acc_cur", name="Everyday", kind="current", provider="Sample Bank", balance=1840.22),
        F.Account(id="acc_sav", name="Rainy day", kind="savings", provider="Sample Bank", balance=6200.0),
        F.Account(id="acc_cc", name="Credit card", kind="credit", provider="Sample Bank", balance=-412.5),
    ]
    netflix = F.Subscription(
        id="sub_netflix",
        merchant="Netflix",
        emoji="📺",
        category="subscriptions",
        amount=12.99,
        cadence="monthly",
        monthly_cost=12.99,
        next_payment="2026-10-28",
        price_rise=F.PriceRise(from_amount=10.99, to_amount=12.99, since="2026-06-28"),
    )
    gym = F.Subscription(
        id="sub_gym",
        merchant="PureGym",
        emoji="🏋️",
        category="health",
        amount=24.99,
        cadence="monthly",
        monthly_cost=24.99,
        next_payment="2026-11-01",
    )
    profile = D.DecisionProfile(
        age=34,
        region="yorkshire-and-the-humber",
        annual_income=38000,
        savings=6200,
        other_debt=412.5,
        housing="rent",
        monthly_rent=850,
    )
    fact = F.PersonalFact(
        id="subs_monthly",
        concept_id="subscriptions",
        text="You spend £47 a month on 6 subscriptions.",
        facts={"monthly_total": 47, "count": 6},
    )
    insights = INS.SpendingInsights(
        meta=meta,
        window_months=3,
        requested_months=6,
        start_month="2026-07",
        end_month="2026-09",
        note="Based on your last 3 months",
        total_income=7500.0,
        total_spend=5100.0,
        monthly=[
            INS.InsightMonth(month="2026-07", income=2500.0, spend=1700.0, net=800.0),
            INS.InsightMonth(month="2026-08", income=2500.0, spend=1750.0, net=750.0),
            INS.InsightMonth(month="2026-09", income=2500.0, spend=1650.0, net=850.0),
        ],
        categories=[
            INS.InsightCategory(
                category="groceries", label="Groceries", emoji="🛒", amount=900.0, share=0.1765, monthly_average=300.0
            )
        ],
        category_months=["2026-07", "2026-08", "2026-09"],
        category_by_month=[
            INS.CategorySeries(category="groceries", label="Groceries", emoji="🛒", values=[290.0, 320.0, 290.0])
        ],
        top_merchants=[INS.InsightMerchant(merchant="Tesco", category="groceries", emoji="🛒", amount=540.0, count=21)],
        subscriptions=INS.InsightSubscriptions(
            monthly_total=37.98,
            annual_total=455.76,
            items=[INS.InsightSubscription(merchant="Netflix", emoji="📺", monthly_cost=12.99, annual_cost=155.88)],
        ),
        unusual=[
            INS.UnusualPayment(
                id="tx_1", date="2026-08-14", merchant="Zara", category="shopping", emoji="🛍️", amount=240.0, typical=35.0
            )
        ],
        patterns=INS.SpendingPatterns(
            weekend_share=0.42,
            weekday_share=0.58,
            average_daily_spend=55.4,
            biggest_weekday="Saturday",
            biggest_day="2026-08-14",
            biggest_day_amount=310.0,
            by_weekday=[INS.WeekdaySpend(weekday="Monday", amount=420.0)],
        ),
        insights=["Groceries is your biggest spend: £900, 18% of the £5,100 you spent."],
    )
    return {
        "SpendingInsights": insights,
        "FinanceOverview": F.FinanceOverview(
            meta=meta,
            balance=8040.22,
            net_worth=7627.72,
            accounts=accounts,
            balance_history=[
                F.Point(date="2026-08-31", value=7420.1),
                F.Point(date="2026-09-30", value=7790.55),
                F.Point(date="2026-10-17", value=8040.22),
            ],
            net_worth_history=[
                F.Point(date="2026-08-31", value=6980.0),
                F.Point(date="2026-09-30", value=7350.4),
                F.Point(date="2026-10-17", value=7627.72),
            ],
        ),
        "Spending": F.SpendingResponse(
            meta=meta,
            month="2026-10",
            total=1236.4,
            categories=[
                F.CategorySpend(
                    category="housing",
                    label="Rent and home",
                    emoji="🏠",
                    amount=850,
                    share=0.687,
                    transactions=1,
                    change_pct=0.0,
                ),
                F.CategorySpend(
                    category="groceries",
                    label="Groceries",
                    emoji="🛒",
                    amount=214.3,
                    share=0.173,
                    transactions=9,
                    change_pct=6.2,
                ),
                F.CategorySpend(
                    category="eating_out",
                    label="Eating out",
                    emoji="🍜",
                    amount=172.1,
                    share=0.139,
                    transactions=7,
                    change_pct=-12.5,
                ),
            ],
        ),
        "Subscriptions": F.SubscriptionsResponse(meta=meta, monthly_total=37.98, count=2, items=[netflix, gym]),
        "Bills": F.BillsResponse(
            meta=meta,
            total_next_30_days=887.98,
            items=[
                F.Bill(
                    id="bill_rent",
                    name="Rent",
                    emoji="🏠",
                    kind="rent",
                    amount=850,
                    due_date="2026-11-01",
                    status="due_soon",
                ),
                F.Bill(
                    id="bill_netflix",
                    name="Netflix",
                    emoji="📺",
                    kind="subscription",
                    amount=12.99,
                    due_date="2026-10-28",
                    status="upcoming",
                ),
            ],
        ),
        "Budgets": F.BudgetsResponse(
            meta=meta,
            month="2026-10",
            items=[
                F.Budget(
                    category="eating_out",
                    label="Eating out",
                    emoji="🍜",
                    limit=150,
                    spent=172.1,
                    progress=1.147,
                    status="over",
                ),
                F.Budget(
                    category="groceries",
                    label="Groceries",
                    emoji="🛒",
                    limit=300,
                    spent=214.3,
                    progress=0.714,
                    status="ok",
                ),
            ],
        ),
        "UpdateBudgets": F.UpdateBudgetsRequest(items=[F.BudgetLimit(category="eating_out", limit=180)]),
        "Goals": F.GoalsResponse(
            meta=meta,
            items=[
                F.SavingsGoal(
                    id="goal_house",
                    name="House deposit",
                    emoji="🏡",
                    target=20000,
                    saved=6200,
                    progress=0.31,
                    target_date="2029-06-01",
                    monthly_needed=429.0,
                )
            ],
        ),
        "CreateGoal": F.CreateGoalRequest(name="Holiday", emoji="🏖️", target=1500, target_date="2027-07-01"),
        "Goal": F.SavingsGoal(
            id="goal_holiday",
            name="Holiday",
            emoji="🏖️",
            target=1500,
            saved=0,
            progress=0.0,
            target_date="2027-07-01",
            monthly_needed=166.67,
        ),
        "FinanceProfile": F.FinanceProfile(
            meta=meta,
            profile=profile,
            character=D.CharacterSpec(
                name="You",
                emoji="🙂",
                occupation="analyst",
                region="yorkshire-and-the-humber",
                town="Leeds",
                birth_year=1992,
                annual_income=38000,
                savings=6200,
                debt=412.5,
                housing="rent",
            ),
            personal_facts=[fact],
        ),
        "SpendPrediction": F.SpendPrediction(
            meta=meta,
            date="2026-10-17",
            predicted=38.4,
            low=12.0,
            high=71.5,
            baseline=24.1,
            reasons=[
                F.Reason(feature="weekday", label="It is Friday", effect=9.8),
                F.Reason(feature="payday", label="You were paid 2 days ago", effect=6.2),
                F.Reason(feature="rain", label="Rain is forecast (6 mm)", effect=-1.7),
            ],
            weather=F.Weather(summary="Light rain", temp_max_c=13.5, rain_mm=6.0, status="live"),
            is_bank_holiday=False,
            days_to_payday=27,
            guess=F.GuessState(amount=30.0, made_at="2026-10-17T08:05:00Z"),
            model=F.ModelInfo(
                name="ridge regression on log spend",
                trained_on_days=180,
                mae=11.3,
                baseline_mae=14.9,
                interval_coverage=0.81,
            ),
        ),
        "Guess": F.GuessRequest(date="2026-10-17", amount=30.0),
        "Guesses": F.GuessesResponse(
            meta=meta,
            points_total=412,
            streak=3,
            best_streak=5,
            items=[F.GuessDay(date="2026-10-16", guess=25.0, predicted=27.9, actual=24.1, points=96, beat_model=True)],
        ),
        "PredictionEvaluation": F.PredictionEvaluation(
            meta=meta,
            method="Walk-forward: train on days before each test day, predict the next day",
            n_days=90,
            mae=11.3,
            baseline_mae=14.9,
            baseline="Average spend for that weekday",
            interval_coverage=0.81,
            days=[F.BacktestDay(date="2026-10-16", predicted=27.9, low=9.0, high=55.2, actual=24.1, baseline=22.0)],
        ),
        "Lives": F.LivesResponse(
            lives=[
                F.LifeListItem(
                    id="lf_8f3a2c",
                    name="Amira",
                    emoji="👩🏽‍⚕️",
                    mode="preset",
                    year=2008,
                    age=26,
                    alive=True,
                    index=101.4,
                    net_worth=-11000,
                    ribbons=0,
                )
            ]
        ),
    }


ERR_EXAMPLES = {
    "NotFound": {"error": {"code": "not_found", "message": "Life lf_x not found.", "source": "api"}},
    "Validation": {"error": {"code": "validation_error", "message": "start_year: must be >= 1990", "source": "api"}},
    "Conflict": {
        "error": {"code": "pending_events", "message": "Answer the open events before you age.", "source": "sim"}
    },
    "RateLimited": {
        "error": {"code": "rate_limited", "message": "Too many requests. Try again in 30 seconds.", "source": "api"}
    },
    "PayloadTooLarge": {
        "error": {"code": "payload_too_large", "message": "Request body is over 64 KB.", "source": "api"}
    },
    "NotImplemented": {"error": {"code": "not_implemented", "message": "Not built yet.", "source": "api"}},
    "StoreUnavailable": {
        "error": {"code": "store_unavailable", "message": "Saving is down. Try again in a minute.", "source": "api"}
    },
    "Unauthorized": {"error": {"code": "unauthorized", "message": "Missing or invalid token.", "source": "api"}},
    "BadGateway": {
        "error": {"code": "unavailable", "message": "Trading212 is not answering. Try again soon.", "source": "trading212"}
    },
    "GatewayTimeout": {
        "error": {"code": "timeout", "message": "Monzo took too long to answer.", "source": "monzo"}
    },
    "PaymentRequired": {
        "error": {
            "code": "payment_required",
            "message": "Free rewind used. Rewind Pass needed (Demo payment).",
            "source": "sim",
        }
    },
}


def friends_examples() -> dict[str, Any]:
    """Friends leaderboard. Scores and a rebased index only: no example holds a money amount."""
    me = FR.FriendCard(
        friend_id="fr_1a2b3c4d5e6f7a8b",
        display_name="You",
        overall_score=72,
        factor_scores={"savings_rate": 80, "runway_months": 65},
        growth_index=412.3,
        mix={"bond": 20.0, "equity": 80.0},
        data_status="mock",
        updated_at="2026-10-17T00:00:00Z",
    )
    pal = FR.FriendCard(
        friend_id="fr_9f8e7d6c5b4a3921",
        display_name="Sam",
        overall_score=64,
        factor_scores={"savings_rate": 55, "runway_months": 70, "isa_concentration": 60},
        growth_index=388.0,
        data_status="live",
        updated_at="2026-10-17T00:00:00Z",
    )
    return {
        "Leaderboard": FR.Leaderboard(
            entries=[
                FR.LeaderboardEntry(card=me, rank=1, is_me=True, score_vs_me=100.0),
                FR.LeaderboardEntry(card=pal, rank=2, is_me=False, score_vs_me=88.9),
            ],
            my_invite_code="K7M2QX9P",
        ),
        "MyFriendCard": me,
        "InviteCode": FR.InviteCode(code="K7M2QX9P"),
        "JoinFriend": FR.JoinFriendRequest(code="K7M2QX9P"),
        "ShareSettings": FR.ShareSettings(display_name="Sam", share_mix=True),
    }


def ref(name: str) -> dict[str, str]:
    return {"$ref": f"#/components/schemas/{name}"}


def body(schema: str, example: str) -> dict[str, Any]:
    return {
        "required": True,
        "content": {
            "application/json": {
                "schema": ref(schema),
                "examples": {example: {"$ref": f"#/components/examples/{example}"}},
            }
        },
    }


def ok(schema: str, example: str, desc: str = "OK", code: str = "200") -> dict[str, Any]:
    return {
        code: {
            "description": desc,
            "content": {
                "application/json": {
                    "schema": ref(schema),
                    "examples": {example: {"$ref": f"#/components/examples/{example}"}},
                }
            },
        }
    }


def errs(*codes: str) -> dict[str, Any]:
    names = {
        "400": "BadRequest",
        "401": "Unauthorized",
        "402": "PaymentRequired",
        "404": "NotFound",
        "409": "Conflict",
        "413": "PayloadTooLarge",
        "422": "ValidationError",
        "429": "RateLimited",
        "501": "NotImplemented",
        "502": "BadGateway",
        "503": "StoreUnavailable",
        "504": "GatewayTimeout",
    }
    return {c: {"$ref": f"#/components/responses/{names[c]}"} for c in codes}


# True while some Tier 2 endpoints may still answer 501 not_implemented. Set False when Tier 2 is built.
STUBS_DECLARED = True
TIER2_OPS = {
    "listChallenges",
    "createRoom",
    "getRoom",
    "getBankAuthLink",
    "bankCallback",
    "getBankSummary",
    "verifyPurchase",
    "signInWithApple",
}

LIFE_ID = {"name": "id", "in": "path", "required": True, "schema": {"type": "string", "pattern": "^lf_[a-z0-9]{6,32}$"}}
STD = ("401", "422", "429", "503")


def op(op_id: str, summary: str, tag: str, responses: dict[str, Any], **extra: Any) -> dict[str, Any]:
    o = {"operationId": op_id, "summary": summary, "tags": [tag], "responses": responses}
    o.update(extra)
    return o


def paths() -> dict[str, Any]:
    return {
        "/v1/health": {
            "get": op("getHealth", "Liveness and dependency checks", "meta", ok("Health", "Health"), security=[])
        },
        "/v1/sources": {
            "get": op(
                "listSources",
                "Status of every data source (live, cached or mock)",
                "meta",
                {**ok("SourcesResponse", "Sources"), **errs("429")},
                security=[],
            )
        },
        "/v1/auth/apple": {
            "post": op(
                "signInWithApple",
                "Exchange a Sign in with Apple identity token for a JWT",
                "auth",
                {**ok("Token", "Token"), **errs("401", "422", "429")},
                requestBody=body("AppleSignInRequest", "AppleSignIn"),
                security=[],
            )
        },
        "/v1/auth/demo": {
            "post": op(
                "signInDemo",
                "Anonymous device sign-in for demos and simulator",
                "auth",
                {**ok("Token", "Token"), **errs("422", "429")},
                requestBody=body("DemoSignInRequest", "DemoSignIn"),
                security=[],
            )
        },
        "/v1/characters": {
            "get": op(
                "listCharacters",
                "Preset characters and one random person from the synthetic population",
                "lives",
                {**ok("CharactersResponse", "Characters"), **errs("422", "429")},
                parameters=[
                    {
                        "name": "seed",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer", "minimum": 0, "maximum": 2147483647},
                    }
                ],
                security=[{}, {"bearer": []}],
            )
        },
        "/v1/lives": {
            "post": op(
                "createLife",
                "Start a life",
                "lives",
                {**ok("Life", "Life", "Created", "201"), **errs("400", "404", *STD)},
                requestBody={
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": ref("CreateLifeRequest"),
                            "examples": {
                                "CreateLife": {"$ref": "#/components/examples/CreateLife"},
                                "CreateLifeSelf": {"$ref": "#/components/examples/CreateLifeSelf"},
                            },
                        }
                    },
                },
            )
        },
        "/v1/lives/{id}": {
            "get": op(
                "getLife", "Get a life", "lives", {**ok("Life", "Life"), **errs("404", *STD)}, parameters=[LIFE_ID]
            )
        },
        "/v1/lives/{id}/age": {
            "post": op(
                "ageLife",
                "Advance one year. Returns new events. 409 if events are open.",
                "lives",
                {**ok("AgeResult", "AgeResult"), **errs("404", "409", *STD)},
                parameters=[LIFE_ID],
            )
        },
        "/v1/lives/{id}/choices": {
            "post": op(
                "chooseLife",
                "Answer an open event",
                "lives",
                {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "schema": ref("ChoiceResult"),
                                "examples": {
                                    "ChoiceResult": {"$ref": "#/components/examples/ChoiceResult"},
                                    "ChoiceResultDefault": {"$ref": "#/components/examples/ChoiceResultDefault"},
                                },
                            }
                        },
                    },
                    **errs("404", "409", *STD),
                },
                parameters=[LIFE_ID],
                requestBody={
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": ref("ChoiceRequest"),
                            "examples": {
                                "Choice": {"$ref": "#/components/examples/Choice"},
                                "ChoiceDefault": {"$ref": "#/components/examples/ChoiceDefault"},
                            },
                        }
                    },
                },
            )
        },
        "/v1/lives/{id}/actions": {
            "post": op(
                "actLife",
                "Do a tab action (Job, Assets, Relationships, Activities, Money)",
                "lives",
                {**ok("ActionResult", "ActionResult"), **errs("402", "404", "409", *STD)},
                parameters=[LIFE_ID],
                requestBody=body("ActionRequest", "Action"),
            )
        },
        "/v1/lives/{id}/rewind": {
            "post": op(
                "rewindLife",
                "Go back to a past decision and take the other path",
                "lives",
                {**ok("RewindResult", "RewindResult"), **errs("402", "404", "409", *STD)},
                parameters=[LIFE_ID],
                requestBody=body("RewindRequest", "Rewind"),
            )
        },
        "/v1/lives/{id}/summary": {
            "get": op(
                "getLifeSummary",
                "Life summary (works for living and dead lives)",
                "lives",
                {**ok("LifeSummary", "Summary"), **errs("404", *STD)},
                parameters=[LIFE_ID],
            )
        },
        "/v1/concepts": {
            "get": op(
                "listConcepts",
                "All lesson concepts (never paywalled)",
                "learn",
                {**ok("ConceptsResponse", "Concepts"), **errs("429")},
            )
        },
        "/v1/challenges": {
            "get": op(
                "listChallenges", "Challenges", "learn", {**ok("ChallengesResponse", "Challenges"), **errs("429")}
            )
        },
        "/v1/decisions": {
            "post": op(
                "createDecision",
                "One clear recommended action for a real situation, with evidence",
                "decision",
                {**ok("Decision", "Decision"), **errs(*STD)},
                requestBody=body("DecisionRequest", "DecisionRequest"),
            )
        },
        "/v1/evaluation": {
            "get": op(
                "getEvaluation",
                "Backtest of the decision engine",
                "decision",
                {**ok("Evaluation", "Evaluation"), **errs("429")},
            )
        },
        "/v1/rooms": {
            "post": op(
                "createRoom",
                "Create a Same Life room",
                "rooms",
                {**ok("Room", "Room", "Created", "201"), **errs("404", *STD)},
                requestBody=body("CreateRoomRequest", "CreateRoom"),
            )
        },
        "/v1/rooms/{code}": {
            "get": op(
                "getRoom",
                "Get a room. The same path upgrades to a WebSocket (see x-websocket).",
                "rooms",
                {**ok("Room", "Room"), **errs("404", *STD)},
                parameters=[
                    {
                        "name": "code",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "pattern": "^[A-Z0-9]{6}$"},
                    }
                ],
                **{
                    "x-websocket": {
                        "url": "/v1/rooms/{code}?token={jwt}",
                        "client_messages": ref("WsClientMessage"),
                        "server_messages": ref("WsServerMessage"),
                        "flow": "Client sends join. Server broadcasts roster. Clients send progress after each AGE. "
                        "Server broadcasts rival per update. Host may send start. finish ends that player's run.",
                    }
                },
            )
        },
        "/v1/bank/auth-link": {
            "get": op(
                "getBankAuthLink",
                "Monzo sign-in link. status live when Monzo OAuth is configured, otherwise a labelled mock link",
                "bank",
                {**ok("BankAuthLink", "BankAuthLink"), **errs(*STD)},
            )
        },
        "/v1/bank/callback": {
            "get": op(
                "bankCallback",
                "Monzo redirect target (no bearer token). Exchanges the code, stores tokens and imports history.",
                "bank",
                {
                    "302": {
                        "description": "Redirect to lifeline://connected?status=ok&provider=monzo&session=<state>, or lifeline://connected?status=error&code=<code>. The body is a small HTML page for browsers that do not follow the custom scheme.",
                        "headers": {"Location": {"schema": {"type": "string"}}},
                    },
                    **errs("400", "422", "429"),
                },
                parameters=[
                    {"name": "code", "in": "query", "required": False, "schema": {"type": "string", "maxLength": 2048}},
                    {"name": "state", "in": "query", "required": True, "schema": {"type": "string", "maxLength": 256}},
                    {"name": "error", "in": "query", "required": False, "schema": {"type": "string", "maxLength": 256}},
                ],
                security=[],
            )
        },
        "/v1/bank/summary": {
            "get": op(
                "getBankSummary",
                "Profile built from connected bank data (prefills Play yourself)",
                "bank",
                {**ok("BankSummary", "BankSummary"), **errs("404", *STD)},
                parameters=[
                    {"name": "session", "in": "query", "required": True, "schema": {"type": "string", "maxLength": 128}}
                ],
            )
        },
        **finance_paths(),
        **investing_paths(),
        **friends_paths(),
        **connection_paths(),
        **next_move_paths(),
        "/v1/purchases/verify": {
            "post": op(
                "verifyPurchase",
                "Verify a StoreKit purchase. DEMO ONLY.",
                "store",
                {**ok("PurchaseVerifyResponse", "PurchaseVerifyResponse"), **errs("400", *STD)},
                requestBody=body("PurchaseVerifyRequest", "PurchaseVerify"),
            )
        },
    }


MONTH = {
    "name": "month",
    "in": "query",
    "required": False,
    "schema": {"type": "string", "pattern": "^\\d{4}-\\d{2}$"},
    "description": "YYYY-MM; default this month",
}
FIN = ("401", "422", "429")


FIN_LIVE = ("401", "422", "429", "503")
PROVIDER_ERRS = ("400", "409", "429", "502", "503", "504")


def investing_paths() -> dict[str, Any]:
    """Investments, money habits and the ISA replay. Return series are synthetic and labelled."""
    return {
        "/v1/finance/investments": {
            "get": op(
                "getInvestments",
                "Connected investment positions, value, cash and allocation",
                "finance",
                {**ok("InvestmentsResponse", "Investments"), **errs(*FIN)},
            )
        },
        "/v1/finance/habits": {
            "get": op(
                "getHabits",
                "Money habit factors (ratios and 0-100 scores, no amounts)",
                "investing",
                {**ok("HabitFactors", "HabitFactors"), **errs(*FIN)},
            )
        },
        "/v1/finance/isa/periods": {
            "get": op(
                "getIsaPeriods",
                "Named past periods and assets for the ISA replay",
                "investing",
                {**ok("IsaPeriodsResponse", "IsaPeriods"), **errs(*FIN)},
            )
        },
        "/v1/finance/isa/backtest": {
            "post": op(
                "postIsaBacktest",
                "Replay up to 4 ISA strategies through a past period. Leave monthly_contribution out to use your own habit",
                "investing",
                {**ok("IsaBacktestResponse", "IsaBacktestResponse"), **errs(*FIN)},
                requestBody=body("IsaBacktestQuery", "IsaBacktestQuery"),
            )
        },
        "/v1/finance/isa/scenarios": {
            "post": op(
                "postIsaScenarios",
                "Modelled paths from similar past periods. Not a forecast.",
                "investing",
                {**ok("IsaScenariosResult", "IsaScenarios"), **errs(*FIN)},
                requestBody=body("IsaScenariosQuery", "IsaScenariosQuery"),
            )
        },
    }


FRIEND_ID = {"name": "friend_id", "in": "path", "required": True, "schema": {"type": "string", "maxLength": 64}}


def friends_paths() -> dict[str, Any]:
    """Friends leaderboard. Friends see scores, a rebased growth index and (opt-in) the mix as percentages."""
    return {
        "/v1/friends": {
            "get": op(
                "getLeaderboard",
                "You and your friends ranked by habit score. No money amounts",
                "friends",
                {**ok("Leaderboard", "Leaderboard"), **errs(*FIN)},
            )
        },
        "/v1/friends/invite": {
            "post": op(
                "createFriendInvite",
                "Your invite code (lifeline://join/CODE). Stable until rotate=true",
                "friends",
                {**ok("InviteCode", "InviteCode"), **errs(*FIN)},
                parameters=[
                    {"name": "rotate", "in": "query", "required": False, "schema": {"type": "boolean", "default": False}}
                ],
            )
        },
        "/v1/friends/join": {
            "post": op(
                "joinFriend",
                "Add a friend by invite code. Both of you see each other. Repeating it is safe",
                "friends",
                {**ok("Leaderboard", "Leaderboard"), **errs("400", "404", *FIN)},
                requestBody=body("JoinFriendRequest", "JoinFriend"),
            )
        },
        "/v1/friends/me": {
            "get": op(
                "getMyFriendCard",
                "Exactly what your friends can see about you",
                "friends",
                {**ok("FriendCard", "MyFriendCard"), **errs(*FIN)},
            ),
            "put": op(
                "updateMyFriendCard",
                "Set the name friends see and whether to share your mix as percentages",
                "friends",
                {**ok("FriendCard", "MyFriendCard"), **errs(*FIN)},
                requestBody=body("ShareSettings", "ShareSettings"),
            ),
        },
        "/v1/friends/{friend_id}": {
            "delete": op(
                "removeFriend",
                "Remove a friend for both of you",
                "friends",
                {**ok("Leaderboard", "Leaderboard"), **errs(*FIN)},
                parameters=[FRIEND_ID],
            )
        },
    }


def connection_paths() -> dict[str, Any]:
    """Connected accounts (Monzo, Trading212). Provider failures map to 400/409/429/502/503/504."""
    return {
        "/v1/connections": {
            "get": op(
                "listConnections",
                "Which providers are connected (masked hints only, never a secret)",
                "connections",
                {**ok("ConnectionsResponse", "Connections"), **errs("401", "429")},
            )
        },
        "/v1/connections/trading212": {
            "post": op(
                "connectTrading212",
                "Connect Trading212. The key is checked with Trading212 before it is stored.",
                "connections",
                {**ok("ProviderConnection", "ProviderConnection"), **errs("401", "422", *PROVIDER_ERRS)},
                requestBody=body("Trading212ConnectRequest", "Trading212Connect"),
            )
        },
        "/v1/connections/monzo/token": {
            "post": op(
                "connectMonzoToken",
                "Dev convenience: connect Monzo with a playground access token",
                "connections",
                {**ok("ProviderConnection", "ProviderConnection"), **errs("401", "422", *PROVIDER_ERRS)},
                requestBody=body("MonzoTokenRequest", "MonzoToken"),
            )
        },
        "/v1/connections/monzo/sync": {
            "post": op(
                "syncMonzo",
                "Retry the Monzo history import (after approving access in the Monzo app)",
                "connections",
                {**ok("HistoryStatus", "HistoryStatus"), **errs("401", *PROVIDER_ERRS)},
            )
        },
        "/v1/connections/{provider}": {
            "delete": op(
                "disconnectProvider",
                "Forget a provider's credentials and imported data",
                "connections",
                {**ok("ConnectionsResponse", "Connections"), **errs("401", "422", "429")},
                parameters=[
                    {
                        "name": "provider",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "enum": ["monzo", "trading212"]},
                    }
                ],
            )
        },
    }


def next_move_paths() -> dict[str, Any]:
    """The product's one question (ADR 0018)."""
    return {
        "/v1/next-move": {
            "get": op(
                "getNextMove",
                "What is my next money move? One top move, up to 2 runners-up, with evidence",
                "next-move",
                {**ok("NextMoveResponse", "NextMove"), **errs("401", "429", "503")},
            )
        },
        "/v1/next-move/test": {
            "post": op(
                "testNextMove",
                "Test it: play each option of a move through the most relevant past period",
                "next-move",
                {**ok("TestMoveResult", "TestMoveResult"), **errs("404", "409", *STD)},
                requestBody=body("TestMoveRequest", "TestMove"),
            )
        },
        "/v1/plan": {
            "get": op(
                "getPlan",
                "The user's plan (moves they chose to do)",
                "next-move",
                {**ok("PlanResponse", "Plan"), **errs("401", "429", "503")},
            ),
            "post": op(
                "addPlanItem",
                "Do this: add a move to the plan",
                "next-move",
                {**ok("PlanItem", "PlanItem", "Created", "201"), **errs("404", *STD)},
                requestBody=body("AddPlanItemRequest", "AddPlanItem"),
            ),
        },
    }


def finance_paths() -> dict[str, Any]:
    """Money tab (ADR 0016). Tier 1 on labelled fixtures; TrueLayer sandbox in Tier 2."""
    return {
        "/v1/finance/overview": {
            "get": op(
                "getFinanceOverview",
                "Balance, net worth and their history",
                "finance",
                {**ok("FinanceOverview", "FinanceOverview"), **errs(*FIN)},
            )
        },
        "/v1/finance/spending": {
            "get": op(
                "getFinanceSpending",
                "Spending by category for a month",
                "finance",
                {**ok("SpendingResponse", "Spending"), **errs(*FIN)},
                parameters=[MONTH],
            )
        },
        "/v1/finance/insights": {
            "get": op(
                "getFinanceInsights",
                "Spending insights over the last N complete months (fewer when history is short)",
                "finance",
                {**ok("SpendingInsights", "SpendingInsights"), **errs(*FIN)},
                parameters=[
                    {
                        "name": "months",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer", "minimum": 1, "maximum": 12, "default": 6},
                        "description": "Window length in complete months; fewer are used if that is all there is",
                    }
                ],
            )
        },
        "/v1/finance/subscriptions": {
            "get": op(
                "listSubscriptions",
                "Detected subscriptions with price-rise flags",
                "finance",
                {**ok("SubscriptionsResponse", "Subscriptions"), **errs(*FIN)},
            )
        },
        "/v1/finance/bills": {
            "get": op(
                "listBills",
                "Bills and upcoming payments (next 30 days)",
                "finance",
                {**ok("BillsResponse", "Bills"), **errs(*FIN)},
            )
        },
        "/v1/finance/budgets": {
            "get": op(
                "listBudgets",
                "Budgets per category with progress",
                "finance",
                {**ok("BudgetsResponse", "Budgets"), **errs(*FIN)},
                parameters=[MONTH],
            ),
            "put": op(
                "updateBudgets",
                "Set budget limits per category",
                "finance",
                {**ok("BudgetsResponse", "Budgets"), **errs(*FIN, "503")},
                requestBody=body("UpdateBudgetsRequest", "UpdateBudgets"),
            ),
        },
        "/v1/finance/goals": {
            "get": op("listGoals", "Savings goals", "finance", {**ok("GoalsResponse", "Goals"), **errs(*FIN)}),
            "post": op(
                "createGoal",
                "Create a savings goal",
                "finance",
                {**ok("SavingsGoal", "Goal", "Created", "201"), **errs(*FIN, "503")},
                requestBody=body("CreateGoalRequest", "CreateGoal"),
            ),
        },
        "/v1/finance/prediction": {
            "get": op(
                "getSpendPrediction",
                "Today's spend prediction with a range and top 3 reasons (ADR 0017)",
                "finance",
                {**ok("SpendPrediction", "SpendPrediction"), **errs(*FIN)},
                parameters=[
                    {
                        "name": "date",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                        "description": "YYYY-MM-DD; default today",
                    }
                ],
            )
        },
        "/v1/finance/guesses": {
            "get": op(
                "listGuesses",
                "Guess my spend: history, points and streak",
                "finance",
                {**ok("GuessesResponse", "Guesses"), **errs(*FIN)},
            ),
            "post": op(
                "makeGuess",
                "Guess today's spend before seeing the prediction (one guess per day)",
                "finance",
                {**ok("SpendPrediction", "SpendPrediction", "Created", "201"), **errs(*FIN, "409", "503")},
                requestBody=body("GuessRequest", "Guess"),
            ),
        },
        "/v1/finance/prediction/evaluation": {
            "get": op(
                "getPredictionEvaluation",
                "Walk-forward backtest of the spend model",
                "finance",
                {**ok("PredictionEvaluation", "PredictionEvaluation"), **errs(*FIN)},
            )
        },
        "/v1/finance/profile": {
            "get": op(
                "getFinanceProfile",
                "Bridge: DecisionProfile and 'Play yourself' character from real data, plus personal facts for lessons",
                "finance",
                {**ok("FinanceProfile", "FinanceProfile"), **errs(*FIN)},
            )
        },
    }


def build() -> dict[str, Any]:
    err_resp = {
        "BadRequest": ("Bad request", "Validation"),
        "Unauthorized": ("Missing or invalid bearer token", "Unauthorized"),
        "PaymentRequired": ("Needs a demo purchase", "PaymentRequired"),
        "NotFound": ("Not found", "NotFound"),
        "Conflict": ("State conflict", "Conflict"),
        "PayloadTooLarge": ("Body over 64 KB", "PayloadTooLarge"),
        "NotImplemented": ("Endpoint not built yet in this tier", "NotImplemented"),
        "StoreUnavailable": ("Service unavailable (life store down, or the provider is not configured or offline)",
                             "StoreUnavailable"),
        "BadGateway": ("A provider (Monzo, Trading212) failed or sent bad data", "BadGateway"),
        "GatewayTimeout": ("A provider (Monzo, Trading212) took too long", "GatewayTimeout"),
        "ValidationError": ("Input failed validation", "Validation"),
        "RateLimited": ("Rate limited", "RateLimited"),
    }
    exs = {k: {"value": ex(v)} for k, v in examples().items()}
    exs.update({f"Error{k}": {"value": v} for k, v in ERR_EXAMPLES.items()})
    p = paths()
    p["/v1/lives"]["get"] = op(
        "listLives",
        "The caller's lives (Play tab: lives, ribbons)",
        "lives",
        {**ok("LivesResponse", "Lives"), **errs("401", "429", "503")},
    )
    for item in p.values():
        for method, o in item.items():
            if method in ("post", "put"):
                o["responses"].update(errs("413"))
            if o["operationId"] in TIER2_OPS and STUBS_DECLARED:
                o["responses"].update(errs("501"))
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Lifeline API",
            "version": "0.1.0",
            "description": "Backend for Lifeline, a BitLife-style game about money on real UK data. "
            "One error format everywhere: {error: {code, message, source}}. "
            "Null fields are omitted from responses.",
        },
        "servers": [{"url": "http://localhost:8000"}],
        "security": [{"bearer": []}],
        "tags": [
            {"name": t}
            for t in (
                "meta", "auth", "next-move", "lives", "learn", "decision", "finance", "investing", "friends", "connections",
                "rooms", "bank", "store",
            )
        ],
        "paths": p,
        "components": {
            "securitySchemes": {"bearer": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}},
            "schemas": schemas(),
            "responses": {
                k: {
                    "description": d,
                    "content": {
                        "application/json": {
                            "schema": ref("Error"),
                            "examples": {e: {"$ref": f"#/components/examples/Error{e}"}},
                        }
                    },
                }
                for k, (d, e) in err_resp.items()
            },
            "examples": exs,
        },
    }


if __name__ == "__main__":
    out = ROOT / "openapi.yaml"
    header = "# GENERATED by contracts/build_openapi.py from services/api/lifeline_contracts. Do not hand-edit.\n"
    out.write_text(header + yaml.safe_dump(build(), sort_keys=False, allow_unicode=True, width=120))
    print(f"wrote {out}")
