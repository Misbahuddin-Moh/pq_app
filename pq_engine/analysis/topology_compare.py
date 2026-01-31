"""
UPS topology comparison engine (data-center oriented)

Compares preset harmonic spectra across UPS input topologies and optional mitigation filters.
Evaluates:
- IEEE-519-style current distortion at PCC (TDD + individual harmonic limits, depends on Isc/IL)
- Estimated PCC voltage distortion THDv using short-circuit MVA (utility input) and impedance scaling

Ranking (utility-real, practical):
1) THDv pass/fail
2) TDD pass/fail
3) major current-limit violations count (practical)
4) severity score (low-order weighted exceedance)
5) heating proxy
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pq_engine.models.ups_harmonics import harmonic_presets, load_adjust_spectrum
from pq_engine.analysis.mitigation import FILTER_LIBRARY, apply_attenuation, run_scenario
from pq_engine.analysis.source_impedance import isc_over_il_from_sc_mva
from pq_engine.analysis.voltage_distortion import (
    source_from_sc_mva,
    thdv_from_spectrum,
    vln_from_vll,
)


DEFAULT_TOPOLOGY_KEYS = [
    "6pulse_typical",
    "12pulse_typical",
    "18pulse_typical",
    "afe_low_harm",
]


def _split_major_minor(ieee_report):
    major, minor = [], []
    for v in ieee_report.worst_violations:
        over = v.ih_percent_of_il - v.limit_percent_of_il
        if v.h <= 13:
            major.append(v)
        elif v.h >= 23 and over <= 1.0:
            minor.append(v)
        elif v.h >= 17 and over <= 0.5:
            minor.append(v)
        else:
            major.append(v)
    return major, minor


def _severity_score(ieee_report) -> float:
    sev = 0.0
    for v in ieee_report.worst_violations:
        over = max(0.0, v.ih_percent_of_il - v.limit_percent_of_il)
        if v.h <= 13:
            w = 5.0
        elif v.h <= 23:
            w = 2.0
        else:
            w = 1.0
        if (v.h >= 23 and over <= 1.0) or (v.h >= 17 and over <= 0.5):
            w *= 0.2
        sev += w * over
    return float(sev)


def compare_ups_topologies(
    load_pu: float,
    il_a: float,
    vll_v: float,
    sc_mva: float,
    topology_keys: Optional[List[str]] = None,
    filters: Optional[List[str]] = None,
    per_topology_filter_map: Optional[Dict[str, List[str]]] = None,
    thdv_limit_percent: float = 5.0,
    z_freq_exp: float = 1.0,
) -> List[dict]:
    """
    Compare UPS topologies at a given load and PCC strength.

    Inputs:
      il_a: IEEE-519 IL at PCC (max-demand fundamental current)
      vll_v, sc_mva: utility-style PCC short-circuit strength for THDv estimation
      z_freq_exp: impedance scaling exponent (0..1 typical), default 1.0 inductive-like
    """
    presets = harmonic_presets()
    topology_keys = topology_keys or DEFAULT_TOPOLOGY_KEYS
    filters = filters or ["none", "tuned_5_7", "broadband_passive", "active_filter_like"]

    # derive Isc/IL from SC MVA (keeps current checks consistent with the same PCC strength input)
    isc_over_il = isc_over_il_from_sc_mva(vll_v, sc_mva, il_a)

    # source model for voltage distortion
    src = source_from_sc_mva(vll_v=vll_v, sc_mva=sc_mva, freq_exp=z_freq_exp)
    v1 = vln_from_vll(vll_v)

    scenarios = []

    for tkey in topology_keys:
        if tkey not in presets:
            raise KeyError(
                f"Preset '{tkey}' not found in harmonic_presets(). Available: {list(presets.keys())}"
            )

        profile = presets[tkey]
        base = load_adjust_spectrum(profile.harmonic_pct_of_fund_rms, load_pu, model="rectifier_like")

        scenarios.append(run_scenario(f"{profile.name} (no filter)", base, il_a=il_a, isc_a=isc_over_il * il_a))

        f_list = filters
        if per_topology_filter_map and tkey in per_topology_filter_map:
            f_list = per_topology_filter_map[tkey]

        for fkey in f_list:
            if fkey == "none":
                continue
            if fkey not in FILTER_LIBRARY:
                raise KeyError(f"Unknown filter key '{fkey}'. Available: {list(FILTER_LIBRARY.keys())}")
            sp = apply_attenuation(base, FILTER_LIBRARY[fkey])
            scenarios.append(run_scenario(f"{profile.name} + {fkey}", sp, il_a=il_a, isc_a=isc_over_il * il_a))

    # Precompute THDv for ranking and output
    enriched = []
    for s in scenarios:
        vres = thdv_from_spectrum(
            harmonic_pct_of_fund=s.spectrum_pct_of_fund,
            i1_a=il_a,
            v1_v=v1,
            src=src,
            max_h=50,
            voltage_limit_percent=thdv_limit_percent,
        )
        enriched.append((s, vres))

    def rank_key(pair):
        s, vres = pair
        major, _minor = _split_major_minor(s.ieee519)
        # priority: voltage compliance first
        v_fail = 0 if vres.pass_limit else 1
        # then current compliance
        tdd_fail = 0 if s.ieee519.tdd_pass else 1
        return (
            v_fail,
            tdd_fail,
            len(major),
            _severity_score(s.ieee519),
            vres.thdv_percent,
            s.heating_proxy,
        )

    enriched_sorted = sorted(enriched, key=rank_key)

    out: List[dict] = []
    for s, vres in enriched_sorted:
        worst = s.ieee519.worst_violations[0].h if s.ieee519.worst_violations else None
        strict_pass = bool(s.ieee519.tdd_pass and len(s.ieee519.worst_violations) == 0)

        major, minor = _split_major_minor(s.ieee519)
        practical_pass = bool(s.ieee519.tdd_pass and len(major) == 0)

        out.append({
            "name": s.name,

            # current distortion
            "thd_i_percent": round(s.thd_i_percent, 2),
            "tdd_percent": round(s.ieee519.tdd_percent, 2),
            "tdd_limit_percent": round(s.ieee519.tdd_limit_percent, 2),
            "strict_pass": strict_pass,
            "practical_pass": practical_pass,
            "severity_score": round(_severity_score(s.ieee519), 3),
            "risk_level_current": s.ieee519.risk_level,
            "isc_over_il": round(isc_over_il, 1),
            "worst_harmonic": worst,
            "heating_proxy": round(s.heating_proxy, 4),

            # voltage distortion
            "thdv_percent": round(vres.thdv_percent, 2),
            "thdv_limit_percent": round(vres.limit_percent, 2),
            "thdv_pass": bool(vres.pass_limit),
            "risk_level_voltage": vres.risk_level,

            # details
            "top_violations": [
                {"h": v.h, "ih_pct": round(v.ih_percent_of_il, 2), "limit_pct": round(v.limit_percent_of_il, 2)}
                for v in s.ieee519.worst_violations
            ],
            "major_violations": [
                {"h": v.h, "over_pct": round((v.ih_percent_of_il - v.limit_percent_of_il), 2)}
                for v in major
            ],
            "minor_violations": [
                {"h": v.h, "over_pct": round((v.ih_percent_of_il - v.limit_percent_of_il), 2)}
                for v in minor
            ],
            "interpretation_current": s.ieee519.interpretation,
            "interpretation_voltage": vres.interpretation,

            # spectrum for plotting/inspection
            "spectrum_pct_of_fund": dict(sorted(s.spectrum_pct_of_fund.items())),
        })

    return out
