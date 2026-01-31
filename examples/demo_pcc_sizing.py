"""
Demo: compute IEEE-519 IL from realistic data center inputs.

This is how we should feed IL into IEEE-519 checks:
- IL = max-demand fundamental current (not instantaneous operating current)
"""

from pq_engine.analysis.pcc_sizing import PCCInputs, format_pcc_summary


def main():
    # Example: 1 MW IT load at demand, 415V system, PF~0.99, UPS efficiency ~0.96
    pcc = PCCInputs(
        vll_v=415.0,
        kw_demand=1000.0,    # kW (IT/output) at max demand point
        pf_disp=0.99,
        efficiency=0.96,
        kw_is_output=True,
    )

    load_pu = 0.60
    print(format_pcc_summary(pcc, load_pu))


if __name__ == "__main__":
    main()
