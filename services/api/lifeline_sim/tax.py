"""Take-home pay. Pure functions of gross income."""

from __future__ import annotations

from lifeline_sim import params as p


def income_tax(gross: float) -> float:
    allowance = p.PERSONAL_ALLOWANCE
    if gross > p.ALLOWANCE_TAPER_START:
        allowance = max(0.0, allowance - (gross - p.ALLOWANCE_TAPER_START) / 2)
    taxable = max(0.0, gross - allowance)
    basic_band = p.BASIC_LIMIT - p.PERSONAL_ALLOWANCE
    higher_band = p.HIGHER_LIMIT - p.BASIC_LIMIT
    tax = min(taxable, basic_band) * p.BASIC_RATE
    tax += min(max(taxable - basic_band, 0.0), higher_band) * p.HIGHER_RATE
    tax += max(taxable - basic_band - higher_band, 0.0) * p.ADDITIONAL_RATE
    return tax


def national_insurance(gross: float) -> float:
    main = max(0.0, min(gross, p.BASIC_LIMIT) - p.PERSONAL_ALLOWANCE) * p.NI_MAIN_RATE
    upper = max(0.0, gross - p.BASIC_LIMIT) * p.NI_UPPER_RATE
    return main + upper


def net_pay(gross: float, employed: bool) -> float:
    """Gross minus income tax, NI (employees only) and the employee pension share."""
    ni = national_insurance(gross) if employed else 0.0
    pension = gross * p.PENSION_EMPLOYEE if employed else 0.0
    return gross - income_tax(gross) - ni - pension
