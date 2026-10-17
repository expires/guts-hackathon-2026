"""Shared types and interfaces. BOSS-owned. Workers import from here and never redefine these."""

from lifeline_contracts.brand import PRODUCT_NAME
from lifeline_contracts.macro import MacroKey, MacroTable, MacroValue
from lifeline_contracts.observation import Observation, SourceStatus, Status

__all__ = [
    "PRODUCT_NAME",
    "MacroKey",
    "MacroTable",
    "MacroValue",
    "Observation",
    "SourceStatus",
    "Status",
]
