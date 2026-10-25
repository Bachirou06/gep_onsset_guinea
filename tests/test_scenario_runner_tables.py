from pathlib import Path

import pandas as pd
import pytest

STUDY = Path(__file__).resolve().parents[1] / "Scenarios" / "guinea_scenarios.json"


@pytest.fixture
def mods(gep_path):
    import scenario_control
    import scenario_runner
    return scenario_control, scenario_runner


def test_build_technologies_keys_and_values(mods):
    sc, sr = mods
    p = sc.load_control(STUDY, check_paths=False).resolved("BU_g0.1")
    t = sr.build_technologies(p)
    assert set(t) >= {"grid", "mg_pv_hybrid", "mg_wind_hybrid", "mg_hydro", "mg_wind", "mg_pv",
                      "sa_pv", "mg_diesel", "sa_diesel", "sa_diesel_cost", "mg_diesel_cost"}
    assert t["grid"].grid_price == 0.1 and t["grid"].distribution_losses == 0.167
    assert t["grid"].grid_capacity_investment == 1363
    assert t["sa_pv"].capital_cost[0.020] == 9620 * p["pv_adjustment_factor"]
    assert t["mg_hydro"].capital_cost == {float("inf"): 3000}
    assert t["sa_diesel_cost"] == {"diesel_price": 0.5, "efficiency": 0.28,
                                   "diesel_truck_consumption": 14, "diesel_truck_volume": 300}


def test_build_technologies_uses_overridden_grid_cost(mods):
    sc, sr = mods
    p = sc.load_control(STUDY, check_paths=False).resolved("BU_g0.22")
    assert sr.build_technologies(p)["grid"].grid_price == 0.22


def test_tech_constants_hold_cell32_literals(mods):
    _, sr = mods
    c = sr.TECH_CONSTANTS
    assert c["grid"]["connection_cost_per_hh"] == 125 and c["grid"]["tech_life"] == 30
    assert c["mg_pv_hybrid"]["capacity_factor"] == 0.5 and c["sa_pv"]["tech_life"] == 15
    assert c["sa_pv"]["capital_cost_bins"] == [0.020, 0.050, 0.100, 1, 5]


def _frame():
    years = [2030, 2040]
    df = pd.DataFrame({"id": [1, 2, 3], "FinalElecCode2030": [1, 3, 99], "FinalElecCode2040": [1, 3, 5]})
    for y in years:
        df[f"Pop{y}"] = [1000.0, 200.0, 50.0]
        df[f"NewConnections{y}"] = [500.0, 200.0, 0.0 if y == 2030 else 50.0]
        df[f"NewCapacity{y}"] = [2000.0, 100.0, 0.0 if y == 2030 else 20.0]
        df[f"InvestmentCost{y}"] = [3.0e6, 1.0e6, 0.0 if y == 2030 else 2.0e5]
    return df


def test_summary_table_shape_and_totals(mods):
    _, sr = mods
    tbl = sr.summary_table(_frame(), [2030, 2040], cost_choice=2)
    assert list(tbl.index) == ["Grid_dens", "Grid_ext", "SA_PV", "MG_PV_Battery", "MG_Hydro",
                               "Non-electrified", "Total"]
    assert list(tbl.columns) == ["Population2030", "NewConnections2030", "Capacity2030 (MW)",
                                 "Investment2030 (million USD)", "Population2040",
                                 "NewConnections2040", "Capacity2040 (MW)",
                                 "Investment2040 (million USD)"]
    assert tbl.loc["Grid_dens", "Population2030"] == 1000 and tbl.loc["SA_PV", "Population2030"] == 200
    assert tbl.loc["Non-electrified", "Population2030"] == 50 and tbl.loc["Total", "Population2030"] == 1250
    assert tbl.loc["MG_PV_Battery", "Capacity2040 (MW)"] == 0.02
    assert tbl.loc["Total", "Investment2040 (million USD)"] == 4.2


def test_variables_table_has_notebook_rows_then_hidden_levers(mods):
    sc, sr = mods
    c = sc.load_control(STUDY, check_paths=False)
    s = c.scenario("BU_g0.078")
    p = c.resolved(s.id)
    df = sr.variables_table(c, s, p, sr.build_technologies(p),
                            extra={"calibrated_csv_sha256": "abc", "scenario_id": s.id})
    assert df.columns.tolist() == ["Variable", "Value", "Source", "Comments", "Description"]
    assert df.Variable.iloc[0] == "Start_year" and "GIS data: Wind velocity" in df.Variable.values
    v = df.set_index("Variable").Value
    assert v["grid_generation_cost"] == 0.078 and v["Rural target tier"] == 6
    assert v["pop_end_year"] == 27697655 and v["base_to_peak"] == 0.8
    assert v["max_grid_extension_dist"] == 50
    for key in ("tech_switches", "diesel_techs", "productive_preference", "tier_1", "tier_5",
                "cost_choice", "hydro_viability_km", "hydro_site_filter", "control_file_sha256",
                "calibrated_csv_sha256", "scenario_id", "legacy_name"):
        assert key in v.index, key
    assert v["hydro_viability_km"] == 10 and v["calibrated_csv_sha256"] == "abc"
    assert v["control_file_sha256"] == c.sha256
