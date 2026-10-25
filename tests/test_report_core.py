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
        assert (case, 0.22) in core and (case, 0.1) in core
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
