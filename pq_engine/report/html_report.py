"""
HTML report generator for UPS Harmonics & Power Quality Analyzer.

- Produces a standalone HTML file.
- Writes plots as PNGs into the same output directory for portability.

Engine is frozen: this module is presentation-only.
"""

from __future__ import annotations

import os
import datetime as _dt
from typing import List, Dict, Optional

import matplotlib.pyplot as plt


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _escape(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _risk_badge(risk: str) -> str:
    r = (risk or "").upper()
    cls = "risk-low"
    if r == "MEDIUM":
        cls = "risk-med"
    elif r == "HIGH":
        cls = "risk-high"
    return f'<span class="badge {cls}">{_escape(r)}</span>'


def _ellipsize(s: str, max_len: int = 44) -> str:
    s = str(s)
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _table_html(headers: List[str], rows: List[List[str]]) -> str:
    th = "".join(f"<th>{_escape(h)}</th>" for h in headers)
    trs = []
    for row in rows:
        tds = "".join(f"<td>{cell}</td>" for cell in row)  # cells are already escaped or HTML
        trs.append(f"<tr>{tds}</tr>")
    return f"""
<table>
  <thead><tr>{th}</tr></thead>
  <tbody>
    {''.join(trs)}
  </tbody>
</table>
""".strip()


def _write_png_spectrum_overlay(
    results: List[dict],
    out_dir: str,
    filename: str = "spectrum_overlay.png",
    top_n: int = 4,
    max_h: int = 50,
) -> str:
    _ensure_dir(out_dir)
    hs = list(range(2, max_h + 1))
    plt.figure()
    for r in results[:top_n]:
        sp = r.get("spectrum_pct_of_fund", {})
        y = [sp.get(h, 0.0) for h in hs]
        plt.plot(hs, y, label=r.get("name", "scenario"))
    plt.xlabel("Harmonic order (h)")
    plt.ylabel("Ih (% of fundamental RMS)")
    plt.title(f"Harmonic spectrum overlay (top {top_n} scenarios)")
    plt.grid(True)
    plt.legend()
    path = os.path.join(out_dir, filename)
    plt.savefig(path, dpi=160, bbox_inches="tight")
    plt.close()
    return filename


def _write_png_thdv_sweep(
    sweep_rows: List[dict],
    out_dir: str,
    filename: str = "thdv_vs_sc_mva.png",
) -> Optional[str]:
    if not sweep_rows:
        return None
    _ensure_dir(out_dir)
    xs = [r["sc_mva"] for r in sweep_rows]
    ys = [r["thdv_percent"] for r in sweep_rows]

    plt.figure()
    plt.plot(xs, ys)
    plt.xlabel("PCC short-circuit strength Ssc (MVA)")
    plt.ylabel("THDv (%)")
    plt.title("Voltage distortion sensitivity (THDv vs Ssc)")
    plt.grid(True)
    path = os.path.join(out_dir, filename)
    plt.savefig(path, dpi=160, bbox_inches="tight")
    plt.close()
    return filename


def generate_html_report(
    *,
    out_dir: str,
    report_name: str,
    inputs_block: Dict[str, str],
    best: dict,
    top_results: List[dict],
    tipping_rows: List[List[str]],
    sweep_rows: Optional[List[dict]] = None,
) -> str:
    _ensure_dir(out_dir)

    spectrum_png = _write_png_spectrum_overlay(top_results, out_dir, top_n=min(4, len(top_results)))
    thdv_png = _write_png_thdv_sweep(sweep_rows or [], out_dir) if sweep_rows is not None else None

    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Build "key takeaways" bullets (presentation-only, derived from already computed fields)
    takeaways = []
    takeaways.append(
        f"Recommended option <b>{_escape(best.get('name',''))}</b> "
        f"at Ssc={_escape(inputs_block.get('PCC strength (Ssc)',''))}."
    )
    takeaways.append(
        f"Voltage distortion: THDv={_escape(best.get('thdv_percent',''))}% "
        f"(limit {_escape(best.get('thdv_limit_percent',''))}%) → "
        f"{'PASS' if best.get('thdv_pass') else 'FAIL'}."
    )
    takeaways.append(
        f"Current distortion: TDD={_escape(best.get('tdd_percent',''))}% "
        f"(limit {_escape(best.get('tdd_limit_percent',''))}%) → "
        f"{'PASS' if best.get('practical_pass') else 'FAIL (practical)'}."
    )
    takeaways.append(
        f"PCC category: Isc/IL={_escape(best.get('isc_over_il',''))} → "
        f"IEEE-519 TDD limit shown above."
    )
    # Highlight common “gotcha” from tipping points: if any option shows >500 MVA for current
    for row in tipping_rows:
        opt, _, cur = row
        if "> 500" in cur and "no filter" in opt.lower():
            takeaways.append(
                "Several non-AFE options do not achieve practical current pass within the tested PCC range "
                "(often due to low-order harmonic limits), even if THDv can pass."
            )
            break

    takeaways_html = "<ul>" + "".join(f"<li>{t}</li>" for t in takeaways) + "</ul>"

    # Exec summary table rows (with risk badges)
    best_lines = [
        ("Recommended option", _escape(best.get("name", ""))),
        ("Voltage (THDv)", _escape(f"{best.get('thdv_percent','')}% (limit {best.get('thdv_limit_percent','')}%) pass={best.get('thdv_pass','')}")),
        ("Current (TDD)", _escape(f"{best.get('tdd_percent','')}% (limit {best.get('tdd_limit_percent','')}%) practical_pass={best.get('practical_pass','')}")),
        ("Risk (Voltage)", _risk_badge(best.get("risk_level_voltage", ""))),
        ("Risk (Current)", _risk_badge(best.get("risk_level_current", ""))),
        ("Isc/IL", _escape(best.get("isc_over_il", ""))),
        ("Worst harmonic", _escape(best.get("worst_harmonic", ""))),
    ]
    best_table = "<table><tbody>" + "".join(
        f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in best_lines
    ) + "</tbody></table>"

    # Inputs table
    inputs_rows = [[_escape(k), _escape(v)] for k, v in inputs_block.items()]
    inputs_table = _table_html(["Input", "Value"], [[f"{k}", f"{v}"] for k, v in inputs_rows])

    # Top scenarios table
    headers = [
        "Scenario",
        "THDv (%)",
        "V pass",
        "TDD (%)",
        "TDD limit",
        "I practical pass",
        "Risk V",
        "Risk I",
        "Worst h",
    ]
    rows = []
    for r in top_results[:12]:
        rows.append([
            f"<span title=\"{_escape(r.get('name',''))}\">{_escape(_ellipsize(r.get('name','')))}</span>",
            _escape(r.get("thdv_percent", "")),
            _escape(r.get("thdv_pass", "")),
            _escape(r.get("tdd_percent", "")),
            _escape(r.get("tdd_limit_percent", "")),
            _escape(r.get("practical_pass", "")),
            _risk_badge(r.get("risk_level_voltage", "")),
            _risk_badge(r.get("risk_level_current", "")),
            _escape(r.get("worst_harmonic", "")),
        ])
    top_table = _table_html(headers, rows)

    # Tipping points table
    tipping_headers = ["Option", "Min Ssc for THDv", "Min Ssc for Current (practical)"]
    tipping_rows_html = [[_escape(a), _escape(b), _escape(c)] for a, b, c in tipping_rows]
    tipping_table = _table_html(tipping_headers, tipping_rows_html)

    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{_escape(report_name)}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    margin: 24px;
    color: #111;
  }}
  h1, h2, h3 {{ margin: 0.2em 0; }}
  .muted {{ color: #555; }}
  .grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }}
  .card {{
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 14px 16px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
    font-size: 14px;
  }}
  th, td {{
    border-bottom: 1px solid #eee;
    padding: 8px 10px;
    text-align: left;
    vertical-align: top;
  }}
  th {{
    background: #fafafa;
    font-weight: 600;
    width: 34%;
  }}
  .badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
    border: 1px solid #ddd;
  }}
  .risk-low {{ background: #ecfdf5; border-color: #a7f3d0; }}
  .risk-med {{ background: #fffbeb; border-color: #fde68a; }}
  .risk-high {{ background: #fef2f2; border-color: #fecaca; }}
  .imgwrap {{ margin-top: 10px; }}
  img {{
    max-width: 100%;
    height: auto;
    border: 1px solid #eee;
    border-radius: 8px;
  }}
  .footer {{
    margin-top: 18px;
    font-size: 13px;
    color: #555;
  }}
  @media (max-width: 900px) {{
    .grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>

<h1>{_escape(report_name)}</h1>
<div class="muted">Generated: {now}</div>

<div class="grid" style="margin-top: 14px;">
  <div class="card">
    <h2>Executive Summary</h2>
    <p class="muted">
      Screening report estimating UPS-driven harmonic current distortion at the PCC (IEEE-519-style)
      and estimating PCC voltage distortion (THDv) from short-circuit strength (Ssc).
    </p>
    <h3>Key takeaways</h3>
    {takeaways_html}
    {best_table}
  </div>

  <div class="card">
    <h2>Inputs & Assumptions</h2>
    {inputs_table}
    <div class="footer">
      Notes:
      <ul>
        <li>THDv is estimated via Vh≈Ih·|Z(h)| using PCC short-circuit strength (Ssc) and |Z|~h^exp.</li>
        <li>IEEE-519 compliance is interpreted in a practical field-engineering sense; confirm with utility requirements and measurements.</li>
      </ul>
    </div>
  </div>
</div>

<div class="card" style="margin-top: 16px;">
  <h2>Top Scenarios (ranked)</h2>
  {top_table}
</div>

<div class="grid" style="margin-top: 16px;">
  <div class="card">
    <h2>Harmonic Spectrum Overlay</h2>
    <div class="imgwrap">
      <img src="{_escape(spectrum_png)}" alt="Spectrum overlay"/>
    </div>
  </div>

  <div class="card">
    <h2>Tipping Points (Minimum Ssc Required)</h2>
    <p class="muted">Minimum PCC short-circuit strength required to meet voltage and practical current criteria (based on tested grid points).</p>
    {tipping_table}
    {"<div class='imgwrap'><img src='"+_escape(thdv_png)+"' alt='THDv sweep'/></div>" if thdv_png else ""}
  </div>
</div>

<div class="footer">
  <b>Disclaimer:</b> This report is a screening analysis using representative harmonic presets and simplified impedance scaling.
  It does not replace detailed harmonic studies (e.g., PSCAD/ETAP) when required by the utility or for final design signoff.
</div>

</body>
</html>
"""

    report_path = os.path.join(out_dir, "report.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    return report_path
