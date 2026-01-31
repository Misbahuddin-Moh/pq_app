"""
Mitigation comparison engine (data-center oriented)

Compares baseline harmonic spectrum vs mitigation options via simple attenuation models.

Outputs:
- strict IEEE-519 pass (TDD pass AND no individual violations)
- practical pass (allows minor high-order exceedances)
- severity_score (for ranking in practical mode)
- heating proxy (eddy-current style weighting: sum(h^2 * Ih^2))

Notes:
- This is a screening tool (not full impedance/resonance modeling).
- IEEE-519 limits apply at PCC and depend on Isc/IL (handled in ieee519.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Callable, List
import math

from pq_engine.analysis.ieee519 import evaluate_ieee519_current_limits, IEEE519CurrentReport


# ----------------------------
# Filter attenuation models
# ----------------------------

def attenuation_none(h: int) -> float:
    return 1.0


def attenuation_tuned_5_7(h: int) -> float:
    """
    Tuned passive filter effect (simple):
    - Strong reduction at 5th/7th
    - Some improvement at 11th/13th
    - Mild elsewhere in low-order
    """
    if h == 5:
        return 0.25
    if h == 7:
        return 0.30
    if h in (11, 13):
        return 0.65
    if 2 <= h <= 25:
        return 0.85
    return 0.95


def attenuation_broadband_passive(h: int) -> float:
    """
    Broadband passive / reactor+filter bank style:
    - Moderate reduction across low-order
    """
    if 2 <= h <= 11:
        return 0.55
    if 12 <= h <= 25:
        return 0.70
    if 26 <= h <= 50:
        return 0.85
    return 1.0


def attenuation_active_filter_like(h: int) -> float:
    """
    Active harmonic filter / AFE-like cleanup:
    - Strong low-order reduction, diminishing at higher order
    """
    if 2 <= h <= 11:
        return 0.25
    if 12 <= h <= 25:
        return 0.40
    if 26 <= h <= 50:
        return 0.60
    return 1.0


FILTER_LIBRARY: Dict[str, Callable[[int], float]] = {
    "none": attenuation_none,
    "tuned_5_7": attenuation_tuned_5_7,
    "broadband_passive": attenuation_broadband_passive,
    "active_filter_like": attenuation_active_filter_like,
}


def apply_attenuation(
    harmonic_pct_of_fund: Dict[int, float],
    attenuation_fn: Callable[[int], float],
) -> Dict[int, float]:
    """Apply attenuation factor per harmonic order."""
    return {int(h): float(pct) * float(attenuation_fn(int(h))) for h, pct in harmonic_pct_of_fund.items()}


# ----------------------------
# Engineer metrics
# ----------------------------

def thd_i_from_pct(harmonic_pct_of_fund: Dict[int, float], max_h: int = 50) -> float:
    """THD-I from % of fundamental RMS."""
    s = 0.0
    for h, pct in harmonic_pct_of_fund.items():
        h = int(h)
        if 2 <= h <= max_h:
            s += (pct / 100.0) ** 2
    return math.sqrt(s)  # per-unit


def irms_inflation_factor(thd_pu: float) -> float:
    """Irms / I1 assuming orthogonal harmonics."""
    return math.sqrt(1.0 + thd_pu * thd_pu)


def transformer_heating_proxy(harmonic_pct_of_fund: Dict[int, float], max_h: int = 50) -> float:
    """
    Eddy-current style proxy:
      sum(h^2 * Ih^2), Ih in per-unit of I1.
    """
    s = 0.0
    for h, pct in harmonic_pct_of_fund.items():
        h = int(h)
        if 2 <= h <= max_h:
            ih_pu = pct / 100.0
            s += (h * h) * (ih_pu * ih_pu)
    return float(s)


# ----------------------------
# Scenario comparison
# ----------------------------

@dataclass
class ScenarioResult:
    name: str
    spectrum_pct_of_fund: Dict[int, float]
    thd_i_percent: float
    irms_over_i1: float
    heating_proxy: float
    ieee519: IEEE519CurrentReport


def run_scenario(
    name: str,
    spectrum_pct_of_fund: Dict[int, float],
    il_a: float,
    isc_a: float,
) -> ScenarioResult:
    thd_pu = thd_i_from_pct(spectrum_pct_of_fund)
    thd_pct = thd_pu * 100.0
    infl = irms_inflation_factor(thd_pu)
    heat = transformer_heating_proxy(spectrum_pct_of_fund)

    rpt = evaluate_ieee519_current_limits(
        harmonic_percent_of_fund=spectrum_pct_of_fund,
        il_a=il_a,
        isc_a=isc_a,
        voltage_class="120V-69kV",
    )

    return ScenarioResult(
        name=name,
        spectrum_pct_of_fund=spectrum_pct_of_fund,
        thd_i_percent=thd_pct,
        irms_over_i1=infl,
        heating_proxy=heat,
        ieee519=rpt,
    )


def _split_major_minor_violations(ieee: IEEE519CurrentReport) -> tuple[list, list]:
    """
    Practical categorization:
    - Low-order (<=13) failures are always major
    - High-order tiny exceedances are minor
    """
    minor = []
    major = []
    for v in ieee.worst_violations:
        over = v.ih_percent_of_il - v.limit_percent_of_il
        if v.h <= 13:
            major.append(v)
        elif v.h >= 23 and over <= 1.0:
            minor.append(v)
        elif v.h >= 17 and over <= 0.5:
            minor.append(v)
        else:
            major.append(v)
    return major, minor


def _severity_score(ieee: IEEE519CurrentReport) -> float:
    """
    Severity emphasizes low-order + big exceedances; downweights minor high-order misses.
    """
    sev = 0.0
    for v in ieee.worst_violations:
        over = max(0.0, v.ih_percent_of_il - v.limit_percent_of_il)

        if v.h <= 13:
            w = 5.0
        elif v.h <= 23:
            w = 2.0
        else:
            w = 1.0

        # downweight minor high-order exceedances
        if (v.h >= 23 and over <= 1.0) or (v.h >= 17 and over <= 0.5):
            w *= 0.2

        sev += w * over

    return float(sev)


def compare_mitigation_options(
    base_spectrum_pct_of_fund: Dict[int, float],
    il_a: float,
    isc_over_il: float,
    include_filters: List[str] | None = None,
) -> List[dict]:
    """
    Returns UI-ready list of dicts describing scenarios.
    Default ranking favors practical-mode outcomes.
    """
    include_filters = include_filters or ["none", "tuned_5_7", "broadband_passive", "active_filter_like"]

    isc_a = float(isc_over_il) * float(il_a)

    scenarios: List[ScenarioResult] = []

    # Baseline
    scenarios.append(run_scenario("baseline", base_spectrum_pct_of_fund, il_a=il_a, isc_a=isc_a))

    # Filtered
    for fkey in include_filters:
        if fkey == "none":
            continue
        att = FILTER_LIBRARY[fkey]
        sp = apply_attenuation(base_spectrum_pct_of_fund, att)
        scenarios.append(run_scenario(f"baseline + {fkey}", sp, il_a=il_a, isc_a=isc_a))

    # Practical ranking:
    # 1) TDD pass
    # 2) major violation count
    # 3) severity score
    # 4) TDD magnitude
    # 5) heating proxy
    def rank_key(s: ScenarioResult):
        major, _minor = _split_major_minor_violations(s.ieee519)
        tdd_fail = 0 if s.ieee519.tdd_pass else 1
        return (tdd_fail, len(major), _severity_score(s.ieee519), s.ieee519.tdd_percent, s.heating_proxy)

    scenarios_sorted = sorted(scenarios, key=rank_key)

    out: List[dict] = []
    for s in scenarios_sorted:
        worst = s.ieee519.worst_violations[0].h if s.ieee519.worst_violations else None

        strict_pass = bool(s.ieee519.tdd_pass and len(s.ieee519.worst_violations) == 0)

        major, minor = _split_major_minor_violations(s.ieee519)
        practical_pass = bool(s.ieee519.tdd_pass and len(major) == 0)

        severity = _severity_score(s.ieee519)

        out.append({
            "name": s.name,
            "thd_i_percent": round(s.thd_i_percent, 2),
            "tdd_percent": round(s.ieee519.tdd_percent, 2),
            "tdd_limit_percent": round(s.ieee519.tdd_limit_percent, 2),
            "strict_pass": strict_pass,
            "practical_pass": practical_pass,
            "severity_score": round(severity, 3),
            "risk_level": s.ieee519.risk_level,
            "isc_over_il": round(s.ieee519.isc_over_il, 1),
            "worst_harmonic": worst,
            "irms_over_i1": round(s.irms_over_i1, 4),
            "heating_proxy": round(s.heating_proxy, 4),
            "top_violations": [
                {"h": v.h, "ih_pct": round(v.ih_percent_of_il, 2), "limit_pct": round(v.limit_percent_of_il, 2)}
                for v in s.ieee519.worst_violations
            ],
            "major_violations": [
                {"h": v.h, "over_pct": round((v.ih_percent_of_il - v.limit_percent_of_il), 2)}
                for v in major
            ],
            "minor_violations": [
                {"h": v.h, "over_pct": round((v.ih_percent_of_il - v.limit_percent_of_il), 2)}
                for v in minor
            ],
            "interpretation": s.ieee519.interpretation,
        })

    return out
