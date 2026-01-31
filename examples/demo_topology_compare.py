"""
Demo: compare UPS topologies + mitigation at PCC with utility-style PCC strength input.

Inputs:
- Demand sizing for IL (IEEE-519 IL)
- PCC short-circuit MVA (utility input) for:
  - Isc/IL used in current limits
  - Zth used in THDv estimate

Outputs:
- ranked table including THDv
- overlay spectrum plot for top scenarios
"""

import matplotlib.pyplot as plt

from pq_engine.analysis.pcc_sizing import PCCInputs, compute_il_ieee519, format_pcc_summary
from pq_engine.analysis.topology_compare import compare_ups_topologies


def print_table(rows, top_n=12):
    cols = [
        "name",
        "thdv_percent",
        "thdv_limit_percent",
        "thdv_pass",
        "tdd_percent",
        "tdd_limit_percent",
        "practical_pass",
        "severity_score",
        "risk_level_voltage",
        "risk_level_current",
        "worst_harmonic",
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
    load_pu = 0.60

    # IEEE-519 IL sizing at PCC (max-demand point)
    pcc = PCCInputs(
        vll_v=415.0,
        kw_demand=1000.0,   # IT/output kW at demand
        pf_disp=0.99,
        efficiency=0.96,
        kw_is_output=True,
    )
    IL = compute_il_ieee519(pcc)

    # Utility-style PCC strength input
    # Try e.g. 50, 100, 250, 500 MVA to see how THDv changes.
    sc_mva = 150.0

    print(format_pcc_summary(pcc, load_pu))
    print(f"Utility PCC strength: Ssc = {sc_mva:.1f} MVA\n")

    results = compare_ups_topologies(
        load_pu=load_pu,
        il_a=IL,
        vll_v=pcc.vll_v,
        sc_mva=sc_mva,
        topology_keys=["6pulse_typical", "12pulse_typical", "18pulse_typical", "afe_low_harm"],
        filters=["none", "tuned_5_7", "broadband_passive", "active_filter_like"],
        per_topology_filter_map={
            "afe_low_harm": ["none"],  # realism: AFE typically doesn't need extra filtering
        },
        thdv_limit_percent=5.0,
        z_freq_exp=1.0,
    )

    print_table(results, top_n=12)

    best = results[0]
    print("\nTop recommendation (utility-real ranking: voltage -> current -> heating):")
    print(f"- {best['name']}")
    print(f"  THDv {best['thdv_percent']}% (limit {best['thdv_limit_percent']}%) pass={best['thdv_pass']} riskV={best['risk_level_voltage']}")
    print(f"  TDD  {best['tdd_percent']}% (limit {best['tdd_limit_percent']}%) practical_pass={best['practical_pass']} riskI={best['risk_level_current']}")
    print(f"  severity={best['severity_score']} Isc/IL={best['isc_over_il']}")

    plot_overlays(results, top_n=4, max_h=50)


if __name__ == "__main__":
    main()
