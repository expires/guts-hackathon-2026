"""Official UK rule numbers (ADR 0033). The table lives in lifeline_engine.rules so next_move can use it without
importing the tools package (which imports next_move)."""

from lifeline_engine.rules import (
    BY_ID,
    FACTS,
    OFFICIAL_DOMAINS,
    OFFICIAL_NON_GOVUK,
    TAX_YEAR,
    TOPICS,
    RuleFact,
    Topic,
    Unit,
    get,
    lookup,
)

__all__ = [
    "BY_ID", "FACTS", "OFFICIAL_DOMAINS", "OFFICIAL_NON_GOVUK", "TAX_YEAR", "TOPICS", "RuleFact", "Topic", "Unit",
    "get", "lookup",
]
