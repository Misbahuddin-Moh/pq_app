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
- Presentation polish (11C):
    * If it passes at the first tested SC MVA, show "<= min grid"
    * If it never passes in tested range, show "> max grid"
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
    Returns (min_sc_mva_voltage, min_sc_mva_current) for the best-matching result row by name.

    Voltage criterion: row["thdv_pass"] == True
    Current criterion: row["practical_pass"] == True
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

        # Find the specific option row by exact name first, then prefix match
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
            raise KeyError(
                f"Option '{option_name}' not found in results at sc_mva={sc_mva}. "
                f"Check naming in options list vs compare_ups_topologies() output."
            )

        if min_v is None and row["thdv_pass"]:
            min_v = sc_mva
        if min_i is None and row["practical_pass"]:
            min_i = sc_mva

        if (min_v is not None) and (min_i is not None):
            break

    return min_v, min_i


def fmt_bound(value, sc_mva_grid):
    """
    Presentation-only formatting:
    - None => > max tested
    - == min tested => <= min tested
    - else => numeric value
    """
    min_grid = sc_mva_grid[0]
    max_grid = sc_mva_grid[-1]
    if value is None:
        return f"> {max_grid:.0f} MVA"
    if value == min_grid:
        return f"<= {min_grid:.0f} MVA"
    return f"{value:.1f} MVA"


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

    # Sweep grid for tipping points (coarse grid; expand if needed)
    sc_mva_grid = [10, 15, 20, 25, 30, 35, 40, 50, 60, 75, 100, 150, 250, 500]

    # THDv model knobs
    thdv_limit = 5.0
    z_freq_exp = 1.0  # impedance magnitude ~ h^exp (1.0 ~ inductive-like)

    topology_keys = ["6pulse_typical", "12pulse_typical", "18pulse_typical", "afe_low_harm"]
    filters = ["none", "tuned_5_7", "broadband_passive", "active_filter_like"]
    per_topology_filter_map = {"afe_low_harm": ["none"]}

    # Option names must match compare_ups_topologies naming
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
    print(
        f"Assumptions: load={load_pu:.2f} pu, IL={IL:.2f} A, VLL={pcc.vll_v:.1f} V, "
        f"THDv limit={thdv_limit:.1f}%, |Z|~h^{z_freq_exp}\n"
    )

    header = (
        "option".ljust(48)
        + " | min_SC_MVA_for_THDv".ljust(22)
        + " | min_SC_MVA_for_current(practical)"
    )
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

        mv_s = fmt_bound(mv, sc_mva_grid)
        mi_s = fmt_bound(mi, sc_mva_grid)

        print(opt.ljust(48) + " | " + mv_s.ljust(22) + " | " + mi_s)

    print("\nNotes:")
    print(f"- '<= {sc_mva_grid[0]} MVA' means it already passes at the minimum tested PCC strength.")
    print(f"- '> {sc_mva_grid[-1]} MVA' means it did not pass within the tested range; expand the grid if needed.")
    print("- Voltage tipping point is usually more sensitive to PCC strength than current, especially for 6-pulse.")
    print("- Use this table to justify AFE vs filters during utility interconnect discussions.\n")


if __name__ == "__main__":
    main()
