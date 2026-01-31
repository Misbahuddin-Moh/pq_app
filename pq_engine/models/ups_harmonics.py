"""
UPS Harmonic Current Model (engineering-oriented)

Purpose:
- Provide realistic, configurable harmonic current spectra for data-center UPS / rectifier loads
- Synthesize time-domain current waveforms (not perfect sine assumptions)
- Support load-dependent distortion behavior

Notes:
- This is a spectrum-driven model: i(t) is built from fundamental + harmonic sinusoids.
- This reflects how many PQ field studies begin (vendor data / measurement-driven harmonic tables).
- Later we can add a pulse-conduction (rectifier physics) model, but this is the practical baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import numpy as np


@dataclass(frozen=True)
class UPSHarmonicProfile:
    """
    harmonic_pct_of_fund_rms: harmonic order -> percent of fundamental RMS current
    """
    name: str
    pulse: Optional[int]
    harmonic_pct_of_fund_rms: Dict[int, float]
    notes: str = ""


def harmonic_presets() -> Dict[str, UPSHarmonicProfile]:
    """
    Practical starting presets (tunable).
    Percent values are Ih_rms / I1_rms * 100.

    These are intentionally conservative/typical, not best-case marketing numbers.
    """
    return {
        # Legacy / simple diode-bridge rectifier UPS
        "6pulse_typical": UPSHarmonicProfile(
            name="6-pulse (typical)",
            pulse=6,
            harmonic_pct_of_fund_rms={
                5: 20.0, 7: 14.0,
                11: 9.0, 13: 7.0,
                17: 5.0, 19: 4.0,
                23: 3.0, 25: 2.0,
                29: 1.5, 31: 1.2,
            },
            notes="Typical for older 6-pulse UPS/rectifiers at moderate-high load. Strong 5th/7th."
        ),

        # Better front ends with phase-shift transformer cancellation
        "12pulse_typical": UPSHarmonicProfile(
            name="12-pulse (typical)",
            pulse=12,
            harmonic_pct_of_fund_rms={
                11: 10.0, 13: 8.0,
                23: 4.0, 25: 3.0,
                35: 2.0, 37: 1.5,
            },
            notes="5th/7th mostly canceled. Dominant 11th/13th."
        ),

        "18pulse_typical": UPSHarmonicProfile(
            name="18-pulse (typical)",
            pulse=18,
            harmonic_pct_of_fund_rms={
                17: 5.0, 19: 4.0,
                35: 2.0, 37: 1.5,
                53: 1.0,
            },
            notes="Lower THD-I, dominant 17th/19th."
        ),

        # Active Front End (IGBT/PWM rectifier). Low low-order harmonics; HF switching not modeled here.
        "afe_low_harm": UPSHarmonicProfile(
            name="AFE (low low-order harmonics)",
            pulse=None,
            harmonic_pct_of_fund_rms={
                5: 2.0, 7: 1.5,
                11: 1.0, 13: 0.8,
                17: 0.6, 19: 0.5,
            },
            notes="Represents modern AFE/PFC behavior for low-order harmonics; ignores HF switching ripple."
        ),
    }


def load_adjust_spectrum(
    base_pct: Dict[int, float],
    load_pu: float,
    model: str = "rectifier_like"
) -> Dict[int, float]:
    """
    Adjust harmonic percentages with load.
    Real UPS distortion is load-dependent:
    - Many rectifiers show *higher THD-I at light load* and improve at higher load.
    - Some AFE units stay relatively stable.

    load_pu: 0..1 (per-unit of rated load)

    model:
      - "rectifier_like": increase harmonic pct at light load
      - "flat": no change
    """
    load_pu = float(np.clip(load_pu, 0.05, 1.00))

    if model == "flat":
        scale = 1.0
    else:
        # Simple practical curve: at 20% load, harmonics ~1.35x; at 100% load, ~1.0x
        # smooth-ish: scale = a + b/(load_pu^c)
        a, b, c = 0.85, 0.15, 0.8
        scale = a + b / (load_pu ** c)
        scale = float(np.clip(scale, 0.95, 1.45))

    return {h: pct * scale for h, pct in base_pct.items()}


def synthesize_current_time_series(
    f_hz: float,
    i1_rms: float,
    harmonic_pct_of_fund_rms: Dict[int, float],
    cycles: int = 10,
    samples_per_cycle: int = 4096,
    fundamental_phase_deg: float = 0.0,
    harmonic_phase_mode: str = "random",
    seed: int = 17,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Build i(t) = I1*sin(wt+phi1) + sum_h Ih*sin(hwt + phih)

    Returns: (t, i, fs)

    harmonic_phase_mode:
      - "random": random phases (more realistic measured shape)
      - "zero": all phases 0 (least realistic)
      - "deterministic": phih = (h * 17 deg) style, stable/repeatable
    """
    f_hz = float(f_hz)
    fs = f_hz * samples_per_cycle
    n = int(cycles * samples_per_cycle)
    t = np.arange(n) / fs

    w = 2.0 * np.pi * f_hz

    i = np.sqrt(2.0) * i1_rms * np.sin(w * t + np.deg2rad(fundamental_phase_deg))

    rng = np.random.default_rng(seed)

    for h, pct in harmonic_pct_of_fund_rms.items():
        ih_rms = (pct / 100.0) * i1_rms
        ih_peak = np.sqrt(2.0) * ih_rms

        if harmonic_phase_mode == "zero":
            ph = 0.0
        elif harmonic_phase_mode == "deterministic":
            ph = np.deg2rad((h * 17.0) % 360.0)
        else:
            ph = rng.uniform(0.0, 2.0 * np.pi)

        i = i + ih_peak * np.sin(h * w * t + ph)

    return t, i, fs


def thd_i_from_spectrum(harmonic_pct_of_fund_rms: Dict[int, float]) -> float:
    """
    THD-I = sqrt(sum (Ih^2)) / I1.
    Given spectrum as % of I1 RMS:
      THD = sqrt(sum((pct/100)^2))
    """
    s = 0.0
    for pct in harmonic_pct_of_fund_rms.values():
        s += (pct / 100.0) ** 2
    return float(np.sqrt(s))


def describe_profile(profile: UPSHarmonicProfile, load_pu: float = 1.0) -> str:
    adj = load_adjust_spectrum(profile.harmonic_pct_of_fund_rms, load_pu)
    thd = thd_i_from_spectrum(adj) * 100.0
    return (
        f"{profile.name}\n"
        f"- load: {load_pu:.2f} pu\n"
        f"- approx THD-I (from spectrum): {thd:.1f}%\n"
        f"- notes: {profile.notes}\n"
    )
