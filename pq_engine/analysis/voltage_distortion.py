"""
Voltage distortion estimation at PCC.

We estimate THDv from current harmonic spectrum and a simple source impedance model.

Core approximation (engineering screening):
  Vh_rms ≈ Ih_rms * |Zsys(h)|

Then:
  THDv = sqrt(sum_{h>=2}(Vh^2)) / V1

Where:
- Ih_rms derived from % of fundamental current I1
- V1 is the fundamental voltage (use VLL or VLN depending on how you define Z1)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional
import math


@dataclass(frozen=True)
class SourceImpedanceModel:
    """
    Simple PCC source impedance model.

    z1_ohm: magnitude of fundamental Thevenin impedance per phase (ohms).
            Use per-phase impedance consistent with VLN and phase currents.

    xr: X/R ratio at fundamental (dimensionless). Used to compute R and X components.
    freq_exp: exponent for impedance magnitude scaling with harmonic order:
        |Z(h)| = |Z1| * h^freq_exp
      - 0.0 => flat magnitude with frequency (rough, sometimes ok for short bus + transformer dominated)
      - 1.0 => inductive-like magnitude scaling ~ h
      - 0.5 => intermediate
    """
    z1_ohm: float
    xr: float = 10.0
    freq_exp: float = 1.0


@dataclass(frozen=True)
class VoltageDistortionResult:
    thdv_percent: float
    vh_by_harmonic_v: Dict[int, float]  # per-harmonic voltage RMS magnitudes (V)
    v1_v: float
    limit_percent: float
    pass_limit: bool
    risk_level: str
    interpretation: str


def z_mag_at_harmonic(z1_ohm: float, h: int, freq_exp: float) -> float:
    if h < 1:
        raise ValueError("harmonic order must be >= 1")
    if z1_ohm <= 0:
        raise ValueError("z1_ohm must be > 0")
    return float(z1_ohm) * (float(h) ** float(freq_exp))


def thdv_from_spectrum(
    harmonic_pct_of_fund: Dict[int, float],
    i1_a: float,
    v1_v: float,
    src: SourceImpedanceModel,
    max_h: int = 50,
    voltage_limit_percent: float = 5.0,
) -> VoltageDistortionResult:
    """
    Compute THDv% from harmonic spectrum and source impedance.

    Args:
      harmonic_pct_of_fund: {h: Ih(% of I1 RMS)}
      i1_a: fundamental RMS current (A) basis (use IL for IEEE-519 PCC checks)
      v1_v: fundamental RMS voltage basis (V) (per-phase VLN recommended)
      src: source impedance model
      voltage_limit_percent: default 5% (common planning threshold; adjustable)

    Returns:
      VoltageDistortionResult
    """
    if i1_a <= 0:
        raise ValueError("i1_a must be > 0")
    if v1_v <= 0:
        raise ValueError("v1_v must be > 0")

    vh: Dict[int, float] = {}
    s = 0.0

    for h, pct in harmonic_pct_of_fund.items():
        h = int(h)
        if 2 <= h <= max_h:
            ih_a = (float(pct) / 100.0) * float(i1_a)
            zh = z_mag_at_harmonic(src.z1_ohm, h, src.freq_exp)
            vh_a = abs(ih_a) * abs(zh)
            vh[h] = vh_a
            s += vh_a * vh_a

    thdv = math.sqrt(s) / float(v1_v)
    thdv_pct = 100.0 * thdv

    pass_limit = thdv_pct <= float(voltage_limit_percent)

    # Risk: simple bands
    if thdv_pct <= 0.6 * voltage_limit_percent:
        risk = "LOW"
    elif thdv_pct <= voltage_limit_percent:
        risk = "MEDIUM"
    else:
        risk = "HIGH"

    interp = (
        "Voltage distortion is driven by harmonic currents flowing through PCC source impedance. "
        "Even if current TDD is acceptable, weak PCC (high impedance) can produce high THDv. "
        "Confirm impedance assumptions with short-circuit data and field measurements."
    )

    return VoltageDistortionResult(
        thdv_percent=thdv_pct,
        vh_by_harmonic_v=vh,
        v1_v=float(v1_v),
        limit_percent=float(voltage_limit_percent),
        pass_limit=bool(pass_limit),
        risk_level=risk,
        interpretation=interp,
    )


def vln_from_vll(vll_v: float) -> float:
    """Convert line-line RMS voltage to line-neutral RMS voltage."""
    return float(vll_v) / 1.7320508075688772
