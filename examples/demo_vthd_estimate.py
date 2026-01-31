"""
Demo: estimate voltage THD at PCC from harmonic current spectrum and source impedance.

This is a screening-level VTHD estimate:
  Vh ≈ Ih * |Z(h)|, THDv computed relative to V1.
"""

from pq_engine.models.ups_harmonics import harmonic_presets, load_adjust_spectrum
from pq_engine.analysis.pcc_sizing import PCCInputs, compute_il_ieee519
from pq_engine.analysis.voltage_distortion import (
    SourceImpedanceModel,
    thdv_from_spectrum,
    vln_from_vll,
)


def main():
    # PCC sizing (IEEE-519 IL basis)
    pcc = PCCInputs(
        vll_v=415.0,
        kw_demand=1000.0,   # IT/output kW demand
        pf_disp=0.99,
        efficiency=0.96,
        kw_is_output=True,
    )
    IL = compute_il_ieee519(pcc)

    # Operating load affects typical harmonic spectrum magnitude assumptions
    load_pu = 0.60

    presets = harmonic_presets()
    profile = presets["6pulse_typical"]  # try "afe_low_harm" to compare
    spectrum = load_adjust_spectrum(profile.harmonic_pct_of_fund_rms, load_pu, model="rectifier_like")

    # Source impedance assumption (per-phase Thevenin magnitude at fundamental)
    # Choose a representative Z1. For strong PCC, Z1 is small; for weak PCC, Z1 is larger.
    # This is a knob you'll eventually derive from short-circuit data.
    src = SourceImpedanceModel(z1_ohm=0.010, xr=10.0, freq_exp=1.0)

    v1 = vln_from_vll(pcc.vll_v)  # use per-phase V1 consistent with per-phase impedance

    res = thdv_from_spectrum(
        harmonic_pct_of_fund=spectrum,
        i1_a=IL,
        v1_v=v1,
        src=src,
        max_h=50,
        voltage_limit_percent=5.0,
    )

    print(f"\nProfile: {profile.name} @ load {load_pu:.2f} pu")
    print(f"IL (IEEE-519 max-demand I1): {IL:.2f} A")
    print(f"Assumed source Z1: {src.z1_ohm:.4f} ohm, freq_exp={src.freq_exp:.2f}")
    print(f"V1 (VLN): {v1:.2f} V")
    print(f"Estimated THDv: {res.thdv_percent:.2f}% (limit {res.limit_percent:.2f}%) pass={res.pass_limit} risk={res.risk_level}")

    # Show top contributing harmonics by voltage magnitude
    top = sorted(res.vh_by_harmonic_v.items(), key=lambda kv: kv[1], reverse=True)[:8]
    print("Top Vh contributors (V RMS):")
    for h, vh in top:
        print(f"  h={h:>2}: {vh:.3f} V")

    print("\nInterpretation:")
    print(res.interpretation)


if __name__ == "__main__":
    main()
