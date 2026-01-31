"""
Demo: IEEE-519-style PCC current distortion check (Table 2 style)

This demonstrates the *correct* framing:
- Harmonics are evaluated at PCC
- Limits depend on Isc/IL
- IL is maximum demand fundamental current at PCC
"""

from pq_engine.models.ups_harmonics import harmonic_presets, load_adjust_spectrum, synthesize_current_time_series
from pq_engine.analysis.harmonic_fft import harmonic_fft
from pq_engine.analysis.ieee519 import evaluate_ieee519_current_limits


def main():
    # ---- UPS model setup
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

    # ---- Extract harmonics from waveform
    res = harmonic_fft(i, fs_hz=fs, f0_hz=f0, max_h=50, window="hann")

    # Build dict h->% of fundamental (exclude h=1)
    h_pct = {b.h: b.percent_of_fund for b in res.bins if b.h >= 2}

    # ---- PCC assumptions (THIS is where IEEE-519 lives)
    # IL should be maximum demand fundamental current at PCC.
    # For demo: assume IL ~= measured I1 at PCC.
    IL = res.i1_rms

    # Example Isc values:
    # - Weak PCC: Isc/IL ~ 15
    # - Moderate: 35
    # - Strong: 100
    Isc_over_IL = 35.0
    Isc = Isc_over_IL * IL

    rpt = evaluate_ieee519_current_limits(
        harmonic_percent_of_fund=h_pct,
        il_a=IL,
        isc_a=Isc,
        voltage_class="120V-69kV"
    )

    print("\n=== IEEE-519-style Current Distortion Check @ PCC ===")
    print(f"Voltage class: {rpt.voltage_class}")
    print(f"IL (A): {rpt.il_a:.2f}")
    print(f"Isc (A): {rpt.isc_a:.2f}")
    print(f"Isc/IL: {rpt.isc_over_il:.1f}  (category: {rpt.category_label})")

    print(f"\nTDD: {rpt.tdd_percent:.2f}%   Limit: {rpt.tdd_limit_percent:.2f}%   Pass: {rpt.tdd_pass}")

    # Show key harmonic checks (typical drivers in data centers)
    key = [5, 7, 11, 13, 17, 19]
    print("\nKey harmonics:")
    for c in rpt.checks:
        if c.h in key:
            status = "PASS" if c.pass_limit else "FAIL"
            print(f"  h{c.h:>2}  Ih={c.ih_percent_of_il:>6.2f}%  limit={c.limit_percent_of_il:>5.2f}%  {status}  band={c.band}")

    if rpt.worst_violations:
        print("\nWorst violations:")
        for c in rpt.worst_violations:
            over = c.ih_percent_of_il - c.limit_percent_of_il
            print(f"  h{c.h:>2} over by {over:.2f}% (Ih={c.ih_percent_of_il:.2f}%, limit={c.limit_percent_of_il:.2f}%)")

    print(f"\nOverall compliance risk: {rpt.risk_level}")
    print("Interpretation:")
    for line in rpt.interpretation:
        print(f" - {line}")


if __name__ == "__main__":
    main()
