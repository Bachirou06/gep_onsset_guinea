"""The final scenario set: three key cases x three grid-cost regimes as the report's core."""
import pandas as pd
import pytest

from report import constants as C


def test_core_constants():
    assert C.REGIME_ORDER == [0.22, 0.085, 0.1] and C.PRIMARY_COST == 0.22
    assert C.REGIME_NAME == {0.22: "Cost-reflective", 0.085: "Hydro cost", 0.1: "Current tariff"}
    assert C.REGIME_KEY == {0.22: "cost_reflective", 0.085: "hydro_cost", 0.1: "current_tariff"}
    assert all(cost in C.REGIME_SOURCE for cost in C.REGIME_ORDER)
    assert C.CORE_CELLS == [(case, cost) for case in C.KEY_CASES for cost in C.REGIME_ORDER]
    assert len(C.CORE_CELLS) == 9
    assert C.COST_LEVELS == [0.047, 0.078, 0.085, 0.1, 0.22] and C.REFERENCE_COST == 0.1
    assert C.COST_ROLE[0.085]


def test_core_label_format():
    assert C.core_label("BU", 0.22) == "BU, Cost-reflective"
    assert C.core_label("TD_Low_minus", 0.085) == "U3R1, Hydro cost"
    assert C.core_label("TD_High_minus", 0.1) == "U4R2, Current tariff"


def test_batch_core_returns_present_cells_in_order(report_sample_batch, repo_root, tmp_path):
    from report.data import load_batch
    b = load_batch(report_sample_batch, repo_root, cache_dir=tmp_path / "cache", log=lambda *a: None)
    core = b.core()
    keys = list(core)
    assert keys == [k for k in C.CORE_CELLS if k in core]                 # CORE_CELLS order
    for case in C.KEY_CASES:
        assert (case, 0.22) in core and (case, 0.1) in core and (case, 0.085) in core
        assert core[(case, 0.22)].grid_cost == 0.22 and core[(case, 0.22)].variant == "reference"
    labels = b.core_labels()
    assert list(labels) == keys and labels[("BU", 0.22)] == "BU, Cost-reflective"


# --- Task 2: core metric builders -------------------------------------------------------
def test_core_headlines_keys_are_core_labels(report_sample_batch, repo_root, tmp_path):
    from report import metrics as M
    from report.data import load_batch
    b = load_batch(report_sample_batch, repo_root, cache_dir=tmp_path / "cache", log=lambda *a: None)
    ch = M.core_headlines(b)
    assert list(ch) == [C.core_label(*k) for k in b.core()]
    assert "BU, Cost-reflective" in ch and ch["BU, Cost-reflective"]["investment_musd_cum"] > 0


def test_regime_switch_table_rows_and_flow_shape(report_sample_batch, repo_root, tmp_path):
    from report import metrics as M
    from report.data import load_batch
    b = load_batch(report_sample_batch, repo_root, cache_dir=tmp_path / "cache", log=lambda *a: None)
    t = M.regime_switch_table(b)
    assert list(t.columns) == ["demand_case", "from_cost", "to_cost", "settlements", "people", "flows"]
    assert (t["from_cost"] == C.PRIMARY_COST).all()
    assert set(t["to_cost"]) <= {0.085, 0.1} and set(t["demand_case"]) <= set(C.KEY_CASES)
    assert ((t["demand_case"] == "BU") & (t["to_cost"] == 0.1)).any()
    for flows in t["flows"]:
        assert isinstance(flows, list) and len(flows) <= 3
        for f in flows:
            assert len(f) == 3 and f[0] in C.SERVED_CODES and f[1] in C.SERVED_CODES and f[2] >= 0


