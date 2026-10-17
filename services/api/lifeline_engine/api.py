"""Public engine API. Implements lifeline_contracts.interfaces.EngineAPI as plain functions."""

from __future__ import annotations

from lifeline_engine.decision import decide
from lifeline_engine.population import random_character
from lifeline_eval.backtest import evaluate

__all__ = ["decide", "evaluate", "random_character"]
