"""Every number in the report comes from a function in this module.

All functions are pure and take the compact per-settlement frame produced by
report.data (columns of report.constants.RESULT_COLUMNS). Definitions follow the
plan's "Metric definitions" section:

- served rows in year y: FinalElecCode_y < 99 and NewConnections_y > 0
- population by technology counts every row carrying the code (unserved rows too)
- new connections, capacity (MW) and investment (million USD) count served rows only
- cumulative = 2030 + 2040
- LCOE statistics drop rows with MinimumOverallLCOE_y >= 99 and, for 2030, code 99
- "excluding densification" restricts to ElecStart == 0
"""
import numpy as np
import pandas as pd

from report.constants import (CASE_ORDER, COST_LEVELS, GRID_CODES, OFFGRID_CODES, REFERENCE_COST,
                              SERVED_CODES, TECH_CATEGORY, YEARS)

TOTAL = "Total"
TOTAL_EXCL = "Total excl. densification"


def served_mask(df: pd.DataFrame, year: int) -> pd.Series:
    return (df[f"FinalElecCode{year}"] < 99) & (df[f"NewConnections{year}"] > 0)


def lcoe_mask(df: pd.DataFrame, year: int, exclude_densification: bool = False) -> pd.Series:
    m = served_mask(df, year) & (df[f"MinimumOverallLCOE{year}"] < 99)
    if exclude_densification:
        m &= df["ElecStart"] == 0
    return m


