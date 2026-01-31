"""
Source impedance utilities (utility-style).

Given short-circuit MVA at PCC and VLL, compute:
- Thevenin impedance magnitude (per-phase) at fundamental
- Available short-circuit current Isc

Key relationships for balanced 3-phase:
  Ssc = sqrt(3) * VLL * Isc
  Zth (per-phase) = V_phase / I_phase = (VLL/sqrt(3)) / Isc
  => Zth = VLL^2 / Ssc

Where:
- VLL in volts
- Ssc in VA
- Zth in ohms (per-phase magnitude at fundamental)
"""

from __future__ import annotations
import math


_SQRT3 = 1.7320508075688772


def isc_a_from_sc_mva(vll_v: float, sc_mva: float) -> float:
    """Compute 3-phase short-circuit current magnitude (A RMS line) from SC MVA and VLL."""
    if vll_v <= 0:
        raise ValueError("vll_v must be > 0.")
    if sc_mva <= 0:
        raise ValueError("sc_mva must be > 0.")
    s_va = float(sc_mva) * 1e6
    return s_va / (_SQRT3 * float(vll_v))


def zth_ohm_from_sc_mva(vll_v: float, sc_mva: float) -> float:
    """
    Compute Thevenin impedance magnitude (ohms, per-phase) at fundamental from SC MVA and VLL.
      Zth = VLL^2 / Ssc
    """
    if vll_v <= 0:
        raise ValueError("vll_v must be > 0.")
    if sc_mva <= 0:
        raise ValueError("sc_mva must be > 0.")
    s_va = float(sc_mva) * 1e6
    return (float(vll_v) ** 2) / s_va


def isc_over_il_from_sc_mva(vll_v: float, sc_mva: float, il_a: float) -> float:
    """Compute Isc/IL using SC MVA derived Isc and provided IL."""
    if il_a <= 0:
        raise ValueError("il_a must be > 0.")
    return isc_a_from_sc_mva(vll_v, sc_mva) / float(il_a)
