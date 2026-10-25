"""Number formatters and the templated key messages.

Every sentence is built by one small function from the metric frames, through the
formatters below, so the wording follows the numbers without hand-editing. A NaN
input raises ValueError rather than rendering "nan"."""
import math

import pandas as pd

from report.constants import CASE_ORDER, CASE_STUDY_NAME, REFERENCE_COST, SENSITIVITY_CASES


def _check(x, name="value") -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        raise ValueError(f"{name} is not a number: {x!r}")
    if math.isnan(v) or math.isinf(v):
        raise ValueError(f"{name} is not finite: {x!r}")
    return v


def fmt_people(x) -> str:
    """13,451,356 -> '13.5 million'; 982,070 -> '982,000' (nearest thousand above 100,000); 2,500 -> '2,500'."""
    v = _check(x, "people")
    if v >= 1e6:
        return f"{v / 1e6:.1f} million"
    if v >= 1e5:
        return f"{round(v, -3):,.0f}"
    return f"{v:,.0f}"


def fmt_musd(x) -> str:
    v = _check(x, "million USD")
    return f"{v:,.0f} million USD" if v >= 100 else f"{v:,.1f} million USD"


def fmt_usd(x) -> str:
    return f"{_check(x, 'USD'):,.0f} USD"


def fmt_pct(x, digits: int = 0) -> str:
    return f"{_check(x, 'share') * 100:.{digits}f}%"


def fmt_lcoe(x, digits: int = 2) -> str:
    return f"{_check(x, 'LCOE'):.{digits}f} USD/kWh"


def fmt_mw(x) -> str:
    v = _check(x, "MW")
    return f"{v:,.0f} MW" if v >= 10 else f"{v:.1f} MW"


def fmt_int(x) -> str:
    return f"{int(round(_check(x, 'count'))):,}"


def direction(delta, up: str = "increases", down: str = "decreases", flat: str = "leaves unchanged",
              tol: float = 0.005) -> str:
    d = _check(delta, "delta")
    if abs(d) <= tol:
        return flat
    return up if d > 0 else down


def name(case: str) -> str:
    return CASE_STUDY_NAME.get(case, case)


# ---------------------------------------------------------------------------
# Key messages
# ---------------------------------------------------------------------------
def _minmax(headlines: dict, key: str):
    items = [(c, _check(headlines[c][key], f"{c}.{key}")) for c in CASE_ORDER if c in headlines]
    lo = min(items, key=lambda t: t[1])
    hi = max(items, key=lambda t: t[1])
    return lo, hi


def km_investment_range(headlines: dict) -> dict:
    lo, hi = _minmax(headlines, "investment_musd_cum")
    people = headlines[hi[0]]["people_reached_cum"]
    return {"id": "km-investment",
            "text": (f"Reaching universal access by 2040 costs between {fmt_musd(lo[1])} ({name(lo[0])}) and "
                     f"{fmt_musd(hi[1])} ({name(hi[0])}) over 2025 to 2040, connecting about "
                     f"{fmt_people(people)} people in every demand case."),
            "source": "Table 4.1"}


def km_unserved_2030(headlines: dict) -> dict:
    ref = headlines.get("BU") or headlines[next(iter(headlines))]
    return {"id": "km-2030",
            "text": (f"The 2030 target of 70 percent access leaves {fmt_people(ref['unserved_2030'])} people to be "
                     f"connected between 2030 and 2040; investment in the second period "
                     f"({fmt_musd(ref['investment_musd_2040'])} in the bottom-up case) is about "
                     f"{ref['investment_musd_2040'] / ref['investment_musd_2030']:.1f} times the first "
                     f"({fmt_musd(ref['investment_musd_2030'])})."),
            "source": "Table 7.1"}


def km_tech_mix(headlines: dict) -> dict:
    lo_case = "TD_Low" if "TD_Low" in headlines else CASE_ORDER[0]
    hi_case = "TD_High" if "TD_High" in headlines else CASE_ORDER[-1]
    lo, hi = headlines[lo_case], headlines[hi_case]
    g_lo, g_hi = _minmax(headlines, "grid_share_2040")
    return {"id": "km-mix",
            "text": (f"The grid serves {fmt_pct(g_lo[1])} ({name(g_lo[0])}) to {fmt_pct(g_hi[1])} ({name(g_hi[0])}) "
                     f"of the 2040 population. Under low demand ({name(lo_case)}) stand-alone PV is the main "
                     f"off-grid option with {fmt_people(lo['sa_pv_people_2040'])} people against "
                     f"{fmt_people(lo['mg_pv_people_2040'])} on mini-grid PV; under high demand ({name(hi_case)}) "
                     f"mini-grid PV takes the lead with {fmt_people(hi['mg_pv_people_2040'])} people against "
                     f"{fmt_people(hi['sa_pv_people_2040'])}."),
            "source": "Figures 4.1 and 4.5, Table 5.4"}


