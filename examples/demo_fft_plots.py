"""
Demo: generate UPS waveform, extract harmonics via FFT, plot waveform + spectrum.
"""

import numpy as np
import matplotlib.pyplot as plt

from pq_engine.models.ups_harmonics import harmonic_presets, load_adjust_spectrum, synthesize_current_time_series
from pq_engine.analysis.harmonic_fft import harmonic_fft


def main():
    f0 = 60.0
    i1_rms = 100.0
    load_pu = 0.6

    profile = harmonic_presets()["6pulse_typical"]
    spectrum = load_adjust_spectrum(profile.harmonic_pct_of_fund_rms, load_pu, model="rectifier_like")

    t, i, fs = synthesize_current_time_series(
        f_hz=f0,
        i1_rms=i1_rms,
        harmonic_pct_of_fund_rms=spectrum,
        cycles=10,
        samples_per_cycle=4096,
        harmonic_phase_mode="random",
        seed=17,
    )

    res = harmonic_fft(i, fs_hz=fs, f0_hz=f0, max_h=50, window="hann")

    print(f"Measured I1_rms: {res.i1_rms:.2f} A")
    print(f"Measured Irms_total: {res.i_rms_total:.2f} A")
    print(f"Measured THD-I: {res.thd_i*100:.2f}%")

    # --- Plot: time waveform (show 1 cycle)
    samples_per_cycle = int(fs / f0)
    n_show = samples_per_cycle
    plt.figure()
    plt.plot(t[:n_show] * 1000.0, i[:n_show])
    plt.xlabel("Time (ms)")
    plt.ylabel("Current (A)")
    plt.title("UPS Input Current (1 cycle)")
    plt.grid(True)

    # --- Plot: harmonic spectrum bar chart (2..50)
    hs = [b.h for b in res.bins if 2 <= b.h <= 50]
    pct = [b.percent_of_fund for b in res.bins if 2 <= b.h <= 50]

    plt.figure()
    plt.bar(hs, pct)
    plt.xlabel("Harmonic Order (h)")
    plt.ylabel("Ih (% of fundamental RMS)")
    plt.title("Harmonic Spectrum (2nd–50th)")
    plt.grid(True, axis="y")

    plt.show()


if __name__ == "__main__":
    main()
