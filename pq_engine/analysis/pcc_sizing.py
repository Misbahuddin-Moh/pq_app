"""
PCC sizing utilities for IEEE-519-style analysis.

Key idea:
- IEEE-519 current distortion limits are referenced to IL, the *maximum demand
  fundamental current at the PCC* (typically 15/30-min demand).
- In data centers, you often know max-demand kW (or a planning demand level),
  service voltage (VLL), and expected displacement PF and efficiency.

We compute:
- I1 (fundamental RMS current) = P_in / (sqrt(3)*VLL*PF)
- where P_in = P_out / efficiency if your kW is IT load output.
"""

from __future__ import annotations
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PCCInputs:
    vll_v: float          # line-to-line voltage (V)
    kw_demand: float      # kW at max demand point (see kw_is_output)
    pf_disp: float        # displacement PF at fundamental (0..1)
    efficiency: float     # efficiency at that demand point (0..1)
    phases: int = 3       # assume 3-phase

    # If kw_demand is IT/output kW, set True (common in data center planning).
    # If kw_demand is already input kW at the PCC, set False.
    kw_is_output: bool = True


def _sqrt3() -> float:
    return 1.7320508075688772


def input_kw_from_output_kw(output_kw: float, efficiency: float) -> float:
    """Convert output kW (IT load) to input kW at PCC using efficiency."""
    if efficiency <= 0.0 or efficiency > 1.0:
        raise ValueError("efficiency must be in (0, 1].")
    return float(output_kw) / float(efficiency)


def fundamental_current_a(
    vll_v: float,
    kw: float,
    pf_disp: float,
    phases: int = 3,
) -> float:
    """
    Fundamental RMS line current for a balanced 3-phase system:
      I1 = P / (sqrt(3)*VLL*PF)
    where P is real power in W.

    Note:
    - This is *fundamental* current estimate (ignores harmonic heating).
    - PF here is displacement PF at the fundamental (not true PF including distortion).
    """
    if phases != 3:
        raise ValueError("Only 3-phase supported in this tool version.")
    if vll_v <= 0:
        raise ValueError("vll_v must be > 0.")
    if pf_disp <= 0 or pf_disp > 1.0:
        raise ValueError("pf_disp must be in (0, 1].")
    p_w = float(kw) * 1000.0
    return p_w / (_sqrt3() * float(vll_v) * float(pf_disp))


def compute_il_ieee519(pcc: PCCInputs) -> float:
    """
    Compute IL as maximum demand fundamental current at PCC.

    If kw_demand is output kW (IT load), we convert to input kW using efficiency.
    """
    kw_in = input_kw_from_output_kw(pcc.kw_demand, pcc.efficiency) if pcc.kw_is_output else float(pcc.kw_demand)
    return fundamental_current_a(pcc.vll_v, kw_in, pcc.pf_disp, phases=pcc.phases)


def compute_operating_i1(pcc: PCCInputs, load_pu: float) -> float:
    """
    Fundamental current at operating load fraction relative to the demand point.
    For quick screening we assume linear scaling of kW with load_pu.
    """
    if load_pu < 0:
        raise ValueError("load_pu must be >= 0.")
    kw_oper = float(pcc.kw_demand) * float(load_pu)
    pcc_oper = PCCInputs(
        vll_v=pcc.vll_v,
        kw_demand=kw_oper,
        pf_disp=pcc.pf_disp,
        efficiency=pcc.efficiency,
        phases=pcc.phases,
        kw_is_output=pcc.kw_is_output,
    )
    return compute_il_ieee519(pcc_oper)


def format_pcc_summary(pcc: PCCInputs, load_pu: float) -> str:
    il = compute_il_ieee519(pcc)
    i1_op = compute_operating_i1(pcc, load_pu)
    kw_in_demand = input_kw_from_output_kw(pcc.kw_demand, pcc.efficiency) if pcc.kw_is_output else float(pcc.kw_demand)
    return (
        "PCC sizing summary:\n"
        f"- VLL: {pcc.vll_v:.1f} V\n"
        f"- Demand kW ({'output' if pcc.kw_is_output else 'input'}): {pcc.kw_demand:.2f} kW\n"
        f"- Demand kW (input @ PCC): {kw_in_demand:.2f} kW\n"
        f"- PF (displacement): {pcc.pf_disp:.3f}\n"
        f"- Efficiency: {pcc.efficiency:.3f}\n"
        f"- IL (IEEE-519 max-demand fundamental): {il:.2f} A\n"
        f"- Operating I1 @ load {load_pu:.2f} pu: {i1_op:.2f} A\n"
    )
