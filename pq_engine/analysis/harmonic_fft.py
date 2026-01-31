"""
Harmonic extraction using FFT (engineering-correct scaling)

Assumptions:
- Fundamental frequency f0 known (e.g., 60 Hz)
- Time record contains an integer number of cycles (recommended)
- Uses windowing to reduce leakage when cycles aren't perfectly integer

Outputs:
- Fundamental RMS, harmonic RMS table, THD-I
- Harmonic phase (useful later for vector summing and engineering interpretation)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, List, Optional
import numpy as np


@dataclass
class HarmonicBin:
    h: int
    freq_hz: float
    i_rms: float
    percent_of_fund: float
    phase_deg: float


@dataclass
class HarmonicAnalysis:
    f0_hz: float
    fs_hz: float
    n_samples: int
    window: str
    i_rms_total: float
    i1_rms: float
    thd_i: float
    bins: List[HarmonicBin]


def _window_vec(n: int, window: str) -> np.ndarray:
    w = window.lower()
    if w in ("rect", "rectangular", "none"):
        return np.ones(n)
    if w in ("hann", "hanning"):
        return np.hanning(n)
    if w == "hamming":
        return np.hamming(n)
    raise ValueError(f"Unknown window: {window}")


def harmonic_fft(
    i: np.ndarray,
    fs_hz: float,
    f0_hz: float,
    max_h: int = 50,
    window: str = "hann",
) -> HarmonicAnalysis:
    """
    Extract harmonic RMS magnitudes using rFFT.

    Scaling notes (single-sided amplitude):
    - For a windowed FFT, amplitude must be corrected by coherent gain (CG).
      CG = mean(window)
    - For real signals, single-sided magnitude: A_peak ≈ (2/N) * |X[k]| / CG
    - Then I_rms = A_peak / sqrt(2)

    We map harmonics to the nearest FFT bin of h*f0.
    Best accuracy when record length contains integer cycles of f0.
    """
    i = np.asarray(i, dtype=float)
    n = i.size
    if n < 8:
        raise ValueError("Signal too short")

    w = _window_vec(n, window)
    cg = float(np.mean(w))  # coherent gain for amplitude correction
    iw = i * w

    X = np.fft.rfft(iw)
    freqs = np.fft.rfftfreq(n, d=1.0/fs_hz)

    i_rms_total = float(np.sqrt(np.mean(i**2)))

    bins: List[HarmonicBin] = []

    def bin_for_freq(freq: float) -> int:
        return int(np.argmin(np.abs(freqs - freq)))

    # Fundamental
    k1 = bin_for_freq(f0_hz)
    X1 = X[k1]
    A1_peak = (2.0 / n) * (np.abs(X1) / cg)
    i1_rms = float(A1_peak / np.sqrt(2.0))
    phase1 = float(np.degrees(np.angle(X1)))

    # Harmonics
    for h in range(1, max_h + 1):
        fh = h * f0_hz
        kh = bin_for_freq(fh)
        Xh = X[kh]
        Ah_peak = (2.0 / n) * (np.abs(Xh) / cg)
        ih_rms = float(Ah_peak / np.sqrt(2.0))
        pct = float((ih_rms / i1_rms * 100.0) if i1_rms > 1e-12 else 0.0)
        ph = float(np.degrees(np.angle(Xh)))
        bins.append(HarmonicBin(h=h, freq_hz=float(freqs[kh]), i_rms=ih_rms, percent_of_fund=pct, phase_deg=ph))

    # THD-I (exclude fundamental h=1)
    harm_sq = sum(b.i_rms**2 for b in bins if b.h >= 2)
    thd_i = float(np.sqrt(harm_sq) / i1_rms) if i1_rms > 1e-12 else 0.0

    return HarmonicAnalysis(
        f0_hz=f0_hz,
        fs_hz=fs_hz,
        n_samples=n,
        window=window,
        i_rms_total=i_rms_total,
        i1_rms=i1_rms,
        thd_i=thd_i,
        bins=bins,
    )
