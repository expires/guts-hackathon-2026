"""Public engine API. Implements lifeline_contracts.interfaces.EngineAPI as plain functions,
plus the Next Move (ADR 0018) entry points."""

from __future__ import annotations

from lifeline_engine.decision import decide
from lifeline_engine.next_move import next_move, option_policy
from lifeline_engine.population import random_character
from lifeline_eval.backtest import evaluate

__all__ = ["decide", "evaluate", "next_move", "option_policy", "random_character"]
