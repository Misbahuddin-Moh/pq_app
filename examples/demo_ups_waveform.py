"""
Demo: UPS harmonic current model
Runs waveform synthesis and prints basic metrics.
(Plots will come in the next commit using matplotlib.)
"""

import numpy as np
from pq_engine.models.ups_harmonics import harmonic_presets, load_adjust_spectrum, synthesize_current_time_series, thd_i_from_spectrum, describe_profile

def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x**2)))

def main():
    presets = harmonic_presets()
    profile = presets["6pulse_typical"]

    load_pu = 0.6  # 60% load example
    spectrum = load_adjust_spectrum(profile.harmonic_pct_of_fund_rms, load_pu, model="rectifier_like")

    print(describe_profile(profile, load_pu=load_pu))

    f0 = 60.0
    i1_rms = 100.0

    t, i, fs = synthesize_current_time_series(
        f_hz=f0,
        i1_rms=i1_rms,
        harmonic_pct_of_fund_rms=spectrum,
        cycles=10,
        samples_per_cycle=4096,
        harmonic_phase_mode="random",
        seed=17,
    )

    print(f"fs = {fs:.1f} Hz, samples = {len(i)}")
    print(f"I1_rms (target) = {i1_rms:.2f} A")
    print(f"Irms_total (time) = {rms(i):.2f} A")

    thd = thd_i_from_spectrum(spectrum) * 100.0
    print(f"THD-I (from spectrum) = {thd:.2f}%")
    dist_pf = 1.0 / np.sqrt(1.0 + (thd/100.0)**2)
    print(f"Distortion PF (approx) = {dist_pf:.3f}")

    # Print top harmonics
    top = sorted(spectrum.items(), key=lambda kv: kv[1], reverse=True)[:8]
    print("Top harmonics (% of fundamental RMS):")
    for h, pct in top:
        print(f"  h={h:>2}: {pct:>6.2f}%")

if __name__ == "__main__":
    main()