# ---------------------------------------------------------------------------
# Technology tables
# ---------------------------------------------------------------------------
def tech_table(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Per technology code: settlements, population, new_connections, capacity_mw,
    investment_musd, energy_gwh. Code 99 appears when present (2030)."""
    code = df[f"FinalElecCode{year}"]
    served = served_mask(df, year)
    codes = list(SERVED_CODES) + ([99] if (code == 99).any() else [])
    rows = {}
    for c in codes:
        sel = code == c
        ss = sel & served
        rows[c] = {
            "settlements": int(sel.sum()),
            "population": float(df.loc[sel, f"Pop{year}"].sum()),
            "new_connections": float(df.loc[ss, f"NewConnections{year}"].sum()),
            "capacity_mw": float(df.loc[ss, f"NewCapacity{year}"].sum()) / 1000.0,
            "investment_musd": float(df.loc[ss, f"InvestmentCost{year}"].sum()) / 1e6,
            "energy_gwh": float(df.loc[ss, f"EnergyPerSettlement{year}"].sum()) / 1e6,
        }
    out = pd.DataFrame.from_dict(rows, orient="index")
    out.index.name = "code"
    return out


def cumulative_table(df: pd.DataFrame) -> pd.DataFrame:
    """Per served code plus Total: new_connections_cum, capacity_mw_cum, investment_musd_cum,
    energy_gwh_cum over 2030 and 2040."""
    parts = [tech_table(df, y).reindex(SERVED_CODES).fillna(0.0) for y in YEARS]
    cum = sum(parts)[["new_connections", "capacity_mw", "investment_musd", "energy_gwh"]]
    cum.columns = [f"{c}_cum" for c in cum.columns]
    cum.loc[TOTAL] = cum.sum()
    return cum


def _households(df: pd.DataFrame, mask: pd.Series, year: int) -> float:
    return float((df.loc[mask, f"NewConnections{year}"] / df.loc[mask, "NumPeoplePerHH"]).sum())


def weighted_lcoe(df: pd.DataFrame, year: int, weight: str = "energy",
                  exclude_densification: bool = False, mask=None) -> float:
    """Weighted delivered LCOE (USD/kWh) of the chosen technology over served rows.
    weight in {"energy", "population", "new_connections"}."""
    m = lcoe_mask(df, year, exclude_densification)
    if mask is not None:
        m &= mask
    col = {"energy": f"EnergyPerSettlement{year}", "population": f"Pop{year}",
           "new_connections": f"NewConnections{year}"}[weight]
    w = df.loc[m, col].astype(float)
    if w.sum() <= 0:
        return float("nan")
    return float((df.loc[m, f"MinimumOverallLCOE{year}"] * w).sum() / w.sum())


def lcoe_by_tech(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Per code: energy-weighted, population-weighted, median, p10, p90 LCOE."""
    m = lcoe_mask(df, year)
    code = df[f"FinalElecCode{year}"]
    rows = {}
    for c in SERVED_CODES:
        sel = m & (code == c)
        if not sel.any():
            continue
        l = df.loc[sel, f"MinimumOverallLCOE{year}"]
        rows[c] = {"lcoe_energy_w": weighted_lcoe(df, year, "energy", mask=(code == c)),
                   "lcoe_pop_w": weighted_lcoe(df, year, "population", mask=(code == c)),
                   "median": float(l.median()), "p10": float(l.quantile(0.1)), "p90": float(l.quantile(0.9)),
                   "settlements": int(sel.sum())}
    out = pd.DataFrame.from_dict(rows, orient="index")
    out.index.name = "code"
    return out


def consultancy_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Rows: served codes, Total, Total excl. densification. Columns: usd_per_new_connection,
    usd_per_household, people_per_musd, lcoe_energy_w, lcoe_pop_w, population_2040,
    share_pop_2040, new_connections_cum, investment_musd_cum."""
    code40 = df["FinalElecCode2040"]
    total_pop = float(df["Pop2040"].sum())
    rows = {}

    def block(sel_code, sel_rows, name):
        nc = inv = hh = 0.0
        for y in YEARS:
            sm = served_mask(df, y) & sel_rows
            if sel_code is not None:
                sm &= df[f"FinalElecCode{y}"] == sel_code
            nc += float(df.loc[sm, f"NewConnections{y}"].sum())
            inv += float(df.loc[sm, f"InvestmentCost{y}"].sum()) / 1e6
            hh += _households(df, sm, y)
        pop_sel = sel_rows & ((code40 == sel_code) if sel_code is not None else (code40 < 99))
        pop = float(df.loc[pop_sel, "Pop2040"].sum())
        m40 = sel_rows & ((code40 == sel_code) if sel_code is not None else True)
        rows[name] = {
            "usd_per_new_connection": inv * 1e6 / nc if nc else float("nan"),
            "usd_per_household": inv * 1e6 / hh if hh else float("nan"),
            "people_per_musd": nc / inv if inv else float("nan"),
            "lcoe_energy_w": weighted_lcoe(df, 2040, "energy", mask=m40),
            "lcoe_pop_w": weighted_lcoe(df, 2040, "population", mask=m40),
            "population_2040": pop,
            "share_pop_2040": pop / total_pop if total_pop else float("nan"),
            "new_connections_cum": nc,
            "investment_musd_cum": inv,
        }

    all_rows = pd.Series(True, index=df.index)
    for c in SERVED_CODES:
        block(c, all_rows, c)
    block(None, all_rows, TOTAL)
    block(None, df["ElecStart"] == 0, TOTAL_EXCL)
    out = pd.DataFrame.from_dict(rows, orient="index")
    out.index.name = "technology"
    return out


def headline(df: pd.DataFrame) -> dict:
    """Scalars for the headline table and the key messages."""
    cum = cumulative_table(df)
    cm = consultancy_metrics(df)
    shares = category_shares(df, 2040)
    return {
        "population_2040": float(df["Pop2040"].sum()),
        "population_2030": float(df["Pop2030"].sum()),
        "unserved_2030": float(df.loc[df["FinalElecCode2030"] == 99, "Pop2030"].sum()),
        "people_reached_cum": float(cum.loc[TOTAL, "new_connections_cum"]),
        "investment_musd_cum": float(cum.loc[TOTAL, "investment_musd_cum"]),
        "investment_musd_2030": float(tech_table(df, 2030).reindex(SERVED_CODES)["investment_musd"].sum()),
        "investment_musd_2040": float(tech_table(df, 2040).reindex(SERVED_CODES)["investment_musd"].sum()),
        "capacity_mw_cum": float(cum.loc[TOTAL, "capacity_mw_cum"]),
        "usd_per_new_connection": float(cm.loc[TOTAL, "usd_per_new_connection"]),
        "people_per_musd": float(cm.loc[TOTAL, "people_per_musd"]),
        "lcoe_energy_w": float(cm.loc[TOTAL, "lcoe_energy_w"]),
        "lcoe_pop_w": float(cm.loc[TOTAL, "lcoe_pop_w"]),
        "lcoe_energy_w_excl_dens": float(cm.loc[TOTAL_EXCL, "lcoe_energy_w"]),
        "grid_share_2040": float(shares.get("Grid", 0.0)),
        "offgrid_share_2040": float(shares.get("Mini-grid", 0.0) + shares.get("Stand-alone", 0.0)),
        "sa_pv_people_2040": float(df.loc[df["FinalElecCode2040"] == 3, "Pop2040"].sum()),
        "mg_pv_people_2040": float(df.loc[df["FinalElecCode2040"] == 5, "Pop2040"].sum()),
        "mg_hydro_people_2040": float(df.loc[df["FinalElecCode2040"] == 7, "Pop2040"].sum()),
        "grid_ext_people_2040": float(df.loc[df["FinalElecCode2040"] == 2, "Pop2040"].sum()),
        "grid_ext_settlements_2040": int((df["FinalElecCode2040"] == 2).sum()),
    }


def category_shares(df: pd.DataFrame, year: int, newly_electrified_only: bool = False) -> pd.Series:
    """Population shares of Grid, Mini-grid, Stand-alone (and None when present)."""
    sel = (df["ElecStart"] == 0) if newly_electrified_only else pd.Series(True, index=df.index)
    cat = df.loc[sel, f"FinalElecCode{year}"].map(TECH_CATEGORY)
    pop = df.loc[sel, f"Pop{year}"].groupby(cat).sum()
    return pop / pop.sum() if pop.sum() else pop


def region_table(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Per Admin_1: settlements, population, grid_share, offgrid_share, new_connections_cum,
    investment_musd_cum, usd_per_new_connection."""
    code = df[f"FinalElecCode{year}"]
    rows = {}
    for region, g in df.groupby(df["Admin_1"].astype(str), observed=True):
        c = code.loc[g.index]
        pop = float(g[f"Pop{year}"].sum())
        nc = inv = 0.0
        for y in YEARS:
            sm = served_mask(g, y)
            nc += float(g.loc[sm, f"NewConnections{y}"].sum())
            inv += float(g.loc[sm, f"InvestmentCost{y}"].sum()) / 1e6
        rows[region] = {
            "settlements": int(len(g)), "population": pop,
            "grid_share": float(g.loc[c.isin(GRID_CODES), f"Pop{year}"].sum()) / pop if pop else float("nan"),
            "offgrid_share": float(g.loc[c.isin(OFFGRID_CODES), f"Pop{year}"].sum()) / pop if pop else float("nan"),
            "new_connections_cum": nc, "investment_musd_cum": inv,
            "usd_per_new_connection": inv * 1e6 / nc if nc else float("nan"),
        }
    out = pd.DataFrame.from_dict(rows, orient="index")
    out.index.name = "region"
    return out.sort_values("population", ascending=False)


def urban_rural_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for name, sel in (("Urban", df["IsUrban"] == 2), ("Rural", df["IsUrban"] != 2)):
        g = df[sel]
        nc = inv = 0.0
        for y in YEARS:
            sm = served_mask(g, y)
            nc += float(g.loc[sm, f"NewConnections{y}"].sum())
            inv += float(g.loc[sm, f"InvestmentCost{y}"].sum()) / 1e6
        rows[name] = {"settlements": int(len(g)), "population_2040": float(g["Pop2040"].sum()),
                      "new_connections_cum": nc, "investment_musd_cum": inv,
                      "usd_per_new_connection": inv * 1e6 / nc if nc else float("nan"),
                      "lcoe_energy_w": weighted_lcoe(df, 2040, "energy", mask=sel),
                      "grid_share_2040": float(category_shares(g, 2040).get("Grid", 0.0))}
    out = pd.DataFrame.from_dict(rows, orient="index")
    out.index.name = "area"
    return out


def hydro_table(df: pd.DataFrame, year: int = 2040) -> dict:
    sel = (df[f"FinalElecCode{year}"] == 7) & served_mask(df, year)
    g = df[sel]
    return {"sites": int(g["HydropowerFID"].nunique()), "settlements": int(len(g)),
            "people": float(g[f"Pop{year}"].sum()),
            "capacity_mw": float(g[f"NewCapacity{year}"].sum()) / 1000.0,
            "investment_musd": float(g[f"InvestmentCost{year}"].sum()) / 1e6,
            "mean_dist_km": float(g["HydropowerDist"].mean()) if len(g) else float("nan")}


def start_year_table(df: pd.DataFrame) -> pd.DataFrame:
    """Start-year electrification by region plus Total: settlements, electrified_settlements,
    pop_start, electrified_pop_start, access_rate_start, urban_pop_start."""
    rows = {}
    groups = list(df.groupby(df["Admin_1"].astype(str), observed=True)) + [(TOTAL, df)]
    for region, g in groups:
        pop = float(g["PopStartYear"].sum())
        el = float(g.loc[g["ElecStart"] == 1, "PopStartYear"].sum())
        rows[region] = {"settlements": int(len(g)), "electrified_settlements": int((g["ElecStart"] == 1).sum()),
                        "pop_start": pop, "electrified_pop_start": el,
                        "access_rate_start": el / pop if pop else float("nan"),
                        "urban_pop_start": float(g.loc[g["IsUrban"] == 2, "PopStartYear"].sum())}
    out = pd.DataFrame.from_dict(rows, orient="index")
    out.index.name = "region"
    return out


def phasing_table(df: pd.DataFrame) -> pd.DataFrame:
    """Multi-index (period, region, code) over served rows: new_connections, capacity_mw,
    investment_musd, settlements."""
    parts = []
    for y in YEARS:
        sm = served_mask(df, y)
        g = df[sm]
        t = g.groupby([g["Admin_1"].astype(str), g[f"FinalElecCode{y}"].astype(int)], observed=True).agg(
            new_connections=(f"NewConnections{y}", "sum"), capacity_kw=(f"NewCapacity{y}", "sum"),
            investment_usd=(f"InvestmentCost{y}", "sum"), settlements=("id", "size"))
        t["capacity_mw"] = t["capacity_kw"] / 1000.0
        t["investment_musd"] = t["investment_usd"] / 1e6
        t = t.drop(columns=["capacity_kw", "investment_usd"])
        t.index = pd.MultiIndex.from_tuples([(y, r, c) for r, c in t.index], names=["period", "region", "code"])
        parts.append(t)
    return pd.concat(parts)


def lcoe_histogram(df: pd.DataFrame, year: int, bins=None) -> pd.DataFrame:
    """Population-weighted histogram of the delivered LCOE over served rows."""
    if bins is None:
        bins = np.arange(0.0, 0.605, 0.005)
    m = lcoe_mask(df, year)
    counts, edges = np.histogram(df.loc[m, f"MinimumOverallLCOE{year}"], bins=bins, weights=df.loc[m, f"Pop{year}"])
    return pd.DataFrame({"bin_left": edges[:-1], "bin_right": edges[1:], "people": counts})


def switches(df_ref: pd.DataFrame, df_alt: pd.DataFrame, year: int = 2040):
    """Settlements whose technology differs between two scenarios (joined on id).
    Returns (flows frame: from_code, to_code, settlements, people; totals dict)."""
    a = df_ref[["id", f"FinalElecCode{year}", f"Pop{year}"]].rename(
        columns={f"FinalElecCode{year}": "from_code", f"Pop{year}": "people"})
    b = df_alt[["id", f"FinalElecCode{year}"]].rename(columns={f"FinalElecCode{year}": "to_code"})
    j = a.merge(b, on="id", how="inner")
    ch = j[j["from_code"] != j["to_code"]]
    flows = (ch.groupby(["from_code", "to_code"]).agg(settlements=("id", "size"), people=("people", "sum"))
             .reset_index().sort_values("people", ascending=False).reset_index(drop=True))
    flows["from_code"] = flows["from_code"].astype(int)
    flows["to_code"] = flows["to_code"].astype(int)
    totals = {"settlements": int(len(ch)), "people": float(ch["people"].sum())}
    return flows, totals


DELTA_METRICS = ["investment_musd_cum", "capacity_mw_cum", "people_reached_cum", "usd_per_new_connection",
                 "lcoe_energy_w", "grid_share_2040"]


def demand_delta(df_var: pd.DataFrame, df_base: pd.DataFrame) -> pd.DataFrame:
    hb, hv = headline(df_base), headline(df_var)
    rows = []
    for m in DELTA_METRICS:
        b, v = hb[m], hv[m]
        rows.append({"metric": m, "base": b, "variant": v, "delta_abs": v - b,
                     "delta_pct": (v - b) / b * 100 if b else float("nan")})
    return pd.DataFrame(rows)


def corridor_table(df: pd.DataFrame, geo_attr: pd.DataFrame, radius_km: float,
                   dist_col: str = "kkt_main_dist_km") -> dict:
    """Metrics for the settlements within radius_km of the line (geo_attr joined on id)."""
    j = df.merge(geo_attr[["id", dist_col]], on="id", how="inner")
    g = j[j[dist_col] <= radius_km]
    if g.empty:
        return {"settlements": 0, "people_2040": 0.0}
    cum = cumulative_table(g)
    nc = float(cum.loc[TOTAL, "new_connections_cum"])
    inv = float(cum.loc[TOTAL, "investment_musd_cum"])
    code = g["FinalElecCode2040"]
    mix = {c: float(g.loc[code == c, "Pop2040"].sum()) for c in SERVED_CODES}
    return {"settlements": int(len(g)), "people_2040": float(g["Pop2040"].sum()),
            "people_start": float(g["PopStartYear"].sum()) if "PopStartYear" in g else float("nan"),
            "electrified_start_settlements": int((g["ElecStart"] == 1).sum()),
            "new_connections_cum": nc, "investment_musd_cum": inv,
            "usd_per_new_connection": inv * 1e6 / nc if nc else float("nan"),
            "lcoe_energy_w": weighted_lcoe(g, 2040, "energy"),
            "mix_pop_2040": mix,
            "grid_share_2040": float(category_shares(g, 2040).get("Grid", 0.0))}


def subset_table(df: pd.DataFrame, mask: pd.Series) -> dict:
    """Same metrics as corridor_table for an arbitrary boolean selection of settlements."""
    g = df[mask]
    if g.empty:
        return {"settlements": 0, "people_2040": 0.0}
    cum = cumulative_table(g)
    nc = float(cum.loc[TOTAL, "new_connections_cum"])
    inv = float(cum.loc[TOTAL, "investment_musd_cum"])
    code = g["FinalElecCode2040"]
    return {"settlements": int(len(g)), "people_2040": float(g["Pop2040"].sum()),
            "electrified_start_settlements": int((g["ElecStart"] == 1).sum()),
            "new_connections_cum": nc, "investment_musd_cum": inv,
            "usd_per_new_connection": inv * 1e6 / nc if nc else float("nan"),
            "lcoe_energy_w": weighted_lcoe(g, 2040, "energy"),
            "mix_pop_2040": {c: float(g.loc[code == c, "Pop2040"].sum()) for c in SERVED_CODES},
            "grid_share_2040": float(category_shares(g, 2040).get("Grid", 0.0))}


# ---------------------------------------------------------------------------
# Cross-scenario tables (take a report.data.Batch)
# ---------------------------------------------------------------------------
def sensitivity_table(batch) -> pd.DataFrame:
    """One row per demand case x grid cost: cumulative investment, capacity, people reached,
    USD per connection, energy-weighted LCOE, grid-extension settlements and people, and
    settlements and people switching technology relative to the reference cost."""
    rows = []
    for case in CASE_ORDER:
        by_cost = batch.by_case(case)
        ref = by_cost.get(REFERENCE_COST)
        for cost in sorted(by_cost):
            s = by_cost[cost]
            h = headline(s.settlements)
            sw = {"settlements": 0, "people": 0.0}
            if ref is not None and cost != REFERENCE_COST:
                _, sw = switches(ref.settlements, s.settlements, 2040)
            rows.append({"demand_case": case, "study_name": s.label, "grid_cost": cost,
                         "scenario_id": s.scenario_id,
                         "investment_musd_cum": h["investment_musd_cum"], "capacity_mw_cum": h["capacity_mw_cum"],
                         "people_reached_cum": h["people_reached_cum"],
                         "usd_per_new_connection": h["usd_per_new_connection"],
                         "lcoe_energy_w": h["lcoe_energy_w"], "lcoe_energy_w_excl_dens": h["lcoe_energy_w_excl_dens"],
                         "grid_share_2040": h["grid_share_2040"],
                         "grid_ext_settlements": h["grid_ext_settlements_2040"],
                         "grid_ext_people": h["grid_ext_people_2040"],
                         "mg_pv_people_2040": h["mg_pv_people_2040"], "sa_pv_people_2040": h["sa_pv_people_2040"],
                         "switched_settlements": sw["settlements"], "switched_people": sw["people"]})
    return pd.DataFrame(rows)


def never_grid_table(batch) -> pd.DataFrame:
    """Settlements that no scenario of the batch connects to the grid by 2040, by region."""
    ids = None
    for s in batch.scenarios.values():
        g = s.settlements
        off = set(g.loc[~g["FinalElecCode2040"].isin(GRID_CODES), "id"])
        ids = off if ids is None else ids & off
    ref = batch.reference()[0].settlements if batch.reference() else next(iter(batch.scenarios.values())).settlements
    g = ref[ref["id"].isin(ids or set())]
    t = g.groupby(g["Admin_1"].astype(str), observed=True).agg(settlements=("id", "size"), people_2040=("Pop2040", "sum"),
                                                              people_start=("PopStartYear", "sum"))
    t.loc[TOTAL] = t.sum()
    t.index.name = "region"
    return t.sort_values("people_2040", ascending=False)
