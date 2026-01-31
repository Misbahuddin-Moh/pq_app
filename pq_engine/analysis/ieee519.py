"""
IEEE-519-style current distortion evaluation at PCC (Table 2 style)

Key points (field reality):
- IEEE-519 limits are applied at the PCC, not at UPS terminals.
- Limits are based on Isc/IL (short-circuit ratio), and expressed as % of IL.
- IL is the maximum demand load current (fundamental component) at PCC under normal operation.

This module implements IEEE-519-2014-style Table 2 logic for systems rated 120 V through 69 kV.
Even-harmonic limits are taken as 25% of corresponding odd-harmonic limits (per table notes). :contentReference[oaicite:1]{index=1}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import math


# Table 2 (120 V through 69 kV) - percent of IL
# Bands are by harmonic order (odd harmonics); even harmonics limited separately.
# Row selection is by Isc/IL.
_TABLE2_ROWS = [
    # (min_exclusive, max_inclusive, limits_by_band, TDD_limit)
    # Bands: [2-10], [11-16], [17-22], [23-34], [35-50]
    (float("-inf"), 20.0,  [4.0, 2.0, 1.5, 0.6, 0.3],  5.0),
    (20.0,          50.0,  [7.0, 3.5, 2.5, 1.0, 0.5],  8.0),
    (50.0,          100.0, [10.0, 4.5, 4.0, 1.5, 0.7], 12.0),
    (100.0,         1000.0,[12.0, 5.5, 5.0, 2.0, 1.0], 15.0),
    (1000.0,        float("inf"), [15.0, 7.0, 6.0, 2.5, 1.4], 20.0),
]


def _band_index(h: int) -> Optional[int]:
    """
    Map harmonic order to Table-2 band index.
    Returns None if outside evaluation range (e.g., h<2 or h>50).
    """
    if h < 2 or h > 50:
        return None
    if 2 <= h < 11:
        return 0
    if 11 <= h < 17:
        return 1
    if 17 <= h < 23:
        return 2
    if 23 <= h < 35:
        return 3
    return 4  # 35..50


def _select_row(isc_over_il: float) -> Tuple[List[float], float, str]:
    """
    Returns (limits_by_band, tdd_limit, label)
    """
    for lo, hi, limits, tdd in _TABLE2_ROWS:
        if (isc_over_il > lo) and (isc_over_il <= hi):
            return limits, tdd, f"{int(lo) if lo!=-math.inf else '<'}–{int(hi)}"
    # fallback (shouldn't happen)
    limits, tdd = _TABLE2_ROWS[-1][2], _TABLE2_ROWS[-1][3]
    return limits, tdd, ">1000"


@dataclass
class HarmonicLimitCheck:
    h: int
    ih_percent_of_il: float
    limit_percent_of_il: float
    pass_limit: bool
    band: str
    note: str = ""


@dataclass
class IEEE519CurrentReport:
    voltage_class: str
    isc_a: float
    il_a: float
    isc_over_il: float
    category_label: str
    tdd_percent: float
    tdd_limit_percent: float
    tdd_pass: bool
    checks: List[HarmonicLimitCheck]
    worst_violations: List[HarmonicLimitCheck]
    risk_level: str
    interpretation: List[str]


def evaluate_ieee519_current_limits(
    harmonic_percent_of_fund: Dict[int, float],
    il_a: float,
    isc_a: float,
    voltage_class: str = "120V-69kV",
    even_harmonic_factor: float = 0.25,
) -> IEEE519CurrentReport:
    """
    harmonic_percent_of_fund: mapping h -> Ih (% of fundamental RMS).
      If your fundamental RMS at PCC equals IL, then this is also Ih (% of IL).

    il_a: IL (A) at PCC = maximum demand fundamental current (NOT instantaneous current)
    isc_a: Isc (A) short-circuit current at PCC

    Returns: structured report with pass/fail checks and interpretation.
    """
    if il_a <= 0:
        raise ValueError("IL must be > 0 A")
    if isc_a <= 0:
        raise ValueError("Isc must be > 0 A")

    isc_over_il = isc_a / il_a
    limits_by_band, tdd_limit, label = _select_row(isc_over_il)

    # Build checks
    checks: List[HarmonicLimitCheck] = []

    # Compute TDD (up to 50th) as sqrt(sum Ih^2)/IL
    sum_sq = 0.0

    for h, pct in harmonic_percent_of_fund.items():
        b = _band_index(h)
        if b is None:
            continue

        ih_pct_il = float(pct)  # assuming pct relative to IL (fundamental RMS demand current)

        # band labels
        band_name = ["2–10", "11–16", "17–22", "23–34", "35–50"][b]

        # odd limit from table
        limit = limits_by_band[b]

        # even harmonic limit adjustment
        note = ""
        if h % 2 == 0:
            limit = limit * even_harmonic_factor
            note = f"even harmonic limit = {even_harmonic_factor*100:.0f}% of odd limit"

        pass_limit = ih_pct_il <= limit + 1e-12

        checks.append(HarmonicLimitCheck(
            h=h,
            ih_percent_of_il=ih_pct_il,
            limit_percent_of_il=float(limit),
            pass_limit=pass_limit,
            band=band_name,
            note=note
        ))

        # contribute to TDD
        sum_sq += (ih_pct_il / 100.0) ** 2

    tdd = math.sqrt(sum_sq) * 100.0  # percent
    tdd_pass = tdd <= tdd_limit + 1e-12

    # Worst violations
    violations = [c for c in checks if not c.pass_limit]
    violations_sorted = sorted(
        violations,
        key=lambda c: (c.ih_percent_of_il - c.limit_percent_of_il),
        reverse=True
    )
    worst = violations_sorted[:5]

    # Risk interpretation (simple but field-useful)
    interpretation: List[str] = []
    if isc_over_il < 20:
        interpretation.append("Weak PCC (low Isc/IL): harmonic currents are more likely to cause voltage distortion upstream.")
    elif isc_over_il < 50:
        interpretation.append("Moderate PCC strength: compliance depends strongly on low-order (5th/7th/11th/13th) magnitudes.")
    else:
        interpretation.append("Strong PCC: current limits are higher, but large 5th/7th can still trigger issues in shared systems.")

    if not tdd_pass:
        interpretation.append("TDD exceeds limit: utility/PCC compliance risk is elevated; expect higher RMS heating and potential voltage THD concerns.")
    if worst:
        hw = ", ".join([f"h{c.h}" for c in worst[:3]])
        interpretation.append(f"Major individual harmonic violations: {hw}. These typically drive transformer/cable heating and upstream voltage distortion.")

    # Rough risk level
    if (not tdd_pass) and len(violations) >= 2:
        risk = "HIGH"
    elif (not tdd_pass) or len(violations) >= 1:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    return IEEE519CurrentReport(
        voltage_class=voltage_class,
        isc_a=float(isc_a),
        il_a=float(il_a),
        isc_over_il=float(isc_over_il),
        category_label=label,
        tdd_percent=float(tdd),
        tdd_limit_percent=float(tdd_limit),
        tdd_pass=bool(tdd_pass),
        checks=sorted(checks, key=lambda c: c.h),
        worst_violations=worst,
        risk_level=risk,
        interpretation=interpretation
    )
