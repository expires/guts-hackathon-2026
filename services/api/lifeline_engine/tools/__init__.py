"""Engine tools for Ask Penny (ADR 0031, 0033): cash-flow projection, the official facts table and tool wrappers."""

from __future__ import annotations

from lifeline_engine.tools.cashflow import Cancel, JobLoss, OneOffCost, Projection, RateRise, cash_flow_projection
from lifeline_engine.tools.wrappers import (
    TOOL_DESCRIPTIONS,
    TOOL_INPUTS,
    CashFlowInput,
    FactsTableInput,
    FinanceSummaryInput,
    LifeReplayInput,
    NextMoveInput,
    SpendPredictionInput,
    TestMoveInput,
    ToolResult,
    source_id,
    tool_cash_flow_projection,
    tool_facts_table,
    tool_finance_summary,
    tool_life_replay,
    tool_next_move,
    tool_schemas,
    tool_spend_prediction,
    tool_test_move,
)

__all__ = [
    "TOOL_DESCRIPTIONS",
    "TOOL_INPUTS",
    "Cancel",
    "CashFlowInput",
    "FactsTableInput",
    "FinanceSummaryInput",
    "JobLoss",
    "LifeReplayInput",
    "NextMoveInput",
    "OneOffCost",
    "Projection",
    "RateRise",
    "SpendPredictionInput",
    "TestMoveInput",
    "ToolResult",
    "cash_flow_projection",
    "source_id",
    "tool_cash_flow_projection",
    "tool_facts_table",
    "tool_finance_summary",
    "tool_life_replay",
    "tool_next_move",
    "tool_schemas",
    "tool_spend_prediction",
    "tool_test_move",
]