def km_cost_per_connection(headlines: dict) -> dict:
    lo, hi = _minmax(headlines, "usd_per_new_connection")
    return {"id": "km-usd-per-connection",
            "text": (f"Capital cost per newly connected person ranges from {fmt_usd(lo[1])} ({name(lo[0])}) to "
                     f"{fmt_usd(hi[1])} ({name(hi[0])}), driven by the demand tier rather than by the technology "
                     f"mix."),
            "source": "Table 5.1"}


def km_people_per_musd(headlines: dict) -> dict:
    lo, hi = _minmax(headlines, "people_per_musd")
    return {"id": "km-people-per-musd",
            "text": (f"One million USD connects {fmt_int(lo[1])} people under {name(lo[0])} and {fmt_int(hi[1])} "
                     f"under {name(hi[0])}."),
            "source": "Table 5.2"}


def km_lcoe(headlines: dict) -> dict:
    lo, hi = _minmax(headlines, "lcoe_energy_w")
    ex_lo, ex_hi = _minmax(headlines, "lcoe_energy_w_excl_dens")
    return {"id": "km-lcoe",
            "text": (f"The energy-weighted delivered cost of electricity in 2040 is {fmt_lcoe(lo[1])} ({name(lo[0])}) "
                     f"to {fmt_lcoe(hi[1])} ({name(hi[0])}) over all served settlements, and "
                     f"{fmt_lcoe(ex_lo[1])} to {fmt_lcoe(ex_hi[1])} for the newly electrified settlements alone, "
                     f"because settlements already on the grid are costed at the {fmt_lcoe(REFERENCE_COST)} "
                     f"generation cost by construction."),
            "source": "Table 5.3"}


def km_grid_cost_sensitivity(sens: pd.DataFrame, case: str = "BU") -> dict:
    s = sens[sens["demand_case"] == case].set_index("grid_cost")
    hi_cost = float(s.index.max())
    ref = s.loc[REFERENCE_COST]
    hi = s.loc[hi_cost]
    inv_delta = (_check(hi["investment_musd_cum"]) - _check(ref["investment_musd_cum"])) / _check(ref["investment_musd_cum"])
    ext_delta = _check(hi["grid_ext_people"]) - _check(ref["grid_ext_people"])
    return {"id": "km-grid-cost",
            "text": (f"Raising the grid generation cost from {REFERENCE_COST} to {hi_cost} USD/kWh "
                     f"{direction(inv_delta, 'raises', 'lowers')} total investment by {abs(inv_delta) * 100:.0f}% in the "
                     f"{name(case)} case and moves {fmt_people(hi['switched_people'])} people to another technology, "
                     f"mostly from grid extension ({fmt_people(abs(ext_delta))} fewer people on grid extension) to "
                     f"mini-grid PV; grid extension is the quantity sensitive to the grid cost."),
            "source": "Figures 9.1 to 9.5, Tables 9.1 and 9.2"}


def km_demand_sensitivity(deltas: dict) -> dict:
    parts = []
    for variant, base in (("TD_Low_minus", "TD_Low"), ("TD_High_plus", "TD_High")):
        if variant in deltas:
            d = deltas[variant]
            parts.append(f"{name(variant)} against {name(base)} {direction(d['investment_musd_cum'] / 100, 'raises', 'lowers')} "
                         f"investment by {abs(_check(d['investment_musd_cum'])):.0f}% and "
                         f"{direction(d['lcoe_energy_w'] / 100, 'raises', 'lowers')} the delivered cost by "
                         f"{abs(_check(d['lcoe_energy_w'])):.0f}%")
    text = "; ".join(parts) if parts else "no demand variant was run"
    return {"id": "km-demand", "text": f"Demand tiers matter more than the grid cost: {text}.", "source": "Table 9.3"}


def km_hydro(hydro: dict, case: str = "BU") -> dict:
    h = hydro.get(case) or next(iter(hydro.values()))
    return {"id": "km-hydro",
            "text": (f"Hydro mini-grids are a niche within the 10 km viability rule: {fmt_int(h['sites'])} sites serve "
                     f"{fmt_int(h['settlements'])} settlements and {fmt_people(h['people'])} people with "
                     f"{fmt_mw(h['capacity_mw'])} in the {name(case)} case."),
            "source": "Table 6.1"}


def key_messages(headlines: dict, sens: pd.DataFrame, deltas: dict, hydro: dict) -> list:
    msgs = [km_investment_range(headlines), km_tech_mix(headlines), km_cost_per_connection(headlines),
            km_people_per_musd(headlines), km_lcoe(headlines), km_unserved_2030(headlines)]
    if sens is not None and len(sens):
        case = "BU" if (sens["demand_case"] == "BU").any() else SENSITIVITY_CASES[0]
        msgs.append(km_grid_cost_sensitivity(sens, case))
    if deltas:
        msgs.append(km_demand_sensitivity(deltas))
    if hydro:
        msgs.append(km_hydro(hydro))
    for m in msgs:
        if "nan" in m["text"].lower().split():
            raise ValueError(f"message {m['id']} contains nan")
    return msgs
