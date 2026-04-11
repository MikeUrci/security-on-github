"""Deterministic valuation helpers.

Every number that lands in the generated pitch book must come from this
module or from the raw data files. pitch.py hands the resulting factbook
to the model and instructs it to refuse to invent figures.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import pandas as pd


@dataclass
class MethodResult:
    method: str
    low: float
    mid: float
    high: float
    notes: str


def _latest_year(d: dict) -> str:
    return sorted(d.keys())[-1]


def filter_comps(comps: pd.DataFrame, target: dict) -> pd.DataFrame:
    """Keep peers within 0.4x–3.0x the target's LTM revenue."""
    ltm_rev = target["historicals"][_latest_year(target["historicals"])]["revenue"]
    lo, hi = ltm_rev * 0.4, ltm_rev * 3.0
    return comps[(comps["revenue_ltm"] >= lo) & (comps["revenue_ltm"] <= hi)].reset_index(drop=True)


def filter_precedents(precedents: pd.DataFrame, target: dict) -> pd.DataFrame:
    """Keep deals in a size range relevant to the target (1x–12x LTM revenue)."""
    ltm_rev = target["historicals"][_latest_year(target["historicals"])]["revenue"]
    lo, hi = ltm_rev * 1.0, ltm_rev * 12.0
    return precedents[
        (precedents["deal_value_usd_m"] >= lo) & (precedents["deal_value_usd_m"] <= hi)
    ].reset_index(drop=True)


def run_dcf(target: dict, wacc: float = 0.10, terminal_growth: float = 0.03,
            tax_rate: float = 0.25) -> MethodResult:
    proj = target["projections"]
    years = sorted(proj.keys())
    ufcf = []
    for y in years:
        p = proj[y]
        ufcf.append(p["ebitda"] * (1 - tax_rate) - p["capex"] - p["change_in_working_capital"])

    def ev(w: float, g: float) -> float:
        pv = sum(f / (1 + w) ** (i + 1) for i, f in enumerate(ufcf))
        tv = (ufcf[-1] * (1 + g)) / (w - g)
        pv += tv / (1 + w) ** len(ufcf)
        return pv

    mid = ev(wacc, terminal_growth)
    low = ev(wacc + 0.01, terminal_growth - 0.005)
    high = ev(wacc - 0.01, terminal_growth + 0.005)

    return MethodResult(
        method="Discounted Cash Flow",
        low=low, mid=mid, high=high,
        notes=(f"WACC {wacc * 100:.1f}% (+/-100 bps), terminal growth "
               f"{terminal_growth * 100:.1f}% (+/-50 bps), tax rate "
               f"{tax_rate * 100:.0f}%, 3-year explicit forecast"),
    )


def dcf_sensitivity(target: dict, tax_rate: float = 0.25) -> dict:
    proj = target["projections"]
    years = sorted(proj.keys())
    ufcf = [
        proj[y]["ebitda"] * (1 - tax_rate) - proj[y]["capex"] - proj[y]["change_in_working_capital"]
        for y in years
    ]
    waccs = [0.08, 0.09, 0.10, 0.11, 0.12]
    gs = [0.020, 0.025, 0.030, 0.035, 0.040]
    matrix = []
    for w in waccs:
        row = []
        for g in gs:
            pv = sum(f / (1 + w) ** (i + 1) for i, f in enumerate(ufcf))
            tv = (ufcf[-1] * (1 + g)) / (w - g)
            pv += tv / (1 + w) ** len(ufcf)
            row.append(round(pv))
        matrix.append(row)
    return {"waccs": waccs, "terminal_growths": gs, "ev_matrix": matrix}