def test_variant_comparison_covers_every_regime_present(report_sample_batch, repo_root, tmp_path):
    from report import metrics as M
    from report.data import load_batch
    b = load_batch(report_sample_batch, repo_root, cache_dir=tmp_path / "cache", log=lambda *a: None)
    vc = M.variant_comparison(b)
    assert "grid_cost" in vc.columns and set(vc["grid_cost"]) <= set(C.REGIME_ORDER)
    assert "dre_share_new_connections" in set(vc["metric"])
    vc1 = M.variant_comparison(b, grid_costs=[0.1])
    assert set(vc1["grid_cost"]) == {0.1} and len(vc1) < len(vc) or set(vc["grid_cost"]) == {0.1}


def test_variant_summary_columns():
    from report import metrics as M
    rows = []
    for metric, ref, var in [("investment_musd_cum", 2307.4, 2299.9), ("grid_ext_people_2040", 3005238.0, 2504332.0),
                             ("mg_pv_people_2040", 2085423.0, 2655447.0), ("dre_share_new_connections", 0.331, 0.36),
                             ("lcoe_energy_w_excl_dens", 0.238, 0.234), ("capacity_mw_cum", 792.4, 816.4)]:
        rows.append({"demand_case": "BU", "grid_cost": 0.22, "variant": "optgrid_optmg", "scenario_id": "x", "metric": metric,
                     "reference": ref, "variant_value": var, "delta_abs": var - ref, "delta_pct": (var - ref) / ref * 100})
    vs = M.variant_summary(pd.DataFrame(rows))
    assert list(vs.index.names) == ["demand_case", "grid_cost", "variant"]
    for m in M.SUMMARY_METRICS:
        assert {f"{m}_ref", f"{m}_var", f"{m}_pct"} <= set(vs.columns)
    assert "capacity_mw_cum_ref" not in vs.columns
    r = vs.loc[("BU", 0.22, "optgrid_optmg")]
    assert r["mg_pv_people_2040_pct"] == pytest.approx(27.3, abs=0.1) and r["investment_musd_cum_var"] == 2299.9


# --- Task 3: key messages over the core matrix ---------------------------------------------
def _h(**over):
    base = {"investment_musd_cum": 2000.0, "people_reached_cum": 18.3e6, "usd_per_new_connection": 110.0,
            "people_per_musd": 9000.0, "lcoe_energy_w": 0.15, "lcoe_energy_w_excl_dens": 0.25, "grid_ext_people_2040": 3.0e6,
            "dre_share_new_connections": 0.33, "investment_musd_2030": 500.0, "investment_musd_2040": 1500.0,
            "unserved_2030": 6.1e6, "grid_share_2040": 0.78, "mg_pv_people_2040": 2.0e6,
            "new_connections_by_tech": {1: 3e6, 2: 3e6, 3: 4e6, 5: 2e6, 7: 0.1e6}, "grid_ext_share_new_connections": 0.16,
            "dre_share_pop_2040": 0.22}
    base.update(over)
    return base


def _core_h():
    return {"U3R1, Cost-reflective": _h(investment_musd_cum=1400.0, grid_ext_people_2040=0.2e6, dre_share_new_connections=0.52),
            "U3R1, Hydro cost": _h(investment_musd_cum=1350.0, grid_ext_people_2040=0.6e6, dre_share_new_connections=0.47),
            "U3R1, Current tariff": _h(investment_musd_cum=1345.0, grid_ext_people_2040=0.3e6, dre_share_new_connections=0.49),
            "BU, Cost-reflective": _h(investment_musd_cum=2384.6, grid_ext_people_2040=3872.0, dre_share_new_connections=0.495),
            "BU, Hydro cost": _h(investment_musd_cum=2310.0, grid_ext_people_2040=3.5e6, dre_share_new_connections=0.30),
            "BU, Current tariff": _h(investment_musd_cum=2307.4, grid_ext_people_2040=3.0e6, dre_share_new_connections=0.331)}


