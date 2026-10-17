"""AI only explains. Figures come from the result dict; the LLM never computes or changes them."""

import json
import logging
import re
from typing import Any, Literal

from pydantic import BaseModel

from playyourself.settings import Settings

log = logging.getLogger(__name__)

Kind = Literal["habit_vector", "backtest", "scenarios", "spending"]
SCENARIO_LABEL = (
    "Modelled scenarios from similar past periods. Not a forecast. Not financial advice."
)

SYSTEM_PROMPT = (
    "Explain only the given JSON in plain UK English, in at most 120 words. Never give advice "
    "or recommendations. Never introduce numbers that are not in the JSON. Say 'modelled "
    "scenario', not 'forecast'."
)


class Explanation(BaseModel):
    text: str
    source: Literal["template", "llm"]
    model: str | None = None


# ---- templates ---------------------------------------------------------------------------
def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".")
    return str(v)


def _scalars(d: Any) -> dict[str, Any]:
    if not isinstance(d, dict):
        return {}
    return {k: v for k, v in d.items() if isinstance(v, int | float) and not isinstance(v, bool)}


def _label(k: str) -> str:
    return k.replace("_", " ")


def _template(kind: Kind, result: dict) -> str:
    if kind == "habit_vector":
        scores = _scalars(result.get("scores")) or _scalars(result)
        if not scores:
            return "No habit scores are available yet."
        parts = ", ".join(f"{_label(k)} {_fmt(v)}" for k, v in scores.items())
        return f"Your habit scores are: {parts}. They describe your past behaviour only."
    if kind == "backtest":
        m = _scalars(result)
        if not m:
            return "No backtest results are available yet."
        parts = ", ".join(f"{_label(k)} {_fmt(v)}" for k, v in m.items())
        return f"Over the tested past period, the strategy had: {parts}. Past results only."
    if kind == "spending":
        insights = [i for i in result.get("insights") or [] if isinstance(i, str)]
        cats = result.get("top_categories")
        top = []
        if isinstance(cats, list):
            for c in cats[:3]:
                if isinstance(c, dict) and c.get("category") and "share_pct" in c:
                    top.append(f"{_label(str(c['category']))} {_fmt(c['share_pct'])}%")
        if not insights and not top:
            return "No spending analysis is available yet."
        parts = [i.rstrip(".") + "." for i in insights[:5]]
        if top:
            parts.append("Largest categories by share of spending: " + ", ".join(top) + ".")
        return " ".join(parts) + " Past spending only."
    scen = result.get("scenarios")
    lines: list[str] = []
    if isinstance(scen, list):
        for s in scen:
            sc = _scalars(s)
            name = s.get("name") or s.get("label") if isinstance(s, dict) else None
            if sc:
                body = ", ".join(f"{_label(k)} {_fmt(v)}" for k, v in sc.items())
                lines.append(f"{name}: {body}" if name else body)
    else:
        sc = _scalars(result)
        if sc:
            lines.append(", ".join(f"{_label(k)} {_fmt(v)}" for k, v in sc.items()))
    body = "; ".join(lines) if lines else "No scenarios are available yet."
    return f"{body}. {SCENARIO_LABEL}"


# ---- guardrail ---------------------------------------------------------------------------
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?|\.\d+")


def _numbers(text: str) -> list[float]:
    out = []
    for m in _NUM.findall(text):
        out.append(float(m.replace(",", "").lstrip(",") or 0))
    return out


def _collect(obj: Any, acc: list[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, int | float):
        acc.append(abs(float(obj)))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _collect(v, acc)
            _acc_str(k, acc)
    elif isinstance(obj, list | tuple):
        for v in obj:
            _collect(v, acc)
    elif isinstance(obj, str):
        _acc_str(obj, acc)


def _acc_str(s: Any, acc: list[float]) -> None:
    if isinstance(s, str):
        acc.extend(_numbers(s))


def numbers_grounded(text: str, result: dict) -> bool:
    allowed: list[float] = []
    _collect(result, allowed)
    for n in _numbers(text):
        ok = False
        for a in allowed:
            for cand in (a, a * 100):
                if any(abs(round(cand, dp) - n) < 1e-9 for dp in (0, 1, 2)) or abs(cand - n) < 1e-9:
                    ok = True
                    break
            if ok:
                break
        if not ok:
            return False
    return True


# ---- public ------------------------------------------------------------------------------
def explain(
    kind: Kind, result: dict, *, client: Any = None, settings: Settings | None = None
) -> Explanation:
    fallback = Explanation(text=_template(kind, result), source="template", model=None)
    if client is None:
        if settings is None or not settings.anthropic_api_key:
            return fallback
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        except Exception:
            log.warning("explain: could not create LLM client; using template")
            return fallback
    model = settings.explainer_model if settings else Settings().explainer_model
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(result, default=str)}],
        )
        text = next(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    except Exception as exc:
        log.warning("explain: LLM call failed (%s); using template", type(exc).__name__)
        return fallback
    if not text or not numbers_grounded(text, result):
        log.warning("explain: LLM text failed grounding check; using template")
        return fallback
    if kind == "scenarios" and SCENARIO_LABEL not in text:
        text = f"{text} {SCENARIO_LABEL}"
    return Explanation(text=text, source="llm", model=model)
