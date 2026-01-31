"""
Demo: compare mitigation options for a UPS harmonic spectrum at PCC.

Shows how the same baseline UPS spectrum changes with:
- tuned filter (5th/7th)
- broadband passive
- active filter-like mitigation
"""

from pq_engine.models.ups_harmonics import harmonic_presets, load_adjust_spectrum
from pq_engine.analysis.mitigation import compare_mitigation_options


def print_table(rows):
    # Lightweight pretty print without extra deps
    cols = ["name", "tdd_percent", "tdd_limit_percent", "ieee519_pass", "risk_level", "worst_harmonic", "heating_proxy"]
    widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    header = " | ".join(c.ljust(widths[c]) for c in cols)
    print(header)
    print("-" * len(header))
    for r in rows:
        line = " | ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols)
        print(line)


def main():
    presets = harmonic_presets()

    # Choose a baseline UPS type
    profile = presets["6pulse_typical"]

    # Load-dependent spectrum
    load_pu = 0.6
    base = load_adjust_spectrum(profile.harmonic_pct_of_fund_rms, load_pu, model="rectifier_like")

    # PCC inputs (demo)
    IL = 100.0          # A (max demand fundamental at PCC) - set this realistically later
    Isc_over_IL = 35.0  # moderate PCC strength

    results = compare_mitigation_options(
        base_spectrum_pct_of_fund=base,
        il_a=IL,
        isc_over_il=Isc_over_IL,
        include_filters=["none", "tuned_5_7", "broadband_passive", "active_filter_like"]
    )

    print(f"\nBaseline profile: {profile.name} @ load {load_pu:.2f} pu")
    print(f"PCC: Isc/IL = {Isc_over_IL:.1f}, IL = {IL:.1f} A\n")

    print_table(results)

    print("\nTop recommendation (ranked):")
    best = results[0]
    print(f"- {best['name']}")
    print(f"  TDD {best['tdd_percent']}% (limit {best['tdd_limit_percent']}%), risk {best['risk_level']}")
    if best["top_violations"]:
        print("  Still violating:")
        for v in best["top_violations"][:3]:
            print(f"   - h{v['h']}: {v['ih_pct']}% > {v['limit_pct']}%")
    else:
        print("  No individual harmonic violations in evaluation band (2–50).")


if __name__ == "__main__":
    main()
