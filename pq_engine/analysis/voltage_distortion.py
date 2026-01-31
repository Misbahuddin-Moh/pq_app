"""
Voltage distortion estimation at PCC.

Screening approximation:
  Vh_rms ≈ Ih_rms * |Zsys(h)|

Then:
  THDv = sqrt(sum_{h>=2}(Vh^2)) / V1

Where:
- Ih derived from harmonic spectrum (% of fundamental current I1)
- Zsys(h) from source impedance model
- V1 is fundamental RMS voltage (VLN recommended if Z is per-phase)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict
import math

from pq_engine.analysis.source_impedance import zth_ohm_from_sc_mva


@dataclass(frozen=True)
class SourceImpedanceModel:
    """
    Simple PCC source impedance model.

    z1_ohm: magnitude of fundamental Thevenin impedance per phase (ohms).
    freq_exp: exponent for impedance magnitude scaling with harmonic order:
        |Z(h)| = |Z1| * h^freq_exp
      - 0.0 => flat magnitude with frequency
      - 1.0 => inductive-like magnitude scaling ~ h
    xr: kept for future expansion (R/X separation), not used in magnitude-only model yet.
    """
    z1_ohm: float
    xr: float = 10.0
    freq_exp: float = 1.0


@dataclass(frozen=True)
class VoltageDistortionResult:
    thdv_percent: float
    vh_by_harmonic_v: Dict[int, float]
    v1_v: float
    limit_percent: float
    pass_limit: bool
    risk_level: str
    interpretation: str


def vln_from_vll(vll_v: float) -> float:
    """Convert line-line RMS voltage to line-neutral RMS voltage."""
    return float(vll_v) / 1.7320508075688772


def z_mag_at_harmonic(z1_ohm: float, h: int, freq_exp: float) -> float:
    if h < 1:
        raise ValueError("harmonic order must be >= 1")
    if z1_ohm <= 0:
        raise ValueError("z1_ohm must be > 0")
    return float(z1_ohm) * (float(h) ** float(freq_exp))


def source_from_sc_mva(vll_v: float, sc_mva: float, xr: float = 10.0, freq_exp: float = 1.0) -> SourceImpedanceModel:
    """Build a SourceImpedanceModel from short-circuit MVA and VLL."""
    z1 = zth_ohm_from_sc_mva(vll_v, sc_mva)
    return SourceImpedanceModel(z1_ohm=z1, xr=xr, freq_exp=freq_exp)


def thdv_from_spectrum(
    harmonic_pct_of_fund: Dict[int, float],
    i1_a: float,
    v1_v: float,
    src: SourceImpedanceModel,
    max_h: int = 50,
    voltage_limit_percent: float = 5.0,
) -> VoltageDistortionResult:
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
            vh_v = abs(ih_a) * abs(zh)
            vh[h] = vh_v
            s += vh_v * vh_v

    thdv = math.sqrt(s) / float(v1_v)
    thdv_pct = 100.0 * thdv
    pass_limit = thdv_pct <= float(voltage_limit_percent)

    if thdv_pct <= 0.6 * voltage_limit_percent:
        risk = "LOW"
    elif thdv_pct <= voltage_limit_percent:
        risk = "MEDIUM"
    else:
        risk = "HIGH"

    interp = (
        "THDv is produced when harmonic currents flow through PCC source impedance. "
        "Weak PCC (low short-circuit MVA / high impedance) amplifies THDv. "
        "Confirm Zth using short-circuit data and verify with field measurements."
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
