"""
UPS topology comparison engine (data-center oriented)

Compares preset harmonic spectra across UPS input topologies:
- 6-pulse
- 12-pulse
- 18-pulse
- AFE (low low-order harmonics)

Optionally applies mitigation attenuation models (filters) to each topology spectrum.
Evaluates IEEE-519-style current limits at PCC (depends on Isc/IL).
Ranks scenarios using practical engineering criteria.

Returns UI-ready scenario dicts including spectrum for plotting.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pq_engine.models.ups_harmonics import harmonic_presets, load_adjust_spectrum
from pq_engine.analysis.mitigation import FILTER_LIBRARY, apply_attenuation, run_scenario


DEFAULT_TOPOLOGY_KEYS = [
    "6pulse_typical",
    "12pulse_typical",
    "18pulse_typical",
    "afe_low_harm",
]


def _split_major_minor(ieee_report):
    """
    Practical categorization:
    - low-order (<=13): always major if violating
    - high-order tiny exceedance: minor
    """
    major = []
    minor = []
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
    """
    Severity emphasizes low-order exceedances and large over-limits.
    Minor high-order exceedances contribute very little.
    """
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
    isc_over_il: float,
    topology_keys: Optional[List[str]] = None,
    filters: Optional[List[str]] = None,
    per_topology_filter_map: Optional[Dict[str, List[str]]] = None,
) -> List[dict]:
    """
    Compare UPS topologies at a given load and PCC stiffness.

    Args:
      load_pu: operating load fraction (0..1)
      il_a: IEEE-519 IL at PCC (max-demand fundamental current)
      isc_over_il: PCC short-circuit ratio
      topology_keys: list of preset keys from harmonic_presets()
      filters: list of filter keys from FILTER_LIBRARY
      per_topology_filter_map: optional override filters for specific topology preset keys

    Returns:
      Ranked list of UI-ready scenario dicts including spectrum.
    """
    presets = harmonic_presets()
    topology_keys = topology_keys or DEFAULT_TOPOLOGY_KEYS
    filters = filters or ["none", "tuned_5_7", "broadband_passive", "active_filter_like"]

    isc_a = float(isc_over_il) * float(il_a)

    scenarios = []

    for tkey in topology_keys:
        if tkey not in presets:
            raise KeyError(
                f"Preset '{tkey}' not found in harmonic_presets(). Available: {list(presets.keys())}"
            )

        profile = presets[tkey]
        base = load_adjust_spectrum(profile.harmonic_pct_of_fund_rms, load_pu, model="rectifier_like")

        # Always include raw topology (no mitigation)
        scenarios.append(run_scenario(f"{profile.name} (no filter)", base, il_a=il_a, isc_a=isc_a))

        # Apply optional filters
        f_list = filters
        if per_topology_filter_map and tkey in per_topology_filter_map:
            f_list = per_topology_filter_map[tkey]

        for fkey in f_list:
            if fkey == "none":
                continue
            if fkey not in FILTER_LIBRARY:
                raise KeyError(f"Unknown filter key '{fkey}'. Available: {list(FILTER_LIBRARY.keys())}")
            sp = apply_attenuation(base, FILTER_LIBRARY[fkey])
            scenarios.append(run_scenario(f"{profile.name} + {fkey}", sp, il_a=il_a, isc_a=isc_a))

    # Rank using practical-mode logic
    def rank_key(s):
        major, _minor = _split_major_minor(s.ieee519)
        tdd_fail = 0 if s.ieee519.tdd_pass else 1
        return (tdd_fail, len(major), _severity_score(s.ieee519), s.ieee519.tdd_percent, s.heating_proxy)

    scenarios_sorted = sorted(scenarios, key=rank_key)

    out: List[dict] = []
    for s in scenarios_sorted:
        worst = s.ieee519.worst_violations[0].h if s.ieee519.worst_violations else None
        strict_pass = bool(s.ieee519.tdd_pass and len(s.ieee519.worst_violations) == 0)

        major, minor = _split_major_minor(s.ieee519)
        practical_pass = bool(s.ieee519.tdd_pass and len(major) == 0)

        out.append({
            "name": s.name,
            "thd_i_percent": round(s.thd_i_percent, 2),
            "tdd_percent": round(s.ieee519.tdd_percent, 2),
            "tdd_limit_percent": round(s.ieee519.tdd_limit_percent, 2),
            "strict_pass": strict_pass,
            "practical_pass": practical_pass,
            "severity_score": round(_severity_score(s.ieee519), 3),
            "risk_level": s.ieee519.risk_level,
            "isc_over_il": round(s.ieee519.isc_over_il, 1),
            "worst_harmonic": worst,
            "irms_over_i1": round(s.irms_over_i1, 4),
            "heating_proxy": round(s.heating_proxy, 4),
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
            "interpretation": s.ieee519.interpretation,
            "spectrum_pct_of_fund": dict(sorted(s.spectrum_pct_of_fund.items())),
        })

    return out
