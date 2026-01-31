"""
Mitigation comparison engine (data-center oriented)

What this does:
- Compare UPS harmonic presets (6-pulse / 12-pulse / 18-pulse / AFE)
- Apply mitigation via simple attenuation models:
  - tuned passive (targets 5th/7th strongly)
  - broadband passive (moderate across a band)
  - active filter / AFE-like cleanup (strong low-order reduction)

Outputs:
- UI-ready scenario summary dicts
- Engineer-style metrics: THD-I, TDD, IEEE-519 pass/fail, Irms inflation, heating proxy

Important:
- This is not an EMTP model of filter impedance. It's an engineering screening tool.
- In real life, filter performance depends on system impedance, tuning, detuning, resonance, etc.
  We'll add "source impedance / resonance risk" later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Callable, List, Tuple
import math

from pq_engine.analysis.ieee519 import evaluate_ieee519_current_limits, IEEE519CurrentReport


# ----------------------------
# Filter attenuation models
# ----------------------------

def attenuation_none(h: int) -> float:
    """No mitigation."""
    return 1.0


def attenuation_tuned_5_7(h: int) -> float:
    """
    Simple tuned passive filter effect:
    - Strong attenuation around 5th and 7th
    - Mild effect on nearby low-order
    """
    if h == 5:
        return 0.25  # 75% reduction
    if h == 7:
        return 0.30  # 70% reduction
    if h in (11, 13):
        return 0.65  # partial improvement
    if 2 <= h <= 25:
        return 0.85  # mild broadband benefit due to impedance shaping
    return 0.95


def attenuation_broadband_passive(h: int) -> float:
    """
    Broadband passive / line reactor + filter bank style:
    - Moderate reduction across low-order harmonics
    - Less aggressive than tuned
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
    Active harmonic filter / AFE-like low-order cleanup:
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
    """Return new spectrum with attenuation applied per harmonic order."""
    out: Dict[int, float] = {}
    for h, pct in harmonic_pct_of_fund.items():
        out[h] = float(pct) * float(attenuation_fn(int(h)))
    return out


# ----------------------------
# Engineer metrics
# ----------------------------

def thd_i_from_pct(harmonic_pct_of_fund: Dict[int, float], max_h: int = 50) -> float:
    """THD-I from % of fundamental RMS."""
    s = 0.0
    for h, pct in harmonic_pct_of_fund.items():
        if 2 <= int(h) <= max_h:
            s += (pct / 100.0) ** 2
    return math.sqrt(s)  # per-unit


def irms_inflation_factor(thd_pu: float) -> float:
    """Irms / I1 assuming harmonics orthogonal: sqrt(1 + THD^2)."""
    return math.sqrt(1.0 + thd_pu * thd_pu)


def transformer_heating_proxy(harmonic_pct_of_fund: Dict[int, float], max_h: int = 50) -> float:
    """
    Simple transformer eddy-current style proxy:
    ~ sum(h^2 * Ih^2) where Ih is per-unit of I1.
    Higher orders contribute disproportionately to eddy losses.
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
        voltage_class="120V-69kV"
    )

    return ScenarioResult(
        name=name,
        spectrum_pct_of_fund=spectrum_pct_of_fund,
        thd_i_percent=thd_pct,
        irms_over_i1=infl,
        heating_proxy=heat,
        ieee519=rpt
    )


def compare_mitigation_options(
    base_spectrum_pct_of_fund: Dict[int, float],
    il_a: float,
    isc_over_il: float,
    include_filters: List[str] = None,
) -> List[dict]:
    """
    Returns UI-ready list of dicts describing scenarios.
    """
    include_filters = include_filters or ["none", "tuned_5_7", "broadband_passive", "active_filter_like"]

    isc_a = float(isc_over_il) * float(il_a)

    scenarios: List[ScenarioResult] = []

    # Baseline
    scenarios.append(run_scenario("baseline", base_spectrum_pct_of_fund, il_a=il_a, isc_a=isc_a))

    # Filtered versions
    for fkey in include_filters:
        if fkey == "none":
            continue
        att = FILTER_LIBRARY[fkey]
        sp = apply_attenuation(base_spectrum_pct_of_fund, att)
        scenarios.append(run_scenario(f"baseline + {fkey}", sp, il_a=il_a, isc_a=isc_a))

    # Rank: prefer pass, then lower TDD, then lower heating proxy
    def rank_key(s: ScenarioResult):
        pass_score = 0 if s.ieee519.tdd_pass and len(s.ieee519.worst_violations) == 0 else 1
        return (pass_score, s.ieee519.tdd_percent, s.heating_proxy)

    scenarios_sorted = sorted(scenarios, key=rank_key)

    out: List[dict] = []
    for s in scenarios_sorted:
        worst = s.ieee519.worst_violations[0].h if s.ieee519.worst_violations else None
        out.append({
            "name": s.name,
            "thd_i_percent": round(s.thd_i_percent, 2),
            "tdd_percent": round(s.ieee519.tdd_percent, 2),
            "tdd_limit_percent": round(s.ieee519.tdd_limit_percent, 2),
            "ieee519_pass": bool(s.ieee519.tdd_pass and len(s.ieee519.worst_violations) == 0),
            "risk_level": s.ieee519.risk_level,
            "isc_over_il": round(s.ieee519.isc_over_il, 1),
            "worst_harmonic": worst,
            "irms_over_i1": round(s.irms_over_i1, 4),
            "heating_proxy": round(s.heating_proxy, 4),
            "top_violations": [
                {"h": v.h, "ih_pct": round(v.ih_percent_of_il, 2), "limit_pct": round(v.limit_percent_of_il, 2)}
                for v in s.ieee519.worst_violations
            ],
            "interpretation": s.ieee519.interpretation,
        })

    return out
