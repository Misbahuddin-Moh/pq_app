"""
Demo: compare mitigation options for a UPS harmonic spectrum at PCC.

Prints a simple table (no extra deps) showing both:
- strict_pass (literal IEEE-519 check)
- practical_pass (engineering judgement for minor high-order exceedances)
- severity_score (for ranking in practical mode)
"""

from pq_engine.models.ups_harmonics import harmonic_presets, load_adjust_spectrum
from pq_engine.analysis.mitigation import compare_mitigation_options


def print_table(rows):
    cols = [
        "name",
        "tdd_percent",
        "tdd_limit_percent",
        "strict_pass",
        "practical_pass",
        "severity_score",
        "risk_level",
        "worst_harmonic",
        "heating_proxy",
    ]
    widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    header = " | ".join(c.ljust(widths[c]) for c in cols)
    print(header)
    print("-" * len(header))
    for r in rows:
        line = " | ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols)
        print(line)


def main():
    presets = harmonic_presets()

    # Baseline UPS type
    profile = presets["6pulse_typical"]

    # Load-dependent spectrum
    load_pu = 0.6
    base = load_adjust_spectrum(profile.harmonic_pct_of_fund_rms, load_pu, model="rectifier_like")

    # PCC inputs (demo)
    IL = 100.0
    Isc_over_IL = 35.0

    results = compare_mitigation_options(
        base_spectrum_pct_of_fund=base,
        il_a=IL,
        isc_over_il=Isc_over_IL,
        include_filters=["none", "tuned_5_7", "broadband_passive", "active_filter_like"],
    )

    print(f"\nBaseline profile: {profile.name} @ load {load_pu:.2f} pu")
    print(f"PCC: Isc/IL = {Isc_over_IL:.1f}, IL = {IL:.1f} A\n")

    print_table(results)

    print("\nTop recommendation (ranked, practical-mode default):")
    best = results[0]
    print(f"- {best['name']}")
    print(f"  TDD {best['tdd_percent']}% (limit {best['tdd_limit_percent']}%), risk {best['risk_level']}")
    print(f"  strict_pass={best['strict_pass']} practical_pass={best['practical_pass']} severity={best['severity_score']}")

    if best["top_violations"]:
        print("  Still violating (strict IEEE-519):")
        for v in best["top_violations"][:3]:
            print(f"   - h{v['h']}: {v['ih_pct']}% > {v['limit_pct']}%")
    else:
        print("  No individual harmonic violations in evaluation band (2–50).")

    if best["major_violations"]:
        print("  Major violations (practical mode):")
        for v in best["major_violations"][:3]:
            print(f"   - h{v['h']} over by {v['over_pct']}%")
    elif best["minor_violations"]:
        print("  Only minor high-order exceedances remain (practical mode).")


if __name__ == "__main__":
    main()
