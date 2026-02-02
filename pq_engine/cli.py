"""
CLI entrypoint for UPS Harmonics & Power Quality Analyzer (IEEE-519-oriented).

Engine is frozen: this module is orchestration + deterministic JSON packaging only.

Usage:
  python -m pq_engine.cli --config configs/sample.yaml --out outputs/

Outputs:
  - outputs/report.html (if enabled)
  - outputs/spectrum_overlay.png (if report enabled; produced by report generator)
  - outputs/thdv_vs_sc_mva.png (if sweep enabled; produced by report generator)
  - outputs/results.json (canonical result packet for UI)
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from pq_engine.analysis.pcc_sizing import PCCInputs, compute_il_ieee519
from pq_engine.analysis.topology_compare import compare_ups_topologies
from pq_engine.report.html_report import generate_html_report

SCHEMA_VERSION = "pq.v1"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _apply_defaults(cfg: Dict[str, Any]) -> Dict[str, Any]:
    defaults: Dict[str, Any] = {
        "site": {"vll_v": 415.0, "frequency_hz": 60.0},
        "load": {
            "demand_kw": 1000.0,
            "load_pu": 0.60,
            "pf_displacement": 0.99,
            "efficiency": 0.96,
            "kw_is_output": True,
        },
        "grid": {"sc_mva": 50.0, "z_exp": 1.0},
        "limits": {"thdv_limit_pct": 5.0},
        "scenario_space": {
            "topology_keys": ["6pulse_typical", "12pulse_typical", "18pulse_typical", "afe_low_harm"],
            "filters": ["none", "tuned_5_7", "broadband_passive", "active_filter_like"],
            "per_topology_filter_map": {"afe_low_harm": ["none"]},
        },
        "report": {"enabled": True, "report_name": "UPS Harmonics & Power Quality Screening Report"},
        "sweeps": {
            "thdv_vs_sc_mva": {
                "enabled": True,
                "points": [20.0, 35.0, 50.0, 75.0, 100.0, 150.0, 250.0, 500.0],
            },
            "tipping_points": {
                "enabled": True,
                "grid": [10, 15, 20, 25, 30, 35, 40, 50, 60, 75, 100, 150, 250, 500],
                "options": [
                    "AFE (low low-order harmonics) (no filter)",
                    "18-pulse (typical) (no filter)",
                    "12-pulse (typical) (no filter)",
                    "6-pulse (typical) (no filter)",
                    "18-pulse (typical) + active_filter_like",
                    "12-pulse (typical) + active_filter_like",
                    "6-pulse (typical) + active_filter_like",
                ],
            },
        },
        "tool": {"name": "ups-pq-analyzer", "version": "0.1.0", "commit": "11C", "engine_frozen": True},
    }
    return _deep_merge(defaults, cfg)


def _validate_cfg(cfg: Dict[str, Any]) -> None:
    def get(path: str) -> Any:
        cur: Any = cfg
        for key in path.split("."):
            if not isinstance(cur, dict) or key not in cur:
                raise ValueError(f"Missing required config key: {path}")
            cur = cur[key]
        return cur

    vll = float(get("site.vll_v"))
    if vll <= 0:
        raise ValueError("site.vll_v must be > 0")

    load_pu = float(get("load.load_pu"))
    if not (0.0 < load_pu <= 1.5):
        raise ValueError("load.load_pu must be in (0, 1.5]")

    pf = float(get("load.pf_displacement"))
    if not (0.0 < pf <= 1.0):
        raise ValueError("load.pf_displacement must be in (0, 1]")

    eff = float(get("load.efficiency"))
    if not (0.0 < eff <= 1.0):
        raise ValueError("load.efficiency must be in (0, 1]")

    sc_mva = float(get("grid.sc_mva"))
    if sc_mva <= 0:
        raise ValueError("grid.sc_mva must be > 0")

    z_exp = float(get("grid.z_exp"))
    if z_exp <= 0:
        raise ValueError("grid.z_exp must be > 0")

    thdv_lim = float(get("limits.thdv_limit_pct"))
    if thdv_lim <= 0:
        raise ValueError("limits.thdv_limit_pct must be > 0")

    tk = get("scenario_space.topology_keys")
    flt = get("scenario_space.filters")
    if not isinstance(tk, list) or not tk:
        raise ValueError("scenario_space.topology_keys must be a non-empty list")
    if not isinstance(flt, list) or not flt:
        raise ValueError("scenario_space.filters must be a non-empty list")


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("Config YAML must be a mapping (top-level dict).")
    return data


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=False), encoding="utf-8")


def _pick_row_by_name(results: List[Dict[str, Any]], option_name: str) -> Optional[Dict[str, Any]]:
    for r in results:
        if r.get("name") == option_name:
            return r
    for r in results:
        if str(r.get("name", "")).startswith(option_name):
            return r
    return None


def _run_thdv_sweep_for_option(
    *,
    load_pu: float,
    il_a: float,
    vll_v: float,
    option_name: str,
    sc_mva_points: List[float],
    topology_keys: List[str],
    filters: List[str],
    per_topology_filter_map: Dict[str, List[str]],
    thdv_limit: float,
    z_freq_exp: float,
) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    for sc_mva in sc_mva_points:
        results = compare_ups_topologies(
            load_pu=load_pu,
            il_a=il_a,
            vll_v=vll_v,
            sc_mva=float(sc_mva),
            topology_keys=topology_keys,
            filters=filters,
            per_topology_filter_map=per_topology_filter_map,
            thdv_limit_percent=thdv_limit,
            z_freq_exp=z_freq_exp,
        )
        row = _pick_row_by_name(results, option_name)
        if row is None:
            continue
        rows.append({"sc_mva": float(sc_mva), "thdv_percent": float(row.get("thdv_percent", 0.0))})
    return rows


def _run_tipping_points_table(
    *,
    load_pu: float,
    il_a: float,
    vll_v: float,
    sc_mva_grid: List[float],
    thdv_limit: float,
    z_freq_exp: float,
    topology_keys: List[str],
    filters: List[str],
    per_topology_filter_map: Dict[str, List[str]],
    options: List[str],
) -> List[List[str]]:
    from examples.demo_tipping_points import find_tipping_points_for_option, fmt_bound

    rows: List[List[str]] = []
    for opt in options:
        mv, mi = find_tipping_points_for_option(
            option_name=opt,
            load_pu=load_pu,
            il_a=il_a,
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


def _format_inputs_block(
    *,
    vll_v: float,
    demand_kw: float,
    pf_disp: float,
    efficiency: float,
    il_a: float,
    load_pu: float,
    sc_mva: float,
    thdv_limit: float,
    z_exp: float,
) -> Dict[str, str]:
    return {
        "VLL": f"{vll_v:.1f} V",
        "Demand (output)": f"{demand_kw:.2f} kW",
        "PF (disp)": f"{pf_disp:.3f}",
        "Efficiency": f"{efficiency:.3f}",
        "IL (IEEE-519)": f"{il_a:.2f} A",
        "Operating load": f"{load_pu:.2f} pu",
        "PCC strength (Ssc)": f"{sc_mva:.1f} MVA",
        "THDv limit": f"{thdv_limit:.1f}%",
        "Impedance scaling": f"|Z| ~ h^{z_exp:.1f}",
    }


def _build_key_takeaways(best: Dict[str, Any], inputs_block: Dict[str, str], tipping_rows: List[List[str]]) -> List[str]:
    takeaways: List[str] = []
    takeaways.append(
        f"Recommended option {best.get('name','')} at Ssc={inputs_block.get('PCC strength (Ssc)','')}."
    )
    takeaways.append(
        f"Voltage distortion: THDv={best.get('thdv_percent','')}% (limit {best.get('thdv_limit_percent','')}%) → "
        f"{'PASS' if best.get('thdv_pass') else 'FAIL'}."
    )
    takeaways.append(
        f"Current distortion: TDD={best.get('tdd_percent','')}% (limit {best.get('tdd_limit_percent','')}%) → "
        f"{'PASS' if best.get('practical_pass') else 'FAIL (practical)'}."
    )
    takeaways.append(
        f"PCC category: Isc/IL={best.get('isc_over_il','')} → IEEE-519 TDD limit shown above."
    )
    for row in tipping_rows:
        opt, _, cur = row
        if "> 500" in cur and "no filter" in opt.lower():
            takeaways.append(
                "Several non-AFE options do not achieve practical current pass within the tested PCC range "
                "(often due to low-order harmonic limits), even if THDv can pass."
            )
            break
    return takeaways


def _fmt_float(x: Any, nd: int = 2) -> Optional[float]:
    if x is None:
        return None
    try:
        return round(float(x), nd)
    except Exception:
        return None


def _build_top_scenarios_table(results: List[Dict[str, Any]], limit: int = 12) -> Dict[str, Any]:
    columns = ["Scenario", "THDv (%)", "V pass", "TDD (%)", "TDD limit", "I practical pass", "Risk V", "Risk I", "Worst h"]
    rows: List[List[Any]] = []
    for r in results[:limit]:
        rows.append(
            [
                r.get("name", ""),
                _fmt_float(r.get("thdv_percent"), 2),
                bool(r.get("thdv_pass")),
                _fmt_float(r.get("tdd_percent"), 2),
                _fmt_float(r.get("tdd_limit_percent"), 1),
                bool(r.get("practical_pass")),
                str(r.get("risk_level_voltage", "")).upper(),
                str(r.get("risk_level_current", "")).upper(),
                r.get("worst_harmonic", None),
            ]
        )
    return {"columns": columns, "rows": rows}


def _build_tipping_points_table(tipping_rows: List[List[str]]) -> Dict[str, Any]:
    columns = ["Option", "Min Ssc for THDv", "Min Ssc for Current (practical)"]
    return {"columns": columns, "rows": tipping_rows}


def _build_result_packet(
    *,
    cfg: Dict[str, Any],
    inputs_block: Dict[str, str],
    best: Dict[str, Any],
    top_results: List[Dict[str, Any]],
    tipping_rows: List[List[str]],
    sweep_rows: Optional[List[Dict[str, float]]],
    out_dir: str,
    report_enabled: bool,
) -> Dict[str, Any]:
    artifacts: Dict[str, Any] = {
        "report_html": str(Path(out_dir) / "report.html") if report_enabled else None,
        "plots": [],
        "raw": [{"name": "results_json", "path": str(Path(out_dir) / "results.json")}],
    }

    if report_enabled:
        artifacts["plots"].append({"name": "spectrum_overlay", "path": str(Path(out_dir) / "spectrum_overlay.png")})
        if sweep_rows is not None:
            artifacts["plots"].append({"name": "thdv_vs_sc_mva", "path": str(Path(out_dir) / "thdv_vs_sc_mva.png")})

    series: Dict[str, Any] = {}
    if sweep_rows is not None:
        series["thdv_vs_sc_mva"] = {
            "x_name": "PCC short-circuit strength Ssc (MVA)",
            "y_name": "THDv (%)",
            "points": [[float(r["sc_mva"]), float(r["thdv_percent"])] for r in sweep_rows],
        }

    packet = {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": _utc_now_iso(),
        "tool": {
            "name": cfg["tool"].get("name", "ups-pq-analyzer"),
            "version": cfg["tool"].get("version", "0.1.0"),
            "engine_frozen": bool(cfg["tool"].get("engine_frozen", True)),
            "commit": cfg["tool"].get("commit", "unknown"),
        },
        "report": {
            "title": cfg["report"].get("report_name", "UPS Harmonics & Power Quality Screening Report"),
            "generated_local": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        "executive_summary": {
            "intro": (
                "Screening report estimating UPS-driven harmonic current distortion at the PCC "
                "(IEEE-519-style) and estimating PCC voltage distortion (THDv) from short-circuit strength (Ssc)."
            ),
            "key_takeaways": _build_key_takeaways(best, inputs_block, tipping_rows),
            "recommended_option": best.get("name", ""),
            "voltage_thdv_percent": _fmt_float(best.get("thdv_percent"), 2),
            "voltage_thdv_limit_percent": _fmt_float(best.get("thdv_limit_percent"), 1),
            "voltage_pass": bool(best.get("thdv_pass")),
            "current_tdd_percent": _fmt_float(best.get("tdd_percent"), 2),
            "current_tdd_limit_percent": _fmt_float(best.get("tdd_limit_percent"), 1),
            "current_practical_pass": bool(best.get("practical_pass")),
            "risk_voltage": str(best.get("risk_level_voltage", "")).upper(),
            "risk_current": str(best.get("risk_level_current", "")).upper(),
            "isc_over_il": _fmt_float(best.get("isc_over_il"), 2),
            "worst_harmonic": best.get("worst_harmonic", None),
        },
        "inputs_assumptions": inputs_block,
        "tables": {
            "top_scenarios_ranked": _build_top_scenarios_table(top_results, limit=12),
            "tipping_points_min_ssc_required": _build_tipping_points_table(tipping_rows),
        },
        "series": series,
        "artifacts": artifacts,
        "disclaimer": (
            "This report is a screening analysis using representative harmonic presets and simplified impedance scaling. "
            "It does not replace detailed harmonic studies (e.g., PSCAD/ETAP) when required by the utility or for final design signoff."
        ),
    }
    return packet


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pq_engine.cli",
        description="UPS Harmonics & Power Quality Analyzer — CLI + results.json (mirrors report.html)",
    )
    parser.add_argument("--config", required=True, help="Path to YAML config (e.g., configs/sample.yaml)")
    parser.add_argument("--out", required=True, help="Output directory (e.g., outputs/)")
    parser.add_argument("--no-report", action="store_true", help="Disable HTML report generation")
    args = parser.parse_args(argv)

    cfg_path = Path(args.config)
    out_dir = str(Path(args.out))

    if not cfg_path.exists():
        print(f"Config not found: {cfg_path}")
        return 2

    os.makedirs(out_dir, exist_ok=True)

    try:
        cfg_raw = _load_yaml(cfg_path)
        cfg = _apply_defaults(cfg_raw)
        if args.no_report:
            cfg.setdefault("report", {})
            cfg["report"]["enabled"] = False
        _validate_cfg(cfg)
    except Exception as e:
        print(f"Config error: {e}")
        return 2

    site = cfg["site"]
    load = cfg["load"]
    grid = cfg["grid"]
    limits = cfg["limits"]
    space = cfg["scenario_space"]
    sweeps = cfg["sweeps"]
    report_cfg = cfg["report"]

    load_pu = float(load["load_pu"])

    pcc = PCCInputs(
        vll_v=float(site["vll_v"]),
        kw_demand=float(load["demand_kw"]),
        pf_disp=float(load["pf_displacement"]),
        efficiency=float(load["efficiency"]),
        kw_is_output=bool(load.get("kw_is_output", True)),
    )
    il_a = float(compute_il_ieee519(pcc))

    sc_mva = float(grid["sc_mva"])
    thdv_limit = float(limits["thdv_limit_pct"])
    z_exp = float(grid["z_exp"])

    topology_keys = list(space["topology_keys"])
    filters = list(space["filters"])
    per_topology_filter_map = dict(space.get("per_topology_filter_map", {}))

    top_results = compare_ups_topologies(
        load_pu=load_pu,
        il_a=il_a,
        vll_v=float(site["vll_v"]),
        sc_mva=sc_mva,
        topology_keys=topology_keys,
        filters=filters,
        per_topology_filter_map=per_topology_filter_map,
        thdv_limit_percent=thdv_limit,
        z_freq_exp=z_exp,
    )

    if not top_results:
        print("No results produced by compare_ups_topologies().")
        return 1

    best = top_results[0]

    tipping_rows: List[List[str]] = []
    if bool(sweeps.get("tipping_points", {}).get("enabled", True)):
        tip = sweeps["tipping_points"]
        tipping_rows = _run_tipping_points_table(
            load_pu=load_pu,
            il_a=il_a,
            vll_v=float(site["vll_v"]),
            sc_mva_grid=[float(x) for x in tip.get("grid", [])],
            thdv_limit=thdv_limit,
            z_freq_exp=z_exp,
            topology_keys=topology_keys,
            filters=filters,
            per_topology_filter_map=per_topology_filter_map,
            options=list(tip.get("options", [])),
        )

    sweep_rows: Optional[List[Dict[str, float]]] = None
    if bool(sweeps.get("thdv_vs_sc_mva", {}).get("enabled", True)):
        sw = sweeps["thdv_vs_sc_mva"]
        sweep_rows = _run_thdv_sweep_for_option(
            load_pu=load_pu,
            il_a=il_a,
            vll_v=float(site["vll_v"]),
            option_name=str(best.get("name", "")),
            sc_mva_points=[float(x) for x in sw.get("points", [])],
            topology_keys=topology_keys,
            filters=filters,
            per_topology_filter_map=per_topology_filter_map,
            thdv_limit=thdv_limit,
            z_freq_exp=z_exp,
        )

    inputs_block = _format_inputs_block(
        vll_v=float(site["vll_v"]),
        demand_kw=float(load["demand_kw"]),
        pf_disp=float(load["pf_displacement"]),
        efficiency=float(load["efficiency"]),
        il_a=il_a,
        load_pu=load_pu,
        sc_mva=sc_mva,
        thdv_limit=thdv_limit,
        z_exp=z_exp,
    )

    report_enabled = bool(report_cfg.get("enabled", True))
    if report_enabled:
        generate_html_report(
            out_dir=out_dir,
            report_name=str(report_cfg.get("report_name", "UPS Harmonics & Power Quality Screening Report")),
            inputs_block=inputs_block,
            best=best,
            top_results=top_results,
            tipping_rows=tipping_rows,
            sweep_rows=sweep_rows,
        )

    packet = _build_result_packet(
        cfg=cfg,
        inputs_block=inputs_block,
        best=best,
        top_results=top_results,
        tipping_rows=tipping_rows,
        sweep_rows=sweep_rows,
        out_dir=out_dir,
        report_enabled=report_enabled,
    )

    _write_json(Path(out_dir) / "results.json", packet)

    print(f"Wrote: {Path(out_dir) / 'results.json'}")
    if report_enabled:
        print(f"Wrote: {Path(out_dir) / 'report.html'}")
        print(f"Open with: open {Path(out_dir) / 'report.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