def comps_valuation(target: dict, comps: pd.DataFrame) -> tuple[MethodResult, MethodResult]:
    ltm_rev = target["historicals"][_latest_year(target["historicals"])]["revenue"]
    ltm_ebitda = target["historicals"][_latest_year(target["historicals"])]["ebitda"]

    rev_q = comps["ev_revenue"].quantile([0.25, 0.5, 0.75])
    eb_q = comps["ev_ebitda"].quantile([0.25, 0.5, 0.75])

    rev_result = MethodResult(
        method="Trading Comparables — EV/Revenue",
        low=rev_q[0.25] * ltm_rev,
        mid=rev_q[0.5] * ltm_rev,
        high=rev_q[0.75] * ltm_rev,
        notes=(f"Filtered to {len(comps)} peers. Multiples 25th/50th/75th: "
               f"{rev_q[0.25]:.1f}x / {rev_q[0.5]:.1f}x / {rev_q[0.75]:.1f}x "
               f"applied to LTM revenue of ${ltm_rev:,.0f}m"),
    )
    eb_result = MethodResult(
        method="Trading Comparables — EV/EBITDA",
        low=eb_q[0.25] * ltm_ebitda,
        mid=eb_q[0.5] * ltm_ebitda,
        high=eb_q[0.75] * ltm_ebitda,
        notes=(f"Filtered to {len(comps)} peers. Multiples 25th/50th/75th: "
               f"{eb_q[0.25]:.1f}x / {eb_q[0.5]:.1f}x / {eb_q[0.75]:.1f}x "
               f"applied to LTM EBITDA of ${ltm_ebitda:,.0f}m"),
    )
    return rev_result, eb_result


def precedents_valuation(target: dict, precs: pd.DataFrame) -> tuple[MethodResult, MethodResult]:
    ltm_rev = target["historicals"][_latest_year(target["historicals"])]["revenue"]
    ltm_ebitda = target["historicals"][_latest_year(target["historicals"])]["ebitda"]

    rev_q = precs["ev_revenue_multiple"].quantile([0.25, 0.5, 0.75])
    eb_q = precs["ev_ebitda_multiple"].quantile([0.25, 0.5, 0.75])

    rev_result = MethodResult(
        method="Precedent Transactions — EV/Revenue",
        low=rev_q[0.25] * ltm_rev,
        mid=rev_q[0.5] * ltm_rev,
        high=rev_q[0.75] * ltm_rev,
        notes=(f"Filtered to {len(precs)} transactions. Multiples 25th/50th/75th: "
               f"{rev_q[0.25]:.1f}x / {rev_q[0.5]:.1f}x / {rev_q[0.75]:.1f}x "
               f"target revenue"),
    )
    eb_result = MethodResult(
        method="Precedent Transactions — EV/EBITDA",
        low=eb_q[0.25] * ltm_ebitda,
        mid=eb_q[0.5] * ltm_ebitda,
        high=eb_q[0.75] * ltm_ebitda,
        notes=(f"Filtered to {len(precs)} transactions. Multiples 25th/50th/75th: "
               f"{eb_q[0.25]:.1f}x / {eb_q[0.5]:.1f}x / {eb_q[0.75]:.1f}x "
               f"target EBITDA"),
    )
    return rev_result, eb_result


def build_football_field(results: list[MethodResult]) -> str:
    lo = min(r.low for r in results) * 0.9
    hi = max(r.high for r in results) * 1.05
    width = 50

    def col(v: float) -> int:
        return max(0, min(width, int(round((v - lo) / (hi - lo) * width))))

    lines: list[str] = []
    lines.append("Enterprise Value Range (USD millions)")
    left = f"${lo:,.0f}m"
    right = f"${hi:,.0f}m"
    pad = max(1, width + 2 - len(left) - len(right))
    lines.append("Scale:  " + left + " " * pad + right)
    axis = "        +" + "-" * width + "+"
    lines.append(axis)
    for r in results:
        bar = [" "] * (width + 1)
        l, m, h = col(r.low), col(r.mid), col(r.high)
        for i in range(l, h + 1):
            bar[i] = "-"
        bar[l] = "|"
        bar[h] = "|"
        bar[m] = "*"
        bar_str = "        |" + "".join(bar[:width]) + "|"
        lines.append(bar_str + f"  {r.method}")
        lines.append(
            "        |" + " " * width + "|"
            + f"    range ${r.low:,.0f}m – ${r.high:,.0f}m  (mid ${r.mid:,.0f}m)"
        )
    lines.append(axis)
    lines.append("Legend:  | = range bound    * = midpoint")
    return "\n".join(lines)


