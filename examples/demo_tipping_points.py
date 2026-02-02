"""
Demo: Find tipping points (minimum PCC short-circuit MVA required) for each option.

We compute two thresholds separately:
- Voltage tipping point: first SC MVA where THDv <= limit
- Current tipping point: first SC MVA where IEEE-519 practical current pass is True

This mirrors real PQ practice:
- Voltage distortion depends strongly on PCC strength (short-circuit MVA).
- IEEE-519 current limits also depend on Isc/IL, so strength matters there too.

Notes:
- We treat "practical_pass" from topology_compare as the current-compliance criterion.
- You can optionally exclude options (e.g., AFE) if you want "next-best without AFE".
"""

from pq_engine.analysis.pcc_sizing import PCCInputs, compute_il_ieee519
from pq_engine.analysis.topology_compare import compare_ups_topologies


def find_tipping_points_for_option(
    option_name: str,
    load_pu: float,
    il_a: float,
    vll_v: float,
    sc_mva_grid,
    thdv_limit: float,
    z_freq_exp: float,
    topology_keys,
    filters,
    per_topology_filter_map,
):
    """
    Returns (min_sc_mva_voltage, min_sc_mva_current) for the best-matching result row by name prefix.
    """
    min_v = None
    min_i = None

    for sc_mva in sc_mva_grid:
        results = compare_ups_topologies(
            load_pu=load_pu,
            il_a=il_a,
            vll_v=vll_v,
            sc_mva=sc_mva,
            topology_keys=topology_keys,
            filters=filters,
            per_topology_filter_map=per_topology_filter_map,
            thdv_limit_percent=thdv_limit,
            z_freq_exp=z_freq_exp,
        )

        # Find the row for this specific option (exact match preferred; fallback prefix match)
        row = None
        for r in results:
            if r["name"] == option_name:
                row = r
                break
        if row is None:
            for r in results:
                if r["name"].startswith(option_name):
                    row = r
                    break
        if row is None:
            raise KeyError(f"Option '{option_name}' not found in results at sc_mva={sc_mva}. Check name/key mapping.")

        if min_v is None and row["thdv_pass"]:
            min_v = sc_mva
        if min_i is None and row["practical_pass"]:
            min_i = sc_mva

        if (min_v is not None) and (min_i is not None):
            break

    return min_v, min_i


def main():
    # ---------- Study configuration ----------
    load_pu = 0.60

    # IEEE-519 IL sizing basis (max-demand)
    pcc = PCCInputs(
        vll_v=415.0,
        kw_demand=1000.0,
        pf_disp=0.99,
        efficiency=0.96,
        kw_is_output=True,
    )
    IL = compute_il_ieee519(pcc)

    # Sweep grid for tipping points
    # Coarse grid first; later we can add refinement search if needed.
    sc_mva_grid = [10, 15, 20, 25, 30, 35, 40, 50, 60, 75, 100, 150, 250, 500]

    # THDv model knobs
    thdv_limit = 5.0
    z_freq_exp = 1.0  # inductive-like scaling

    # Options (names must match the scenario naming produced by compare_ups_topologies)
    topology_keys = ["6pulse_typical", "12pulse_typical", "18pulse_typical", "afe_low_harm"]
    filters = ["none", "tuned_5_7", "broadband_passive", "active_filter_like"]
    per_topology_filter_map = {"afe_low_harm": ["none"]}

    # Build a list of option names we want tipping points for.
    # We generate them in the same style as compare_ups_topologies naming.
    options = [
        "AFE (low low-order harmonics) (no filter)",
        "18-pulse (typical) (no filter)",
        "12-pulse (typical) (no filter)",
        "6-pulse (typical) (no filter)",
        "18-pulse (typical) + active_filter_like",
        "12-pulse (typical) + active_filter_like",
        "6-pulse (typical) + active_filter_like",
        "18-pulse (typical) + broadband_passive",
        "12-pulse (typical) + broadband_passive",
        "6-pulse (typical) + broadband_passive",
        "18-pulse (typical) + tuned_5_7",
        "12-pulse (typical) + tuned_5_7",
        "6-pulse (typical) + tuned_5_7",
    ]

    print("\nTipping points (minimum PCC short-circuit MVA required)\n")
    print(f"Assumptions: load={load_pu:.2f} pu, IL={IL:.2f} A, VLL={pcc.vll_v:.1f} V, THDv limit={thdv_limit:.1f}%, Z~h^{z_freq_exp}\n")

    header = "option".ljust(48) + " | min_SC_MVA_for_THDv".ljust(22) + " | min_SC_MVA_for_current(practical)"
    print(header)
    print("-" * len(header))

    for opt in options:
        mv, mi = find_tipping_points_for_option(
            option_name=opt,
            load_pu=load_pu,
            il_a=IL,
            vll_v=pcc.vll_v,
            sc_mva_grid=sc_mva_grid,
            thdv_limit=thdv_limit,
            z_freq_exp=z_freq_exp,
            topology_keys=topology_keys,
            filters=filters,
            per_topology_filter_map=per_topology_filter_map,
        )

        mv_s = f"{mv:.1f} MVA" if mv is not None else "never (in grid)"
        mi_s = f"{mi:.1f} MVA" if mi is not None else "never (in grid)"

        print(opt.ljust(48) + " | " + mv_s.ljust(22) + " | " + mi_s)

    print("\nNotes:")
    print("- If an option says 'never (in grid)', expand sc_mva_grid upward or check limits/assumptions.")
    print("- Voltage tipping point is usually much more sensitive to PCC strength than current, especially for 6-pulse.")
    print("- This table is what you put in an interconnect report to justify AFE vs filters.\n")


if __name__ == "__main__":
    main()
