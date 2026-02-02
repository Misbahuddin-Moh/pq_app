"""
Generate an HTML engineering-style report into outputs/report.html

Run:
  python -m examples.demo_generate_report
"""

import os

from pq_engine.analysis.pcc_sizing import PCCInputs, compute_il_ieee519
from pq_engine.analysis.topology_compare import compare_ups_topologies
from pq_engine.report.html_report import generate_html_report


def run_tipping_points_table(load_pu, IL, vll_v):
    # We reuse your tipping-points logic by importing the demo module functions.
    # Keeps engine frozen; report layer can call existing outputs.
    from examples.demo_tipping_points import find_tipping_points_for_option, fmt_bound

    sc_mva_grid = [10, 15, 20, 25, 30, 35, 40, 50, 60, 75, 100, 150, 250, 500]
    thdv_limit = 5.0
    z_freq_exp = 1.0

    topology_keys = ["6pulse_typical", "12pulse_typical", "18pulse_typical", "afe_low_harm"]
    filters = ["none", "tuned_5_7", "broadband_passive", "active_filter_like"]
    per_topology_filter_map = {"afe_low_harm": ["none"]}

    options = [
        "AFE (low low-order harmonics) (no filter)",
        "18-pulse (typical) (no filter)",
        "12-pulse (typical) (no filter)",
        "6-pulse (typical) (no filter)",
        "18-pulse (typical) + active_filter_like",
        "12-pulse (typical) + active_filter_like",
        "6-pulse (typical) + active_filter_like",
    ]

    rows = []
    for opt in options:
        mv, mi = find_tipping_points_for_option(
            option_name=opt,
            load_pu=load_pu,
            il_a=IL,
            vll_v=vll_v,
            sc_mva_grid=sc_mva_grid,
            thdv_limit=thdv_limit,
            z_freq_exp=z_freq_exp,
            topology_keys=topology_keys,
            filters=filters,
            per_topology_filter_map=per_topology_filter_map,
        )
        rows.append([opt, fmt_bound(mv, sc_mva_grid), fmt_bound(mi, sc_mva_grid)])
    return rows


def run_thdv_sweep_for_best(load_pu, IL, vll_v, option_name):
    # Sweep THDv vs Ssc for a single option by running compare for each sc_mva and grabbing that option row.
    sc_mva_points = [20.0, 35.0, 50.0, 75.0, 100.0, 150.0, 250.0, 500.0]
    rows = []
    for sc_mva in sc_mva_points:
        results = compare_ups_topologies(
            load_pu=load_pu,
            il_a=IL,
            vll_v=vll_v,
            sc_mva=sc_mva,
            topology_keys=["6pulse_typical", "12pulse_typical", "18pulse_typical", "afe_low_harm"],
            filters=["none", "tuned_5_7", "broadband_passive", "active_filter_like"],
            per_topology_filter_map={"afe_low_harm": ["none"]},
            thdv_limit_percent=5.0,
            z_freq_exp=1.0,
        )

        row = None
        for r in results:
            if r["name"] == option_name:
                row = r
                break
        if row is None:
            # fallback: prefix match
            for r in results:
                if r["name"].startswith(option_name):
                    row = r
                    break
        if row is None:
            continue

        rows.append({"sc_mva": sc_mva, "thdv_percent": row["thdv_percent"]})
    return rows


def main():
    out_dir = "outputs"
    os.makedirs(out_dir, exist_ok=True)

    load_pu = 0.60

    # PCC sizing basis
    pcc = PCCInputs(
        vll_v=415.0,
        kw_demand=1000.0,
        pf_disp=0.99,
        efficiency=0.96,
        kw_is_output=True,
    )
    IL = compute_il_ieee519(pcc)

    # Pick a PCC strength for the report case
    sc_mva = 50.0  # try 20, 35, 50, 150

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

    tipping_rows = run_tipping_points_table(load_pu, IL, pcc.vll_v)

    # For the plot, sweep THDv vs Ssc for the "best" option in this case
    sweep_rows = run_thdv_sweep_for_best(load_pu, IL, pcc.vll_v, best["name"])

    inputs_block = {
        "VLL": f"{pcc.vll_v:.1f} V",
        "Demand (output)": f"{pcc.kw_demand:.2f} kW",
        "PF (disp)": f"{pcc.pf_disp:.3f}",
        "Efficiency": f"{pcc.efficiency:.3f}",
        "IL (IEEE-519)": f"{IL:.2f} A",
        "Operating load": f"{load_pu:.2f} pu",
        "PCC strength (Ssc)": f"{sc_mva:.1f} MVA",
        "THDv limit": "5.0%",
        "Impedance scaling": "|Z| ~ h^1.0",
    }

    report_path = generate_html_report(
        out_dir=out_dir,
        report_name="UPS Harmonics & Power Quality Screening Report",
        inputs_block=inputs_block,
        best=best,
        top_results=results,
        tipping_rows=tipping_rows,
        sweep_rows=sweep_rows,
    )

    print(f"\nReport generated: {report_path}")
    print("Open it with:")
    print("  open outputs/report.html\n")


if __name__ == "__main__":
    main()