def build_factbook(target: dict, comps: pd.DataFrame, precedents: pd.DataFrame,
                   wacc: float = 0.10, terminal_growth: float = 0.03) -> dict:
    f_comps = filter_comps(comps, target)
    f_precs = filter_precedents(precedents, target)

    dcf = run_dcf(target, wacc=wacc, terminal_growth=terminal_growth)
    comps_rev, comps_eb = comps_valuation(target, f_comps)
    prec_rev, prec_eb = precedents_valuation(target, f_precs)

    results = [dcf, comps_rev, comps_eb, prec_rev, prec_eb]
    football = build_football_field(results)
    sensitivity = dcf_sensitivity(target)

    latest = _latest_year(target["historicals"])
    return {
        "target_ltm_revenue": target["historicals"][latest]["revenue"],
        "target_ltm_ebitda": target["historicals"][latest]["ebitda"],
        "methods": [asdict(r) for r in results],
        "filtered_comps": f_comps.to_dict(orient="records"),
        "filtered_precedents": f_precs.to_dict(orient="records"),
        "dcf_sensitivity": sensitivity,
        "football_field_ascii": football,
        "assumptions": {
            "wacc": wacc,
            "terminal_growth": terminal_growth,
            "tax_rate": 0.25,
        },
    }


def _md_table(rows: list[dict]) -> str:
    if not rows:
        return "_(no rows after filtering)_"
    headers = list(rows[0].keys())
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
    return "\n".join(out)


def format_factbook_for_prompt(fb: dict) -> str:
    lines: list[str] = []
    lines.append("## FACTBOOK — pre-computed, authoritative")
    lines.append(f"Target LTM Revenue: ${fb['target_ltm_revenue']:,.1f}m")
    lines.append(f"Target LTM EBITDA:  ${fb['target_ltm_ebitda']:,.1f}m")
    a = fb["assumptions"]
    lines.append(
        f"Assumptions: WACC {a['wacc'] * 100:.1f}%, terminal growth "
        f"{a['terminal_growth'] * 100:.1f}%, tax rate {a['tax_rate'] * 100:.0f}%"
    )
    lines.append("")
    lines.append("### Methods")
    for m in fb["methods"]:
        lines.append(
            f"- **{m['method']}** — low ${m['low']:,.0f}m | mid "
            f"${m['mid']:,.0f}m | high ${m['high']:,.0f}m"
        )
        lines.append(f"  _{m['notes']}_")
    lines.append("")
    lines.append("### Football Field (reproduce this verbatim inside a fenced code block)")
    lines.append("```")
    lines.append(fb["football_field_ascii"])
    lines.append("```")
    lines.append("")
    lines.append("### Filtered Trading Comparables")
    lines.append(_md_table(fb["filtered_comps"]))
    lines.append("")
    lines.append("### Filtered Precedent Transactions")
    lines.append(_md_table(fb["filtered_precedents"]))
    lines.append("")
    lines.append("### DCF Sensitivity (Enterprise Value, $m)")
    s = fb["dcf_sensitivity"]
    header = "| WACC \\\\ g | " + " | ".join(f"{g * 100:.1f}%" for g in s["terminal_growths"]) + " |"
    sep = "| --- | " + " | ".join("---" for _ in s["terminal_growths"]) + " |"
    lines.append(header)
    lines.append(sep)
    for w, row in zip(s["waccs"], s["ev_matrix"]):
        lines.append(
            f"| {w * 100:.0f}% | "
            + " | ".join(f"${v:,}m" for v in row) + " |"
        )
    return "\n".join(lines)