def test_minmax_messages_name_core_labels():
    from report import messages as MS
    m = MS.km_investment_range(_core_h())
    assert "U3R1, Current tariff" in m["text"] and "BU, Cost-reflective" in m["text"]
    assert "demand case" not in m["text"]
    m2 = MS.km_cost_per_connection({"BU, Cost-reflective": _h(usd_per_new_connection=130.0), "U3R1, Hydro cost": _h(usd_per_new_connection=70.0)})
    assert "U3R1, Hydro cost" in m2["text"] and "BU, Cost-reflective" in m2["text"]


def test_km_regime_effect_names_regimes_and_directions():
    from report import messages as MS
    sw = pd.DataFrame([{"demand_case": "BU", "from_cost": 0.22, "to_cost": 0.085, "settlements": 1300, "people": 3.4e6, "flows": [(5, 2, 3.0e6), (3, 2, 0.4e6)]},
                       {"demand_case": "BU", "from_cost": 0.22, "to_cost": 0.1, "settlements": 1303, "people": 3.0e6, "flows": [(5, 2, 2.9e6)]},
                       {"demand_case": "TD_Low_minus", "from_cost": 0.22, "to_cost": 0.085, "settlements": 200, "people": 0.4e6, "flows": [(5, 2, 0.4e6)]},
                       {"demand_case": "TD_Low_minus", "from_cost": 0.22, "to_cost": 0.1, "settlements": 0, "people": 0.0, "flows": []}])
    m = MS.km_regime_effect(_core_h(), sw)
    t = m["text"]
    assert m["id"] == "km-regime" and "BU" in t and "U3R1" in t and "U4R2" not in t
    assert "hydro-cost regime" in t.lower() or "hydro cost" in t.lower()
    assert "3.4 million people" in t and "mini-grid PV with battery to grid extension" in t
    assert "no settlement changes technology" in t            # U3R1 at the current tariff
    assert "nan" not in t.lower().split()


def test_km_supply_variants_filters_on_primary_cost():
    from report import messages as MS
    rows = []
    for cost, mg in ((0.22, 900000.0), (0.1, 570024.0)):
        for metric, ref, dabs in [("investment_musd_cum", 2300.0, -7.0), ("grid_share_2040", 0.78, -0.02), ("mg_pv_people_2040", 2.0e6, mg)]:
            rows.append({"demand_case": "BU", "grid_cost": cost, "variant": "optgrid_optmg", "scenario_id": "x", "metric": metric,
                         "reference": ref, "variant_value": ref + dabs, "delta_abs": dabs, "delta_pct": dabs / ref * 100})
    vc = pd.DataFrame(rows)
    m = MS.km_supply_variants(vc)
    assert "900,000 people" in m["text"] and "570,000" not in m["text"] and "cost-reflective" in m["text"].lower()
    m2 = MS.km_supply_variants(vc, grid_cost=0.1)
    assert "570,000 people" in m2["text"] and "current tariff" in m2["text"].lower()


def test_key_messages_accepts_core_inputs():
    from report import messages as MS
    primary = {"TD_Low_minus": _h(), "BU": _h()}
    sw = pd.DataFrame(columns=["demand_case", "from_cost", "to_cost", "settlements", "people", "flows"])
    msgs = MS.key_messages(_core_h(), None, {}, {"BU": {"sites": 30, "settlements": 60, "people": 70011.0, "capacity_mw": 3.2}},
                           None, switch_df=sw, primary_h=primary)
    ids = [m["id"] for m in msgs]
    assert ids[0] == "km-investment" and "km-regime" not in ids and "km-mix" in ids and "km-hydro" in ids
    sw2 = pd.DataFrame([{"demand_case": "BU", "from_cost": 0.22, "to_cost": 0.1, "settlements": 1, "people": 10.0, "flows": [(5, 2, 10.0)]}])
    ids2 = [m["id"] for m in MS.key_messages(_core_h(), None, {}, {}, None, switch_df=sw2, primary_h=primary)]
    assert ids2[1] == "km-regime"
