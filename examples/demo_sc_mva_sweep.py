"""
Demo: Sweep PCC short-circuit strength (SC MVA) and see how recommendations change.

This mimics real interconnect study reasoning:
- Strong PCC -> voltage distortion low and IEEE-519 current limits looser
- Weak PCC -> THDv rises and current limits tighten -> mitigation/topology needed
"""

from pq_engine.analysis.pcc_sizing import PCCInputs, compute_il_ieee519
from pq_engine.analysis.source_impedance import isc_over_il_from_sc_mva
from pq_engine.analysis.topology_compare import compare_ups_topologies


def main():
    load_pu = 0.60

    pcc = PCCInputs(
        vll_v=415.0,
        kw_demand=1000.0,
        pf_disp=0.99,
        efficiency=0.96,
        kw_is_output=True,
    )
    IL = compute_il_ieee519(pcc)

    sc_mva_points = [20.0, 35.0, 50.0, 75.0, 100.0, 150.0, 250.0, 500.0]

    print("\nSC MVA sweep (best option per PCC strength)\n")
    header = (
        "Ssc_MVA | Isc/IL | best_option"
        + " " * 22
        + "| THDv% | Vpass | TDD% | TDDlim | Ipass(prac) | riskV | riskI"
    )
    print(header)
    print("-" * len(header))

    for sc_mva in sc_mva_points:
        isc_over_il = isc_over_il_from_sc_mva(pcc.vll_v, sc_mva, IL)

        results = compare_ups_topologies(
            load_pu=load_pu,
            il_a=IL,
            vll_v=pcc.vll_v,
            sc_mva=sc_mva,
            topology_keys=["6pulse_typical", "12pulse_typical", "18pulse_typical", "afe_low_harm"],
            filters=["none", "tuned_5_7", "broadband_passive", "active_filter_like"],
            per_topology_filter_map={"afe_low_harm": ["none"]},
            thdv_limit_percent=5.0,
            z_freq_exp=1.0,
        )

        best = results[0]

        line = (
            f"{sc_mva:7.1f} | "
            f"{isc_over_il:6.1f} | "
            f"{best['name'][:35].ljust(35)} | "
            f"{best['thdv_percent']:5.2f} | "
            f"{str(best['thdv_pass']):5} | "
            f"{best['tdd_percent']:5.2f} | "
            f"{best['tdd_limit_percent']:6.2f} | "
            f"{str(best['practical_pass']):11} | "
            f"{best['risk_level_voltage']:<5} | "
            f"{best['risk_level_current']:<5}"
        )
        print(line)

    print("\nTip: focus on 20–50 MVA rows to see weak-PCC effects.\n")


if __name__ == "__main__":
    main()
