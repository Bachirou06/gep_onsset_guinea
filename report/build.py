"""Build the static HTML results report for one finished batch.

    python -m report.build GuineaRuns/Outputs/2026-10-25_table1 --inputs "GuineaRuns/Inputs/Guinea Data"

Writes <batch>/report/guinea_scenarios_report_<batch>.html and build_manifest.json.
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

from report import figures as F
from report import maps as MP
from report import messages as MS
from report import metrics as M
from report.constants import (CASE_DESCRIPTION, CASE_ORDER, CASE_STUDY_NAME, CHAPTERS, COST_LEVELS, COST_ROLE,
                              DEMAND_VARIANTS, KEY_CASES, NOT_ASSIGNED, REFERENCE_COST, SENSITIVITY_CASES, SERVED_CODES,
                              TECH, TECH_KEY, TECH_LABEL, TECH_ORDER)
from report.data import check_consistency, load_batch
from report.render import render, table_html

F_INT, F_1, F_2, F_LCOE, F_PCT = "{:,.0f}", "{:,.1f}", "{:,.2f}", "{:.3f}", "{:.1%}"
METRIC_LABELS = {"investment_musd_cum": "Cumulative investment (million USD)", "capacity_mw_cum": "Cumulative capacity (MW)",
                 "people_reached_cum": "People reached 2025 to 2040", "usd_per_new_connection": "USD per newly connected person",
                 "lcoe_energy_w": "Delivered LCOE 2040, energy-weighted (USD/kWh)", "grid_share_2040": "Grid share of 2040 population",
                 "lcoe_energy_w_excl_dens": "Delivered LCOE 2040 excluding densification (USD/kWh)", "people_per_musd": "People per million USD",
                 "population_2040": "Population 2040", "new_connections_cum": "New connections 2025 to 2040"}


def _git(repo_root):
    try:
        c = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=True).stdout.strip()
        d = bool(subprocess.run(["git", "status", "--porcelain"], cwd=repo_root, capture_output=True, text=True, check=True).stdout.strip())
        return c, d
    except Exception:
        return "unknown", None


def _versions():
    import matplotlib
    import plotly
    v = {"python": sys.version.split()[0], "pandas": pd.__version__, "plotly": plotly.__version__,
         "matplotlib": matplotlib.__version__}
    try:
        import geopandas
        v["geopandas"] = geopandas.__version__
    except ImportError:
        v["geopandas"] = "not installed"
    return v


def _case_rows(refs, fn):
    """{study name: value} over the reference scenarios in display order."""
    return {CASE_STUDY_NAME.get(s.demand_case, s.demand_case): fn(s) for s in refs}


def _tech_rows_table(by_case: dict, column: str, fmt: str, caption: str, index_label="Technology") -> str:
    """Rows technology (+ totals), columns study names, from per-case consultancy_metrics frames."""
    frame = pd.DataFrame({name: cm[column] for name, cm in by_case.items()})
    frame.index = [TECH_LABEL.get(i, i) if not isinstance(i, str) else i for i in frame.index]
    return table_html(frame, {c: fmt for c in frame.columns}, caption=caption, index_label=index_label,
                      total_rows=[M.TOTAL, M.TOTAL_EXCL])


DEFAULT_MAP_COLOURS = 96     # palette quantisation of the map PNGs; six technology colours plus greys lose nothing


def build(batch_dir, repo_root, out_path=None, inputs_dir=None, id_subset=None, maps=True, geo=True,
          corridor_km=10, map_dpi=150, map_colours=DEFAULT_MAP_COLOURS, sample=False, use_cache=True,
          allow_inconsistent=False, log=print) -> Path:
    t0 = time.time()
    batch_dir = Path(batch_dir)
    repo_root = Path(repo_root)
    out_path = Path(out_path) if out_path else batch_dir / "report" / f"guinea_scenarios_report_{batch_dir.name}.html"
    out_dir = out_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / "cache"
    assets = {}

    batch = load_batch(batch_dir, repo_root, cache_dir=cache_dir, id_subset=id_subset, use_cache=use_cache, log=log)
    refs = batch.reference()
    ref_by_case = {s.demand_case: s for s in refs}
    primary = ref_by_case.get("BU", refs[0])
    n_settlements = int(len(primary.settlements))
    log(f"batch {batch.name}: {len(batch.scenarios)} scenarios, {n_settlements} settlements, {len(refs)} reference cases")

    # --- consistency --------------------------------------------------------
    if sample:
        consistency, cons_df = "skipped (sample)", None
    else:
        cons_df = check_consistency(batch)
        bad = int((~cons_df["ok"]).sum())
        consistency = "PASS" if bad == 0 else f"FAIL ({bad} mismatches)"
        if bad and not allow_inconsistent:
            raise RuntimeError(f"consistency check failed: {bad} mismatches; see check_consistency(batch)")
    log(f"consistency: {consistency}")

    # --- geography ------------------------------------------------------------
    layers = geo_attr = None
    if geo and inputs_dir is not None:
        from report.geo import HAS_GEO, load_layers, settlement_geo_attributes
        if HAS_GEO:
            layers = load_layers(inputs_dir)
            geo_attr = settlement_geo_attributes(primary.settlements[["id", "X_deg", "Y_deg"]], layers, cache_dir,
                                                 inputs_dir=inputs_dir, log=log)
    elif maps and inputs_dir is not None:
        try:
            from report.geo import HAS_GEO, load_layers
            layers = load_layers(inputs_dir) if HAS_GEO else None
        except Exception:
            layers = None

    # --- metrics ---------------------------------------------------------------
    H = {s.demand_case: M.headline(s.settlements) for s in refs}
    TT = {s.demand_case: {y: M.tech_table(s.settlements, y) for y in (2030, 2040)} for s in refs}
    CM = {CASE_STUDY_NAME.get(s.demand_case, s.demand_case): M.consultancy_metrics(s.settlements) for s in refs}
    REG = {s.demand_case: M.region_table(s.settlements, 2040) for s in refs}
    UR = {s.demand_case: M.urban_rural_table(s.settlements) for s in refs}
    HY = {s.demand_case: M.hydro_table(s.settlements, 2040) for s in refs}
    sens = M.sensitivity_table(batch)
    deltas_df, deltas = {}, {}
    for variant, base in DEMAND_VARIANTS:
        if variant in ref_by_case and base in ref_by_case:
            d = M.demand_delta(ref_by_case[variant].settlements, ref_by_case[base].settlements)
            deltas_df[variant] = d
            deltas[variant] = d.set_index("metric")["delta_pct"].to_dict()
    bu = batch.by_case("BU")
    flows_bu, totals_bu = (M.switches(bu[REFERENCE_COST].settlements, bu[max(bu)].settlements)
                           if REFERENCE_COST in bu and max(bu) != REFERENCE_COST else (pd.DataFrame(), {}))
    start = M.start_year_table(primary.settlements)
    never = M.never_grid_table(batch)
    phasing_bu = M.phasing_table(primary.settlements)

    # --- supply-side variants ---------------------------------------------------
    vc = M.variant_comparison(batch)
    variant_names = batch.variant_names()

    # --- key messages ---------------------------------------------------------
    key_messages = MS.key_messages(H, sens, deltas, HY, vc if len(vc) else None)
    kpis = [{"study_name": CASE_STUDY_NAME.get(s.demand_case, s.demand_case) + (" (key scenario)" if s.demand_case in KEY_CASES else ""),
             "description": CASE_DESCRIPTION.get(s.demand_case, ""),
             "dre_new": MS.fmt_pct(H[s.demand_case]["dre_share_new_connections"]),
             "people": MS.fmt_people(H[s.demand_case]["people_reached_cum"]),
             "investment": MS.fmt_musd(H[s.demand_case]["investment_musd_cum"]),
             "usd_per_connection": MS.fmt_usd(H[s.demand_case]["usd_per_new_connection"]),
             "lcoe": MS.fmt_lcoe(H[s.demand_case]["lcoe_energy_w"]),
             "lcoe_new": MS.fmt_lcoe(H[s.demand_case]["lcoe_energy_w_excl_dens"])} for s in refs]
    n_urban = int((primary.settlements["IsUrban"] == 2).sum())
    urban_people = float(primary.settlements.loc[primary.settlements["IsUrban"] == 2, "Pop2040"].sum())
    meta = batch.control.get("meta", {})
    p_ref = primary.manifest.get("parameters", {})
    cap_conn = p_ref.get("annual_new_grid_connections_limit_intermediate", 127)
    cap_mw = p_ref.get("annual_grid_cap_gen_limit_intermediate", 90)
    disc = p_ref.get("discount_rate", 0.08)
    target_mid = p_ref.get("intermediate_electrification_target", 0.7)
    yr_start, yr_mid, yr_end = p_ref.get("start_year", 2025), p_ref.get("intermediate_year", 2030), p_ref.get("end_year", 2040)
    cost_levels = sorted({s.grid_cost for s in batch.scenarios.values()})
    hi_cost = max(cost_levels)

    # --- tables -------------------------------------------------------------------
    T = {}
    rows = [{"Scenario id": s.scenario_id, "Study name": CASE_STUDY_NAME.get(s.demand_case, s.demand_case),
             "Demand case": s.demand_case, "Urban tier": s.urban_tier, "Rural tier": s.rural_tier,
             "Grid cost (USD/kWh)": s.grid_cost, "Cost role": COST_ROLE.get(s.grid_cost, ""), "Label": s.label}
            for s in batch.scenarios.values()]
    T["t21"] = table_html(pd.DataFrame(rows), {"Grid cost (USD/kWh)": "{:.3f}"}, index=False,
                          caption="Table 2.1. Scenario matrix of the batch")
    p = primary.manifest.get("parameters", {})
    keys = ["start_year", "intermediate_year", "end_year", "intermediate_electrification_target", "electrification_rate_target",
            "num_people_per_hh_urban", "num_people_per_hh_rural", "discount_rate", "annual_new_grid_connections_limit_intermediate",
            "annual_grid_cap_gen_limit_intermediate", "grid_generation_cost", "grid_power_plants_capital_cost", "grid_losses",
            "mg_pv_capital_cost", "mg_hydro_capital_cost", "sa_pv_capital_cost_1", "sa_pv_capital_cost_3", "sa_pv_capital_cost_5",
            "mv_line_cost", "lv_line_cost", "hv_line_cost", "tier_1", "tier_2", "tier_3", "tier_4", "tier_5",
            "productive_demand", "productive_preference", "tech_switches", "diesel_techs", "pop_threshold"]
    def _readable(k, v):
        if isinstance(v, dict) and set(v) == {"inf"}:
            return f"{v['inf']:,.0f} USD/kW, all years"
        if k == "tech_switches" and isinstance(v, dict):
            return ", ".join(f"{t} {'on' if on else 'off'}" for t, on in v.items())
        if isinstance(v, float) and v.is_integer():
            return f"{int(v):,}"
        if isinstance(v, (int, float)):
            return f"{v:,}" if abs(v) >= 1000 else str(v)
        return str(v)
    T["t22"] = table_html(pd.DataFrame([{"Parameter": k, "Value": _readable(k, p[k])} for k in keys if k in p]), index=False,
                          caption="Table 2.2. Shared assumptions of every scenario (from the batch manifests)")
    cal = primary.manifest.get("calibration", {})
    cal_rows = [{"Parameter": k, "Value": _readable(k, v)} for k, v in cal.items()]
    cal_rows += [{"Parameter": "calibrated input", "Value": ", ".join(batch.provenance()["calibrated_csv"])},
                 {"Parameter": "settlements in the model", "Value": f"{primary.manifest.get('rows_out', n_settlements):,}"},
                 {"Parameter": "raw extraction", "Value": meta.get("input_file_confirmed", "see the control file")},
                 {"Parameter": "settlements classed urban", "Value": f"{n_urban} ({MS.fmt_people(urban_people)} people in {yr_end})"}]
    T["t23"] = table_html(pd.DataFrame(cal_rows), index=False, caption="Table 2.3. Calibration block and input file")
    sup = batch.control.get("meta", {}).get("superseded_runs", {})
    T["t24"] = table_html(pd.DataFrame([{"Earlier run": k, "Status": v} for k, v in sup.items()]) if sup else
                          pd.DataFrame([{"Earlier run": "none", "Status": ""}]), index=False,
                          caption="Table 2.4. Earlier runs superseded by this batch")
    T["t31"] = table_html(start, {"settlements": F_INT, "electrified_settlements": F_INT, "pop_start": F_INT,
                                  "electrified_pop_start": F_INT, "access_rate_start": F_PCT, "urban_pop_start": F_INT},
                          caption="Table 3.1. Start-year (2025) electrification by region after calibration",
                          col_labels={"settlements": "Settlements", "electrified_settlements": "Electrified settlements",
                                      "pop_start": "Population 2025", "electrified_pop_start": "Electrified population 2025",
                                      "access_rate_start": "Access rate 2025", "urban_pop_start": "Urban population 2025"},
                          index_label="Region", total_rows=["Total"])
    never = pd.concat([never.drop(index="Total", errors="ignore"), never.loc[["Total"]]]) if "Total" in never.index else never
    T["t32"] = table_html(never, {"settlements": F_INT, "people_2040": F_INT, "people_start": F_INT},
                          caption="Table 3.2. Settlements that no scenario connects to the grid by 2040, by region",
                          col_labels={"settlements": "Settlements", "people_2040": "People 2040", "people_start": "People 2025"},
                          index_label="Region", total_rows=["Total"])
    hl = pd.DataFrame({CASE_STUDY_NAME.get(c, c): {k: v for k, v in H[c].items() if not isinstance(v, dict)} for c in H}).T
    hl_cols = ["population_2040", "people_reached_cum", "investment_musd_cum", "capacity_mw_cum", "usd_per_new_connection",
               "people_per_musd", "lcoe_energy_w", "lcoe_energy_w_excl_dens", "grid_share_2040", "dre_share_new_connections",
               "dre_share_pop_2040"]
    T["t41"] = table_html(hl[hl_cols], {"population_2040": F_INT, "people_reached_cum": F_INT, "investment_musd_cum": F_1,
                                        "capacity_mw_cum": F_1, "usd_per_new_connection": F_INT, "people_per_musd": F_INT,
                                        "lcoe_energy_w": F_LCOE, "lcoe_energy_w_excl_dens": F_LCOE, "grid_share_2040": F_PCT,
                                        "dre_share_new_connections": F_PCT, "dre_share_pop_2040": F_PCT},
                          caption=f"Table 4.1. Headline results per demand case at {REFERENCE_COST} USD/kWh (key scenarios: "
                                  f"{', '.join(CASE_STUDY_NAME.get(k, k) for k in KEY_CASES if k in H)})",
                          col_labels={**METRIC_LABELS, "dre_share_new_connections": "Decentralised share of new connections",
                                      "dre_share_pop_2040": "Decentralised share of 2040 population"}, index_label="Demand case")
    mix = M.mix_table({s.demand_case: s.settlements for s in refs})
    mix.index = pd.MultiIndex.from_tuples([(CASE_STUDY_NAME.get(c, c), "New connections 2025 to 2040" if b == "new_connections"
                                            else "Population 2040 (incl. already on the grid)") for c, b in mix.index],
                                          names=["Demand case", "Basis"])
    T["t41b"] = table_html(mix, {**{c: F_PCT for c in mix.columns if c != "total"}, "total": F_INT},
                           caption="Table 4.1b. Technology mix per demand case on two bases: share of the new connections (where the "
                                   "decentralised impact shows) and share of the 2040 population, which includes the people already on the grid",
                           col_labels={"total": "Total (people)"}, index_label="Demand case / basis")
    reg_pop = pd.DataFrame({CASE_STUDY_NAME.get(c, c): REG[c]["grid_share"] for c in REG})
    reg_pop.insert(0, "Population 2040", REG[primary.demand_case]["population"])
    T["t42"] = table_html(reg_pop.sort_values("Population 2040", ascending=False),
                          {"Population 2040": F_INT, **{c: F_PCT for c in reg_pop.columns if c != "Population 2040"}},
                          caption="Table 4.2. Grid share of the 2040 population by region and demand case", index_label="Region")
    reg_inv = pd.DataFrame({CASE_STUDY_NAME.get(c, c): REG[c]["investment_musd_cum"] for c in REG})
    T["t42b"] = table_html(reg_inv.sort_values(reg_inv.columns[-1], ascending=False), {c: F_1 for c in reg_inv.columns},
                           caption="Table 4.2b. Cumulative investment 2025 to 2040 by region and demand case (million USD)",
                           index_label="Region")
    ur = pd.concat({CASE_STUDY_NAME.get(c, c): UR[c] for c in UR}, names=["Demand case", "Area"])
    T["t43"] = table_html(ur, {"settlements": F_INT, "population_2040": F_INT, "new_connections_cum": F_INT,
                               "investment_musd_cum": F_1, "usd_per_new_connection": F_INT, "lcoe_energy_w": F_LCOE,
                               "grid_share_2040": F_PCT},
                          caption="Table 4.3. Urban and rural split per demand case (urban = the settlements the model classes as urban)",
                          col_labels={"settlements": "Settlements", "population_2040": "Population 2040",
                                      "new_connections_cum": "New connections", "investment_musd_cum": "Investment (million USD)",
                                      "usd_per_new_connection": "USD per person", "lcoe_energy_w": "LCOE (USD/kWh)",
                                      "grid_share_2040": "Grid share"}, index_label="Demand case / area")
    T["t51"] = _tech_rows_table(CM, "usd_per_new_connection", F_INT, "Table 5.1. Capital cost per newly connected person (USD), 2025 to 2040")
    T["t52"] = _tech_rows_table(CM, "people_per_musd", F_INT, "Table 5.2. People reached per million USD invested, 2025 to 2040")
    T["t53"] = _tech_rows_table(CM, "lcoe_energy_w", F_LCOE, "Table 5.3. Delivered LCOE 2040, energy-weighted (USD/kWh)")
    sh = pd.DataFrame({CASE_STUDY_NAME.get(s.demand_case, s.demand_case): {
        "Grid, all": M.category_shares(s.settlements, 2040).get("Grid", 0.0),
        "Off-grid, all": 1 - M.category_shares(s.settlements, 2040).get("Grid", 0.0),
        "Grid, newly electrified": M.category_shares(s.settlements, 2040, True).get("Grid", 0.0),
        "Off-grid, newly electrified": 1 - M.category_shares(s.settlements, 2040, True).get("Grid", 0.0)} for s in refs}).T
    T["t54"] = table_html(sh, {c: F_PCT for c in sh.columns}, caption="Table 5.4. Grid and off-grid shares of the 2040 population, all settlements and newly electrified settlements only", index_label="Demand case")
    hy = pd.DataFrame({CASE_STUDY_NAME.get(c, c): HY[c] for c in HY}).T
    T["t61"] = table_html(hy[["sites", "settlements", "people", "capacity_mw", "investment_musd", "capacity_mw_cum", "investment_musd_cum", "mean_dist_km"]],
                          {"sites": F_INT, "settlements": F_INT, "people": F_INT, "capacity_mw": F_2, "investment_musd": F_2,
                           "capacity_mw_cum": F_2, "investment_musd_cum": F_2, "mean_dist_km": F_1},
                          caption="Table 6.1. Hydro mini-grids per demand case: the 2040 period, and cumulative over 2025 to 2040",
                          col_labels={"sites": "Sites used 2040", "settlements": "Settlements 2040", "people": "People 2040", "capacity_mw": "Capacity 2040 period (MW)",
                                      "investment_musd": "Investment 2040 period (million USD)", "capacity_mw_cum": "Capacity cumulative (MW)",
                                      "investment_musd_cum": "Investment cumulative (million USD)", "mean_dist_km": "Mean distance to site (km)"},
                          index_label="Demand case")
    ph = []
    for y in (2030, 2040):
        t = TT[primary.demand_case][y].reindex(SERVED_CODES)
        for c in SERVED_CODES:
            ph.append({"Period": f"to {y}", "Technology": TECH_LABEL[c], "New connections": t.loc[c, "new_connections"],
                       "Capacity (MW)": t.loc[c, "capacity_mw"], "Investment (million USD)": t.loc[c, "investment_musd"]})
    T["t71"] = table_html(pd.DataFrame(ph), {"New connections": F_INT, "Capacity (MW)": F_1, "Investment (million USD)": F_1}, index=False,
                          caption=f"Table 7.1. Phasing by period and technology, {CASE_STUDY_NAME.get(primary.demand_case)} case")
    reg_ph = phasing_bu.groupby(level=["period", "region"])["new_connections"].sum().unstack("period").fillna(0.0)
    reg_ph.columns = [f"New connections to {c}" for c in reg_ph.columns]
    T["t71b"] = table_html(reg_ph.sort_values(reg_ph.columns[-1], ascending=False), {c: F_INT for c in reg_ph.columns},
                           caption=f"Table 7.1b. New connections by region and period, {CASE_STUDY_NAME.get(primary.demand_case)} case", index_label="Region")

    corridor = geo_attr is not None
    corridor_text = corridor_note = ""
    if corridor:
        cr = []
        for s in refs:
            for r in (5, corridor_km, 25) if corridor_km not in (5, 25) else (5, 25):
                c = M.corridor_table(s.settlements, geo_attr, r)
                cr.append({"Demand case": CASE_STUDY_NAME.get(s.demand_case, s.demand_case), "Corridor (km)": r, **{k: v for k, v in c.items() if k != "mix_pop_2040"},
                           **{f"pop_{TECH[k][0]}": v for k, v in c.get("mix_pop_2040", {}).items()}})
        crd = pd.DataFrame(cr)
        corridor_formats = {"settlements": F_INT, "people_2040": F_INT, "people_start": F_INT, "electrified_start_settlements": F_INT,
                            "people_newly_electrified_2040": F_INT, "new_connections_cum": F_INT, "investment_musd_cum": F_2,
                            "usd_per_new_connection": F_INT, "lcoe_energy_w": F_LCOE, "lcoe_energy_w_excl_dens": F_LCOE,
                            "grid_share_2040": F_PCT, "grid_share_newly_electrified": F_PCT, **{f"pop_{TECH[k][0]}": F_INT for k in SERVED_CODES}}
        corridor_labels = {"settlements": "Settlements", "people_2040": "People 2040", "people_start": "People 2025",
                           "electrified_start_settlements": "Settlements grid-connected in 2025",
                           "people_newly_electrified_2040": "People in newly electrified settlements, 2040",
                           "new_connections_cum": "New connections", "investment_musd_cum": "Investment (million USD)",
                           "usd_per_new_connection": "USD per person", "lcoe_energy_w": "LCOE, all (USD/kWh)",
                           "lcoe_energy_w_excl_dens": "LCOE, newly electrified (USD/kWh)", "grid_share_2040": "Grid share, all",
                           "grid_share_newly_electrified": "Grid share, newly electrified",
                           **{f"pop_{TECH[k][0]}": f"People on {TECH_LABEL[k][0].lower() + TECH_LABEL[k][1:]}" for k in SERVED_CODES}}
        T["t81"] = table_html(crd, corridor_formats, index=False,
                              caption="Table 8.1. Settlements within a corridor of the planned Linsan to Manantali line, per demand case",
                              col_labels=corridor_labels)
        sub_rows = []
        g = primary.settlements.merge(geo_attr, on="id", how="left")
        for s in refs:
            gs = s.settlements.merge(geo_attr, on="id", how="left")
            for label, mask in (("Affected localities (5)", gs["affected_locality"].astype(str) != ""),
                                ("Moyen-Bafing national park", gs["in_moyen_bafing"].astype(bool)),
                                ("Protected areas crossed by the line (9)", gs["in_protected_span_hv"].astype(bool)),
                                ("All protected areas", gs["in_protected_area"].astype(bool))):
                st = M.subset_table(gs, mask)
                sub_rows.append({"Demand case": CASE_STUDY_NAME.get(s.demand_case, s.demand_case), "Area": label,
                                 **{k: v for k, v in st.items() if k != "mix_pop_2040"}})
        srd = pd.DataFrame(sub_rows)
        T["t82"] = table_html(srd, corridor_formats, index=False,
                              caption="Table 8.2. Settlements inside the affected localities and protected areas, per demand case",
                              col_labels=corridor_labels)
        c10 = M.corridor_table(primary.settlements, geo_attr, corridor_km)
        already = 1 - c10["people_newly_electrified_2040"] / c10["people_2040"] if c10["people_2040"] else 0.0
        new_mix = {k: v for k, v in c10["mix_pop_2040"].items()}
        corridor_text = (f"Within {corridor_km} km of the planned Linsan to Manantali 225 kV line the batch holds {c10['settlements']:,} settlements "
                         f"with {MS.fmt_people(c10['people_2040'])} people in {yr_end}. {MS.fmt_pct(already)} of those people live in the "
                         f"{c10['electrified_start_settlements']:,} settlements that were already grid-connected in {yr_start} (the towns along the line), "
                         f"so the comparison that matters is the {MS.fmt_people(c10['people_newly_electrified_2040'])} people in newly electrified settlements. "
                         f"In the {CASE_STUDY_NAME.get(primary.demand_case)} case the least-cost mix reaches {MS.fmt_pct(c10['grid_share_newly_electrified'])} of them "
                         f"by grid extension and the rest by decentralised systems, at a delivered cost of {MS.fmt_lcoe(c10['lcoe_energy_w_excl_dens'])} "
                         f"for the newly electrified settlements ({MS.fmt_lcoe(c10['lcoe_energy_w'])} over all corridor settlements, where the towns are costed at the "
                         f"generation price) and {MS.fmt_usd(c10['usd_per_new_connection'])} per newly connected person. Tables 8.1 and 8.2 give the same metrics for "
                         f"5 and 25 km corridors, for the five localities named as affected, for the Moyen-Bafing park and for the protected areas the line crosses.")
        corridor_note = ("The corridor is measured from the Linsan to Manantali feature only; the second feature of the layer (Maneah to Grandes Chutes) "
                         "runs beside Conakry and would add the capital's population. The planned-grid layer used by the model is a copy of the existing "
                         "network, so none of these settlements was modelled as reachable through the Koukoutamba line; the paired scenario will do that.")

    ge = sens.pivot(index="demand_case", columns="grid_cost", values=["grid_ext_settlements", "grid_ext_people"])
    ge = ge.reindex([c for c in CASE_ORDER if c in ge.index])
    ge.index = [CASE_STUDY_NAME.get(c, c) for c in ge.index]
    ge.columns = [f"{'Settlements' if a == 'grid_ext_settlements' else 'People'} at {b}" for a, b in ge.columns]
    T["t91"] = table_html(ge, {c: F_INT for c in ge.columns}, caption="Table 9.1. Grid extension in 2040 by grid generation cost (USD/kWh)", index_label="Demand case")
    sw_rows = []
    for case in SENSITIVITY_CASES:
        by_cost = batch.by_case(case)
        if REFERENCE_COST not in by_cost:
            continue
        for cost in sorted(by_cost):
            if cost == REFERENCE_COST:
                continue
            fl, tot = M.switches(by_cost[REFERENCE_COST].settlements, by_cost[cost].settlements)
            top = "; ".join(f"{TECH_LABEL[int(r.from_code)]} to {TECH_LABEL[int(r.to_code)]} ({r.people / 1e6:.2f} M)" for r in fl.head(3).itertuples())
            sw_rows.append({"Demand case": CASE_STUDY_NAME.get(case, case), "Grid cost (USD/kWh)": cost, "Switched settlements": tot["settlements"],
                            "Switched people": tot["people"], "Largest flows": top or "none"})
    T["t92"] = table_html(pd.DataFrame(sw_rows), {"Switched settlements": F_INT, "Switched people": F_INT, "Grid cost (USD/kWh)": "{:.3f}"}, index=False,
                          caption=f"Table 9.2. Settlements whose least-cost technology differs from the reference ({REFERENCE_COST} USD/kWh) in 2040")
    dd = []
    metric_fmt = {"investment_musd_cum": F_1, "capacity_mw_cum": F_1, "people_reached_cum": F_INT, "usd_per_new_connection": F_INT,
                  "lcoe_energy_w": F_LCOE, "lcoe_energy_w_excl_dens": F_LCOE, "grid_share_2040": F_PCT}
    for variant, d in deltas_df.items():
        base = dict(DEMAND_VARIANTS)[variant]
        for r in d.itertuples():
            f = metric_fmt.get(r.metric, F_2)
            dd.append({"Variant": f"{CASE_STUDY_NAME.get(variant)} vs {CASE_STUDY_NAME.get(base)}", "Metric": METRIC_LABELS.get(r.metric, r.metric),
                       "Base": f.format(r.base), "Variant value": f.format(r.variant),
                       "Change": ("{:+.1%}" if f == F_PCT else "{:+,.3f}" if f == F_LCOE else "{:+,.1f}" if f == F_1 else "{:+,.0f}").format(r.delta_abs),
                       "Change (%)": f"{r.delta_pct:+.1f}"})
    T["t93"] = table_html(pd.DataFrame(dd) if dd else pd.DataFrame([{"Variant": "none", "Metric": "", "Base": "", "Variant value": "", "Change": "", "Change (%)": ""}]),
                          index=False, caption="Table 9.3. Demand variants against their base case at the reference grid cost")
    VARIANT_LABELS = {"optgrid": "Optimistic grid expansion (no connection or capacity cap to 2030)",
                      "optgrid_optmg": "Optimistic grid expansion and mini-grid PV panels 25 percent cheaper"}
    if len(vc):
        wide = vc.pivot_table(index=["demand_case", "variant", "metric"], values=["reference", "variant_value", "delta_pct"], aggfunc="first")
        vrows = []
        for (case, variant, metric), r in wide.iterrows():
            f = metric_fmt.get(metric, F_INT if "people" in metric or "unserved" in metric else F_2)
            vrows.append({"Demand case": CASE_STUDY_NAME.get(case, case), "Variant": VARIANT_LABELS.get(variant, variant),
                          "Metric": METRIC_LABELS.get(metric, metric.replace("_", " ")), "Reference": f.format(r["reference"]),
                          "Variant value": f.format(r["variant_value"]), "Change (%)": f"{r['delta_pct']:+.1f}" if pd.notna(r["delta_pct"]) else "n/a"})
        order = {m: i for i, m in enumerate(M.VARIANT_METRICS)}
        vdf = pd.DataFrame(vrows)
        T["t94"] = table_html(vdf, index=False, caption="Table 9.4. Supply-side variants against their reference scenario at the reference grid cost")
    else:
        T["t94"] = ""
    T["a1"] = table_html(pd.DataFrame([{"Scenario id": s["id"], "Demand case": s["demand_case"], "Overrides": json.dumps(s["overrides"]),
                                        "Legacy run": s.get("legacy_name") or ""} for s in batch.control.get("scenarios", [])]),
                         index=False, caption="Table A.1. Scenario overrides in the control file")
    T["a2"] = table_html(pd.DataFrame([{"Scenario id": s.scenario_id, "Started": s.manifest.get("started", ""), "Seconds": s.manifest.get("seconds", 0),
                                        "Git commit": str(s.manifest.get("git_commit", ""))[:7], "Dirty": str(s.manifest.get("git_dirty", "")),
                                        "Calibrated sha256": str(s.manifest.get("calibrated_csv_sha256", ""))[:12], "Rows": s.manifest.get("rows_out", 0),
                                        "Python": s.manifest.get("python", ""), "pandas": s.manifest.get("pandas", "")} for s in batch.scenarios.values()]),
                         {"Seconds": F_1, "Rows": F_INT}, index=False, caption="Table A.2. Run manifests")
    if cons_df is not None:
        cs = cons_df.groupby("scenario_id")["ok"].agg(checks="size", passed="sum").reset_index()
        T["a3"] = table_html(cs, {"checks": F_INT, "passed": F_INT}, index=False, caption="Table A.3. Consistency check of per-settlement aggregates against comparison_summary.csv")
    else:
        T["a3"] = table_html(pd.DataFrame([{"Consistency check": consistency}]), index=False, caption="Table A.3. Consistency check")
    T["glossary"] = table_html(pd.DataFrame([{"Term": TECH[c][1], "Code": c, "Category": TECH[c][3], "Meaning": {
        1: "Settlement already on the grid in 2025, served by densification of the existing network",
        2: "Settlement newly connected by extending the MV network", 3: "Solar home systems, sized per household",
        5: "Mini-grid with PV generation and battery storage (diesel switched off)", 7: "Mini-grid fed by a small hydro site within 10 km",
        99: "Not yet electrified in 2030 under the 70 percent interim target"}[c]} for c in TECH_ORDER]), index=False, caption="Glossary of technology classes")

    # --- figures -----------------------------------------------------------------
    figs = {"ch4": [], "ch9": [], "ch9b": []}
    long = pd.DataFrame([{"demand_case": c, "year": y, "code": code, **row.to_dict()}
                         for c in TT for y in TT[c] for code, row in TT[c][y].iterrows()])
    x_order = [c for c in CASE_ORDER if c in TT]
    src_ref = f"{', '.join(s.scenario_id for s in refs)} Results files; batch {batch.name}"
    for num, col, title, ytitle, cap in (("4.1", "population", "Population by least-cost technology", "People",
                                           "Population by least-cost technology in 2030 and 2040, per demand case (2030 includes the people not yet electrified under the 70 percent target)."),
                                          ("4.2", "new_connections", "New connections by technology", "People newly connected",
                                           "People newly connected in each period, by technology and demand case."),
                                          ("4.3", "capacity_mw", "New capacity by technology", "MW",
                                           "Capacity added in each period, by technology and demand case."),
                                          ("4.4", "investment_musd", "Investment by technology", "Million USD",
                                           "Investment in each period, by technology and demand case.")):
        fid = f"fig-{num.replace('.', '-')}"
        fig = F.stacked_by_tech(long, col, title, ytitle, x_order)
        figs["ch4"].append({"id": fid, "num": num, "div": F.fig_to_div(fig, fid), "caption": cap, "source": src_ref})
    hist = pd.concat([M.lcoe_histogram(s.settlements, 2040, newly_electrified_only=True).assign(demand_case=s.demand_case) for s in refs])
    figs["f46"] = {"div": F.fig_to_div(F.lcoe_histograms(hist, "Delivered LCOE distribution of the newly electrified settlements, 2040"), "fig-4-6"),
                   "caption": ("Population-weighted distribution of the delivered LCOE of the chosen technology in 2040 for the newly electrified "
                               "settlements (ElecStart 0), per demand case, in 0.005 USD/kWh bins; the diamond at the right end holds everyone above "
                               "0.60 USD/kWh. Settlements already on the grid are excluded because their LCOE equals the generation cost by construction."),
                   "source": f"MinimumOverallLCOE2040, Pop2040 and ElecStart of the reference Results files; {src_ref}"}
    gm = pd.DataFrame([{"demand_case": c, **{k: H[c][k] for k in ("usd_per_new_connection", "people_per_musd", "lcoe_energy_w")}} for c in H])
    figs["f51"] = {"div": F.fig_to_div(F.grouped_metric_bars(gm, ["usd_per_new_connection", "people_per_musd", "lcoe_energy_w"],
                                                              ["USD per newly connected person", "People per million USD", "Delivered LCOE 2040 (USD/kWh)"], x_order),
                                        "fig-5-1"),
                   "caption": "The three study metrics for the whole country, per demand case.", "source": "Tables 5.1 to 5.3"}
    ph_long = phasing_bu.reset_index().rename(columns={"region": "demand_case", "period": "year", "new_connections": "value"})
    reg_order = list(REG[primary.demand_case].sort_values("population", ascending=False).index)
    figs["f72"] = {"div": F.fig_to_div(F.stacked_by_tech(ph_long, "value", f"New connections by region and technology, {CASE_STUDY_NAME.get(primary.demand_case)} case",
                                                          "People newly connected", reg_order), "fig-7-2"),
                   "caption": f"People newly connected in each period by region and technology, {CASE_STUDY_NAME.get(primary.demand_case)} case.",
                   "source": f"{primary.scenario_id} Results file; batch {batch.name}"}
    for num, col, ytitle, cap in (("9.1", "investment_musd_cum", "Cumulative investment 2025 to 2040 (million USD)", "Cumulative investment against the grid generation cost."),
                                  ("9.2", "capacity_mw_cum", "Cumulative capacity added (MW)", "Cumulative capacity against the grid generation cost."),
                                  ("9.3", "usd_per_new_connection", "USD per newly connected person", "Capital cost per newly connected person against the grid generation cost."),
                                  ("9.3b", "lcoe_energy_w", "Delivered LCOE 2040, energy-weighted (USD/kWh)", "Delivered LCOE against the grid generation cost.")):
        fid = f"fig-{num.replace('.', '-')}"
        figs["ch9"].append({"id": fid, "num": num, "div": F.fig_to_div(F.lines_vs_cost(sens, col, ytitle), fid), "caption": cap,
                            "source": f"sensitivity table over the {len(batch.scenarios)} scenarios; batch {batch.name}"})
    sh_long = pd.DataFrame([{"demand_case": s.demand_case, "grid_cost": s.grid_cost, "code": code, "population": row["population"]}
                            for s in batch.scenarios.values() if s.demand_case in SENSITIVITY_CASES and s.variant == "reference"
                            for code, row in M.tech_table(s.settlements, 2040).iterrows() if code in SERVED_CODES])
    cases_present = [c for c in SENSITIVITY_CASES if (sh_long["demand_case"] == c).any()]
    figs["ch9"].append({"id": "fig-9-4", "num": "9.4", "div": F.fig_to_div(F.shares_vs_cost(sh_long, cases_present, "Technology shares of the 2040 population against the grid cost"), "fig-9-4"),
                        "caption": "Shares of the 2040 population by least-cost technology at each grid generation cost, per demand case.",
                        "source": f"FinalElecCode2040 and Pop2040 of the {len(sh_long['demand_case'].unique()) * len(COST_LEVELS)} sensitivity Results files"})
    # switch heat maps at the highest grid cost for every key case that has it
    hi_cost_all = max(cost_levels)
    n_sw = 0
    for case in [c for c in SENSITIVITY_CASES if c in ref_by_case]:
        by_cost = batch.by_case(case)
        if hi_cost_all not in by_cost or REFERENCE_COST not in by_cost:
            continue
        fl, tot = M.switches(by_cost[REFERENCE_COST].settlements, by_cost[hi_cost_all].settlements)
        if not len(fl):
            continue
        fid = "fig-9-5" if n_sw == 0 else f"fig-9-5{'bcd'[n_sw - 1]}"
        figs["ch9"].append({"id": fid, "num": "9.5" if n_sw == 0 else f"9.5{'bcd'[n_sw - 1]}",
                            "div": F.fig_to_div(F.switch_matrix(fl, f"Technology switches, {CASE_STUDY_NAME.get(case)} at {REFERENCE_COST} against {hi_cost_all} USD/kWh"), fid),
                            "caption": f"People moving between technologies when the grid cost rises from {REFERENCE_COST} to {hi_cost_all} USD/kWh, "
                                       f"{CASE_STUDY_NAME.get(case)} case ({tot['settlements']:,} settlements, {MS.fmt_people(tot['people'])} people).",
                            "source": f"{by_cost[REFERENCE_COST].scenario_id} and {by_cost[hi_cost_all].scenario_id} Results files joined on id"})
        n_sw += 1
    if n_sw == 0:
        figs["ch9"].append({"id": "fig-9-5", "num": "9.5", "div": "<p class='note'>No high grid-cost run for the key cases.</p>", "caption": "Not available.", "source": ""})
    for i, (variant, d) in enumerate(deltas_df.items()):
        base = dict(DEMAND_VARIANTS)[variant]
        fid = "fig-9-7" if i == 0 else f"fig-9-7{'b' if i == 1 else i}"
        figs["ch9b"].append({"id": fid, "num": "9.7" if i == 0 else "9.7b", "div": F.fig_to_div(F.delta_bars(d, f"{CASE_STUDY_NAME.get(variant)} against {CASE_STUDY_NAME.get(base)}", METRIC_LABELS), fid),
                             "caption": f"Percent change of the headline metrics, {CASE_STUDY_NAME.get(variant)} against {CASE_STUDY_NAME.get(base)} at {REFERENCE_COST} USD/kWh.",
                             "source": "Table 9.3"})
    if not figs["ch9b"]:
        figs["ch9b"].append({"id": "fig-9-7", "num": "9.7", "div": "<p class='note'>No demand variant in the batch.</p>", "caption": "Not available.", "source": ""})
    # grid cost bins for the bottom-up case: heat maps of the distribution
    figs["bins"] = []
    bins_case = "BU" if "BU" in ref_by_case else SENSITIVITY_CASES[0]
    bins_costs = sorted(batch.by_case(bins_case))
    bins_ok = len(bins_costs) >= 5
    if bins_ok:
        bt = M.cost_bin_table(batch, bins_case)
        tech_pop = bt[[f"pop_share_{TECH_KEY[c]}" for c in SERVED_CODES]].T
        tech_pop.index = [TECH_LABEL[c] for c in SERVED_CODES]
        tech_nc = bt[[f"nc_share_{TECH_KEY[c]}" for c in SERVED_CODES]].T
        tech_nc.index = [TECH_LABEL[c] for c in SERVED_CODES]
        reg = M.cost_bin_region_table(batch, bins_case)
        nm = CASE_STUDY_NAME.get(bins_case, bins_case)
        for fid, num, z, title, cap in (("fig-9-9", "9.9", tech_pop, f"Share of the 2040 population by technology and grid cost, {nm} case",
                                         "Share of the 2040 population served by each technology at each grid generation cost level; people already on the grid count under grid densification."),
                                        ("fig-9-9b", "9.9b", tech_nc, f"Share of new connections 2025 to 2040 by technology and grid cost, {nm} case",
                                         "Share of the people newly connected over 2025 to 2040 by each technology at each grid cost level, where the decentralised impact shows."),
                                        ("fig-9-10", "9.10", reg, f"Grid share of the 2040 population by region and grid cost, {nm} case",
                                         "Share of each region's 2040 population served by the grid (densification and extension) at each grid cost level.")):
            figs["bins"].append({"id": fid, "num": num, "div": F.fig_to_div(F.heatmap(z, title, "Grid cost (USD/kWh)", "", ".0%", colorbar_title="share"), fid),
                                 "caption": cap, "source": f"{', '.join(bt['scenario_id'])} Results files; batch {batch.name}"})
        bt_show = bt[["investment_musd_cum", "capacity_mw_cum", "grid_ext_settlements_2040", "grid_ext_people_2040", "dre_share_new_connections",
                      "usd_per_new_connection", "lcoe_energy_w_excl_dens"]].copy()
        bt_show.index = [f"{c}" for c in bt_show.index]
        T["t95"] = table_html(bt_show, {"investment_musd_cum": F_1, "capacity_mw_cum": F_1, "grid_ext_settlements_2040": F_INT, "grid_ext_people_2040": F_INT,
                                        "dre_share_new_connections": F_PCT, "usd_per_new_connection": F_INT, "lcoe_energy_w_excl_dens": F_LCOE},
                              caption=f"Table 9.5. Headline metrics of the {nm} case at each grid generation cost level (USD/kWh)",
                              col_labels={**METRIC_LABELS, "grid_ext_settlements_2040": "Grid-extension settlements 2040", "grid_ext_people_2040": "People on grid extension 2040",
                                          "dre_share_new_connections": "Decentralised share of new connections"}, index_label="Grid cost (USD/kWh)")
    else:
        T["t95"] = ""
    figs["ch9c"] = []
    vlabels = {**METRIC_LABELS, "grid_ext_people_2040": "People on grid extension 2040", "mg_pv_people_2040": "People on mini-grid PV 2040",
               "sa_pv_people_2040": "People on stand-alone PV 2040", "unserved_2030": "People not yet electrified 2030"}
    for i, variant in enumerate(variant_names):
        sub = vc[vc["variant"] == variant]
        fid = "fig-9-8" if i == 0 else f"fig-9-8{'bcd'[i - 1] if i <= 3 else i}"
        figs["ch9c"].append({"id": fid, "num": "9.8" if i == 0 else f"9.8{'bcd'[i - 1] if i <= 3 else i}",
                             "div": F.fig_to_div(F.delta_bars_by_case(sub, VARIANT_LABELS.get(variant, variant), vlabels,
                                                                      [m for m in M.VARIANT_METRICS if m != "unserved_2030"]), fid),
                             "caption": f"Percent change of the headline metrics under the variant '{VARIANT_LABELS.get(variant, variant)}' "
                                        f"against the reference scenario of each demand case, at {REFERENCE_COST} USD/kWh.",
                             "source": "Table 9.4"})

    # --- maps ----------------------------------------------------------------------
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    maps_ctx = {"map31": None, "ch4": [], "map61": None, "ch7": [], "map81": None, "map96": None, "map97": None}
    if maps:
        def add(key, png, caption, source, mid, num, alt, into=None):
            png = MP.shrink_png(png, map_colours) if map_colours else png
            entry = {"id": mid, "num": num, "uri": MP.png_data_uri(png), "caption": caption, "source": source, "alt": alt}
            assets[mid] = len(png)
            if into is not None:
                into.append(entry)
            else:
                maps_ctx[key] = entry
            log(f"map {mid}: {len(png) / 1e6:.2f} MB")
        def src(s, cols, kkt=True):
            lines = "existing HV and planned Koukoutamba lines" if kkt else "existing HV lines"
            return f"{s.scenario_id} Results file ({cols}); GADM 4.1 boundaries; {lines} from the study GIS inputs; batch {batch.name}; built {stamp}"
        add("map31", MP.status_map(primary.settlements, layers, "Electrification status in the start year", src(primary, "X_deg, Y_deg, ElecStart, PopStartYear", kkt=False), dpi=map_dpi),
            "Start-year electrification status after calibration.", src(primary, "X_deg, Y_deg, ElecStart, PopStartYear", kkt=False), "map-3-1", "3.1", "Start-year electrification status map")
        for i, s in enumerate(refs):
            nm = CASE_STUDY_NAME.get(s.demand_case, s.demand_case)
            png = MP.technology_map(s.settlements, 2040, layers, "Least-cost technology, 2040",
                                    f"{nm}: {CASE_DESCRIPTION.get(s.demand_case, '')}, grid cost {REFERENCE_COST} USD/kWh",
                                    src(s, "X_deg, Y_deg, FinalElecCode2040, Pop2040"), dpi=map_dpi)
            add(None, png, f"Least-cost technology per settlement in 2040, {nm} case.", src(s, "X_deg, Y_deg, FinalElecCode2040, Pop2040"),
                f"map-4-5-{s.demand_case}", f"4.5{'abcde'[i]}", f"Least-cost technology map 2040, {nm}", into=maps_ctx["ch4"])
        add("map61", MP.hydro_map(primary.settlements, layers, "Hydro mini-grids and small-hydro potential", src(primary, "X_deg, Y_deg, FinalElecCode2040, Pop2040"), dpi=map_dpi),
            f"Settlements served by hydro mini-grids in 2040 ({CASE_STUDY_NAME.get(primary.demand_case)} case) and the small-hydro potential sites.",
            src(primary, "X_deg, Y_deg, FinalElecCode2040, Pop2040") + "; Guinea_mini_hydro.gpkg", "map-6-1", "6.1", "Hydro mini-grid map")
        for i, case in enumerate([c for c in ("BU", "TD_Low") if c in ref_by_case]):
            s = ref_by_case[case]
            nm = CASE_STUDY_NAME.get(case, case)
            add(None, MP.two_panel_map(s.settlements, layers, f"Phasing of the least-cost technology, {nm} case", src(s, "X_deg, Y_deg, FinalElecCode2030, FinalElecCode2040"),
                                       subtitle=f"{CASE_DESCRIPTION.get(case, '')}, grid cost {REFERENCE_COST} USD/kWh", dpi=map_dpi),
                f"Least-cost technology in 2030 (70 percent access) and 2040 (universal access), {nm} case.",
                src(s, "X_deg, Y_deg, FinalElecCode2030, FinalElecCode2040"), f"map-7-1-{case}", f"7.1{'ab'[i]}", f"Two-panel phasing map, {nm}", into=maps_ctx["ch7"])
        if REFERENCE_COST in bu and max(bu) != REFERENCE_COST:
            add("map96", MP.switch_map(bu[REFERENCE_COST].settlements, bu[max(bu)].settlements, 2040, layers, f"{REFERENCE_COST} USD/kWh", f"{max(bu)} USD/kWh",
                                       "Technology switches with a higher grid cost", src(bu[max(bu)], "X_deg, Y_deg, FinalElecCode2040, Pop2040"), dpi=map_dpi),
                f"Settlements whose least-cost technology changes when the grid cost rises from {REFERENCE_COST} to {max(bu)} USD/kWh, bottom-up case.",
                src(bu[max(bu)], "X_deg, Y_deg, FinalElecCode2040, Pop2040"), "map-9-6", "9.6", "Technology switch map")
        bu_variants = batch.variants("BU")
        if REFERENCE_COST in bu and bu_variants:
            vname = "optgrid_optmg" if "optgrid_optmg" in bu_variants else next(iter(bu_variants))
            vs = bu_variants[vname]
            add("map97", MP.switch_map(bu[REFERENCE_COST].settlements, vs.settlements, 2040, layers, "the reference", VARIANT_LABELS.get(vname, vname).lower(),
                                       "Technology switches under the supply-side variant", src(vs, "X_deg, Y_deg, FinalElecCode2040, Pop2040"), dpi=map_dpi),
                f"Settlements whose least-cost technology changes under the variant '{VARIANT_LABELS.get(vname, vname)}', bottom-up case at {REFERENCE_COST} USD/kWh.",
                src(vs, "X_deg, Y_deg, FinalElecCode2040, Pop2040"), "map-9-7", "9.7b", "Technology switch map, supply-side variant")
        if corridor:
            add("map81", MP.corridor_map(primary.settlements, geo_attr, layers, corridor_km, "Koukoutamba corridor and affected areas",
                                         src(primary, "X_deg, Y_deg, FinalElecCode2040, Pop2040") + "; HV_KKT.shp; protected-area layers", dpi=map_dpi),
                f"Settlements within {corridor_km} km of the planned Linsan to Manantali line coloured by least-cost technology in 2040 ({CASE_STUDY_NAME.get(primary.demand_case)} case), with the affected localities and the protected areas crossed by the line.",
                src(primary, "X_deg, Y_deg, FinalElecCode2040, Pop2040") + "; HV_KKT.shp; protected-area layers", "map-8-1", "8.1", "Koukoutamba corridor map")

    # --- texts ------------------------------------------------------------------------
    hp = H[primary.demand_case]
    st_tot = start.loc["Total"]
    cost_desc = ", ".join(f"{c} ({COST_ROLE.get(c, 'other')})" for c in cost_levels)
    texts = {
        "scope_text": (f"The batch holds {len(batch.scenarios)} scenarios: {len(refs)} demand cases at the reference grid generation cost of {REFERENCE_COST} USD/kWh, "
                       f"and the Table 1 cases at {', '.join(str(c) for c in cost_levels if c != REFERENCE_COST)} USD/kWh. Every scenario runs on the same "
                       f"calibrated input of {n_settlements:,} settlements, the same {cap_conn:,},000 grid connections and {cap_mw} MW per year to {yr_mid}, "
                       f"a {disc * 100:.0f} percent discount rate and universal access in {yr_end} with a {target_mid * 100:.0f} percent interim target in {yr_mid}. "
                       f"Demand cases differ only through the residential tiers; the bottom-up case assigns a custom tier per settlement from GDP-PPP and poverty. "
                       f"The urban tier applies to the {n_urban} settlements the model classes as urban ({MS.fmt_people(urban_people)} people in {yr_end}), "
                       f"so the two top-down variants that change only the urban tier move demand and investment in those settlements alone."),
        "access_text": (f"After calibration to the national statistics, {MS.fmt_pct(st_tot['access_rate_start'])} of the {MS.fmt_people(st_tot['pop_start'])} people "
                        f"of 2025 live in settlements classed as electrified, in {int(st_tot['electrified_settlements']):,} of {int(st_tot['settlements']):,} settlements. "
                        f"Table 3.1 gives the regional picture; Table 3.2 lists the settlements that no scenario of the batch reaches with the grid by 2040, which are the "
                        f"communities for which decentralised options are the only route to access whatever the demand or the grid cost."),
        "reference_text": (f"At the reference grid cost the five demand cases reach the same population in 2040 ({MS.fmt_people(hp['population_2040'])}) with "
                           f"cumulative investment from {MS.fmt_musd(min(h['investment_musd_cum'] for h in H.values()))} to {MS.fmt_musd(max(h['investment_musd_cum'] for h in H.values()))}. "
                           f"Figures 4.1 to 4.4 show how the technology mix moves with the demand tier, the maps show where each technology is least cost, and Tables 4.2 "
                           f"and 4.3 break the results down by region and by urban and rural settlements."),
        "metrics_text": ("The proposal compares the options on three metrics: the delivered cost of electricity, the capital cost per new connection and the number of "
                         "people reached per million USD. Tables 5.1 to 5.3 give them by technology and demand case; Figure 5.1 the national values. Table 5.4 separates "
                         "the population already on the grid from the newly electrified settlements, where the comparison between grid extension and decentralised options "
                         "is actually made."),
        "lcoe_note": (f"The delivered LCOE of grid densification equals the grid generation cost ({REFERENCE_COST} USD/kWh) by construction, because settlements already "
                      f"electrified in 2025 are costed at the generation price without new network. The 'Total excl. densification' line therefore gives the delivered cost "
                      f"of the newly electrified settlements, which is the figure to compare with the Koukoutamba option."),
        "hydro_text": (f"Hydro mini-grids are only viable within 10 km of a small-hydro site of at most 1 MW (an upstream filter of the extraction). In the "
                       f"{CASE_STUDY_NAME.get(primary.demand_case)} case they serve {HY[primary.demand_case]['settlements']:,} settlements and "
                       f"{MS.fmt_people(HY[primary.demand_case]['people'])} people from {HY[primary.demand_case]['sites']} sites. The result is indicative: the potential "
                       f"layer gives capacity and location but no seasonal flow, so dry-season output is not represented."),
        "roadmap_text": (f"The 70 percent interim target sequences the roll-out: to 2030 the model connects {MS.fmt_people(hp['people_reached_cum'] - M.tech_table(primary.settlements, 2040).reindex(SERVED_CODES)['new_connections'].sum())} people for "
                         f"{MS.fmt_musd(hp['investment_musd_2030'])}, leaving {MS.fmt_people(hp['unserved_2030'])} people for the second period, which costs "
                         f"{MS.fmt_musd(hp['investment_musd_2040'])}. Table 7.1 gives the phasing by technology, Table 7.1b by region, and the two-panel maps show "
                         f"where the 2030 and 2040 frontiers fall."),
        "sensitivity_text": (f"The grid generation cost sweeps over {cost_desc} USD/kWh for the Table 1 cases; "
                             f"{hi_cost} USD/kWh is close to the unsubsidised production cost. Figures 9.1 to 9.4 trace the headline metrics, Table 9.1 isolates grid extension, "
                             f"which is the quantity that moves, and Table 9.2 and Figure 9.5 show which settlements switch and where they go. The demand variants "
                             f"({CASE_STUDY_NAME.get('TD_Low_minus')} and {CASE_STUDY_NAME.get('TD_High_plus')}) are compared with their base case in Table 9.3; "
                             f"{CASE_STUDY_NAME.get('TD_High_plus')} raises the urban tier only, which reaches the {n_urban} urban settlements and leaves the "
                             f"technology mix, the hydro sites and the cost of the newly electrified settlements unchanged."),
    }
    rules = ["Hydro mini-grids are only viable within 10 km of a hydro site: hard-coded in the model (max_hydro_dist) and recorded in every manifest.",
             "Mini-hydro sites above 1 MW are excluded upstream: the extraction used a layer filtered at 1 MW or below, so the hydro potential column holds 0 to 1,000 kW.",
             "The roll-out follows nationwide least cost (prioritisation 5); the model calls hard-code it.",
             "Diesel technologies and wind mini-grids are switched off; PV mini-grids are PV with battery."]
    caveats = ["The planned-HV layer used in the extraction is a copy of the existing network (PlannedHVLineDist equals CurrentHVLineDist everywhere), so the planned Koukoutamba line was never part of the model's grid. Chapter 8 measures the corridor from the line layer directly.",
               "The delivered LCOE of settlements already on the grid equals the grid generation cost by construction; national LCOE averages therefore track the cost input. Chapter 5 reports the newly electrified settlements separately.",
               "In 2030 the model leaves 30 percent of the population unserved by design (interim target); 2030 totals in the Summaries files count those people under 'Not yet electrified', and all per-connection metrics here use served settlements only.",
               "The earlier runs listed in Table 2.4 are superseded by this batch (the control file records why).",
               f"Population, urban ratio and electrification rates follow the calibration block (Table 2.3); the {yr_end} urban ratio of "
               f"{cal.get('urban_ratio_end_year', 0.45) * 100:.0f} percent is a working assumption to confirm.",
               f"Only {n_urban} settlements are classed as urban ({MS.fmt_people(urban_people)} people in {yr_end}); the urban tier therefore acts on those "
               f"settlements alone, and the urban and rural split of Table 4.3 compares those {n_urban} settlements with the rest of the country."]
    model_says = ["Where each technology is least cost at settlement level, for five demand cases and four grid costs (chapters 4 and 9).",
                  "The three comparison metrics by technology, region and urban or rural area (chapter 5), and the settlements never reached by the grid (chapter 3).",
                  "The phasing of connections, capacity and investment between 2030 and 2040 (chapter 7).",
                  "The settlements, people, investment and delivered cost inside the Koukoutamba corridor, the affected localities and the protected areas (chapter 8).",
                  "How much of the result depends on the grid cost assumption, and which settlements switch (chapter 9): the evidence for the subsidised against unsubsidised comparison."]
    model_does_not_say = ["Tariffs, affordability and ability to pay: the model costs supply, not what households are charged.",
                          "Financing structure, public against private capital, and the cost of capital beyond the single 8 percent discount rate.",
                          "The Koukoutamba plant's capacity, cost, dry-season firm output and transmission corridor cost: those enter the paired scenario, not this batch.",
                          "Institutional, regulatory and operational barriers, and the quality of imported solar equipment.",
                          "Seasonal hydro output: the small-hydro layer gives capacity and location only."]
    method_notes = ["Served rows in a year: FinalElecCode below 99 and NewConnections above 0. Population by technology counts every settlement carrying the code; connections, capacity and investment count served settlements only.",
                    "Cumulative values add the 2030 and 2040 periods; a settlement is attributed to its technology in each period.",
                    "USD per newly connected person = cumulative investment / cumulative new connections; people per million USD is its inverse.",
                    "Delivered LCOE = the LCOE of the chosen technology, weighted by the settlement's annual energy (or population), over served settlements with an LCOE below 99.",
                    "Switching: settlements joined on id between the reference and the alternative cost; a switch is a different FinalElecCode2040.",
                    "Corridor distances in EPSG:32629 (UTM 29N) to the Linsan to Manantali feature of HV_KKT.shp; membership of polygons by point-in-polygon.",
                    "Maps: GADM 4.1 boundaries, Guinea only; stand-alone systems drawn first, mini-grids, then grid on top; legends give settlement counts and population shares."]

    summaries = [{"id": s.scenario_id, "label": s.label,
                  "html": table_html(s.summaries, {c: F_INT if "Population" in c or "Connections" in c else F_2 for c in s.summaries.columns}, index_label="Technology")}
                 for s in batch.scenarios.values()]

    prov = batch.provenance()
    prov["model_seconds_min"] = round(prov["model_seconds"] / 60, 1)
    rc, rdirty = _git(repo_root)
    v = _versions()
    build_info = {"report_commit": rc, "report_dirty": rdirty, "timestamp": stamp, "consistency": consistency, "sample": sample,
                  "n_settlements": n_settlements, **v}
    context = {"title": "Guinea decentralised electrification study: scenario results",
               "subtitle": f"Least-cost electrification of {n_settlements:,} settlements, {len(batch.scenarios)} scenarios, batch {batch.name}",
               "chapters": CHAPTERS, "prov": prov, "build": build_info, "kpis": kpis, "key_messages": key_messages, "tables": T,
               "rules": rules, "caveats": caveats, "maps": maps_ctx, "n_settlements": f"{n_settlements:,}", "reference_cost": REFERENCE_COST,
               "figs": figs, "corridor": corridor, "corridor_text": corridor_text, "corridor_note": corridor_note,
               "model_says": model_says, "model_does_not_say": model_does_not_say, "summaries": summaries, "method_notes": method_notes,
               "variant_names": variant_names, "variant_labels": VARIANT_LABELS, "bins_ok": bins_ok,
               "bins_text": (f"The {CASE_STUDY_NAME.get(bins_case, bins_case)} case is run at {len(bins_costs)} grid generation cost levels "
                             f"({', '.join(str(c) for c in bins_costs)} USD/kWh). The heat maps show how the technology mix moves with the cost of "
                             f"grid electricity, on the two bases of chapter 4: the 2040 population, where the people already on the grid dominate, and the "
                             f"new connections of 2025 to 2040, where the decentralised impact shows; Figure 9.10 gives the regional picture and Table 9.5 the "
                             f"headline metrics per level.") if bins_ok else "",
               "variants_text": (f"Two supply-side variants are run for the Table 1 cases at the reference grid cost: full grid expansion "
                                 f"(the {cap_conn:,},000 connections and {cap_mw} MW per year caps to {yr_mid} removed) and, on top of it, "
                                 f"mini-grid PV panels 25 percent cheaper (factor 0.75 on the panel cost of the PV-battery mini-grid; battery and "
                                 f"inverter unchanged). Table 9.4 compares each variant with its reference scenario; Figure 9.8 shows the changes; "
                                 f"the switch map shows where the bottom-up case changes technology.") if variant_names else "",
               "batch_log": batch.batch_log, "checks_md": batch.checks_md, "plotly_js": F.plotly_js(), **texts}
    html = render(context)
    out_path.write_text(html, encoding="utf-8")
    for f in figs["ch4"] + figs["ch9"] + figs["ch9b"] + [figs["f46"], figs["f51"], figs["f72"]]:
        assets[f.get("id", "fig")] = len(f["div"].encode("utf-8"))
    assets["plotly_js"] = len(context["plotly_js"].encode("utf-8"))
    manifest = {"batch": batch.name, "batch_dir": str(batch_dir), "n_scenarios": len(batch.scenarios), "n_settlements": n_settlements,
                "sample": sample, "consistency": consistency, "html": str(out_path), "html_bytes": out_path.stat().st_size,
                "assets": assets, "inputs_dir": str(inputs_dir) if inputs_dir else None, "corridor_km": corridor_km,
                "map_dpi": map_dpi, "map_colours": map_colours, "report_commit": rc, "report_dirty": rdirty, "built": stamp,
                "seconds": round(time.time() - t0, 1), "provenance": prov, **v}
    (out_dir / "build_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    log(f"wrote {out_path} ({out_path.stat().st_size / 1e6:.1f} MB) in {manifest['seconds']} s")
    return out_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("batch", help="batch folder under GuineaRuns/Outputs")
    ap.add_argument("--out", help="output HTML path (default <batch>/report/guinea_scenarios_report_<batch>.html)")
    ap.add_argument("--inputs", help="GIS inputs folder (Guinea Data) for maps and the corridor chapter")
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--no-maps", action="store_true")
    ap.add_argument("--no-geo", action="store_true")
    ap.add_argument("--corridor-km", type=float, default=10)
    ap.add_argument("--map-dpi", type=int, default=150)
    ap.add_argument("--map-colours", type=int, default=DEFAULT_MAP_COLOURS,
                    help="palette-quantise map PNGs to this many colours (0 = off)")
    ap.add_argument("--sample", type=int, default=0, help="build on a random sample of N settlements (seed 42), for checks")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--allow-inconsistent", action="store_true")
    a = ap.parse_args(argv)
    id_subset = None
    sample = False
    if a.sample:
        from report.data import discover_scenarios, load_settlements
        first = discover_scenarios(Path(a.batch))[0]
        ids = load_settlements(first, Path(a.batch) / "report" / "cache")["id"]
        id_subset = ids.sample(n=min(a.sample, len(ids)), random_state=42).to_numpy()
        sample = True
    build(a.batch, a.repo, out_path=a.out, inputs_dir=a.inputs, id_subset=id_subset, maps=not a.no_maps, geo=not a.no_geo,
          corridor_km=a.corridor_km, map_dpi=a.map_dpi, map_colours=a.map_colours, sample=sample, use_cache=not a.no_cache,
          allow_inconsistent=a.allow_inconsistent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
