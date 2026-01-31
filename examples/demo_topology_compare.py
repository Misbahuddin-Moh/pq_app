"""
Demo: compare UPS topologies + mitigation at PCC with IEEE-519-style IL sizing.

- Computes IL from demand kW, VLL, PF, efficiency (IEEE-519 aligned)
- Compares 6/12/18 pulse and AFE presets
- Applies mitigation filters (attenuation models)
- Prints ranked table with strict vs practical pass
- Plots overlay of top 4 scenarios
"""

import matplotlib.pyplot as plt

from pq_engine.analysis.pcc_sizing import PCCInputs, compute_il_ieee519, format_pcc_summary
from pq_engine.analysis.topology_compare import compare_ups_topologies


def print_table(rows, top_n=12):
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
    rows = rows[:top_n]
    widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    header = " | ".join(c.ljust(widths[c]) for c in cols)
    print(header)
    print("-" * len(header))
    for r in rows:
        line = " | ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols)
        print(line)


def plot_overlays(rows, top_n=4, max_h=50):
    hs = list(range(2, max_h + 1))
    plt.figure()
    for r in rows[:top_n]:
        sp = r["spectrum_pct_of_fund"]
        y = [sp.get(h, 0.0) for h in hs]
        plt.plot(hs, y, label=r["name"])
    plt.xlabel("Harmonic order (h)")
    plt.ylabel("Ih (% of fundamental RMS)")
    plt.title(f"Harmonic spectrum overlay (top {top_n} scenarios)")
    plt.grid(True)
    plt.legend()
    plt.show()


def main():
    # Operating condition (affects harmonic spectrum magnitude model)
    load_pu = 0.60

    # IEEE-519 IL is based on max-demand point at PCC
    pcc = PCCInputs(
        vll_v=415.0,
        kw_demand=1000.0,   # kW (IT/output) at max demand
        pf_disp=0.99,
        efficiency=0.96,
        kw_is_output=True,
    )
    IL = compute_il_ieee519(pcc)

    # PCC stiffness (Isc/IL)
    Isc_over_IL = 35.0

    print(format_pcc_summary(pcc, load_pu))

    results = compare_ups_topologies(
        load_pu=load_pu,
        il_a=IL,
        isc_over_il=Isc_over_IL,
        topology_keys=["6pulse_typical", "12pulse_typical", "18pulse_typical", "afe_low_harm"],
        filters=["none", "tuned_5_7", "broadband_passive", "active_filter_like"],
        per_topology_filter_map={
            "afe_low_harm": ["none"],  # realism: AFE usually doesn't need extra filtering
        },
    )

    print(f"\nPCC case: load={load_pu:.2f} pu, IL={IL:.2f} A, Isc/IL={Isc_over_IL:.1f}\n")
    print_table(results, top_n=12)

    best = results[0]
    print("\nTop recommendation (practical ranking):")
    print(f"- {best['name']}")
    print(f"  TDD {best['tdd_percent']}% (limit {best['tdd_limit_percent']}%), risk {best['risk_level']}")
    print(f"  strict_pass={best['strict_pass']} practical_pass={best['practical_pass']} severity={best['severity_score']}")

    if best["major_violations"]:
        print("  Major violations remain (practical mode):")
        for v in best["major_violations"][:3]:
            print(f"   - h{v['h']} over by {v['over_pct']}%")
    elif best["minor_violations"]:
        print("  Only minor high-order exceedances remain (practical mode).")

    plot_overlays(results, top_n=4, max_h=50)


if __name__ == "__main__":
    main()
