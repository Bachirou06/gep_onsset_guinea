from pathlib import Path

import pytest

STUDY = Path(__file__).resolve().parents[1] / "Scenarios" / "guinea_scenarios.json"
REGRESSION = Path(__file__).resolve().parents[1] / "Scenarios" / "regression_u3r1.json"

EXPECTED_ORDER = [
    "TD_Low_g0.1", "TD_Low_minus_g0.1", "TD_High_g0.1", "TD_High_plus_g0.1", "BU_g0.1",
    "TD_Low_g0.047", "TD_High_g0.047", "BU_g0.047",
    "TD_Low_g0.078", "TD_High_g0.078", "BU_g0.078",
    "TD_Low_g0.22", "TD_High_g0.22", "BU_g0.22",
]


@pytest.fixture
def sc(gep_path):
    import scenario_control
    return scenario_control


VARIANT_IDS = ["TD_Low_optgrid_g0.1", "TD_Low_optgrid_optmg_g0.1", "TD_High_optgrid_g0.1", "TD_High_optgrid_optmg_g0.1",
               "BU_optgrid_g0.1", "BU_optgrid_optmg_g0.1"]


KEY_IDS = ["TD_High_minus_g0.1", "TD_High_minus_g0.047", "TD_High_minus_g0.078", "TD_High_minus_g0.22",
           "TD_High_minus_optgrid_g0.1", "TD_High_minus_optgrid_optmg_g0.1", "TD_Low_minus_g0.047", "TD_Low_minus_g0.078",
           "TD_Low_minus_g0.22", "TD_Low_minus_optgrid_g0.1", "TD_Low_minus_optgrid_optmg_g0.1"]


def test_study_file_loads_fourteen_in_order_then_the_supply_variants(sc):
    c = sc.load_control(STUDY, check_paths=False)
    assert c.ids()[:14] == EXPECTED_ORDER
    assert c.ids()[14:20] == VARIANT_IDS
    assert set(c.ids()[20:]) >= set(KEY_IDS)
    assert {f"BU_g{b}" for b in (0.06, 0.12, 0.14, 0.16, 0.18, 0.2, 0.25)} <= set(c.ids())
    p = c.resolved("TD_High_minus_g0.1")
    assert (p["urban_target_tier"], p["rural_target_tier"], p["grid_generation_cost"]) == (4, 2, 0.1)
    assert c.resolved("TD_High_minus_g0.22")["grid_generation_cost"] == 0.22
    assert c.resolved("TD_Low_minus_optgrid_optmg_g0.1")["mg_pv_hybrid_cost_factor"] == 0.75
    for sid in VARIANT_IDS:
        s = c.scenario(sid)
        p = c.resolved(sid)
        assert s.variant in ("optgrid", "optgrid_optmg") and p["grid_generation_cost"] == 0.1
        assert p["annual_new_grid_connections_limit_intermediate"] == 999999999
        assert p["annual_grid_cap_gen_limit_intermediate"] == 999999999
        assert p["mg_pv_hybrid_cost_factor"] == (0.75 if s.variant == "optgrid_optmg" else 1)
    assert all(c.scenario(sid).variant == "reference" for sid in EXPECTED_ORDER)


@pytest.mark.parametrize("sid,ut,rt,gc", [
    ("TD_Low_g0.1", 3, 2, 0.1), ("TD_Low_minus_g0.1", 3, 1, 0.1), ("TD_High_g0.1", 4, 3, 0.1),
    ("TD_High_plus_g0.1", 5, 3, 0.1), ("BU_g0.1", 6, 6, 0.1), ("BU_g0.22", 6, 6, 0.22),
    ("TD_High_g0.047", 4, 3, 0.047), ("TD_Low_g0.078", 3, 2, 0.078),
])
def test_study_levers(sc, sid, ut, rt, gc):
    p = sc.load_control(STUDY, check_paths=False).resolved(sid)
    assert (p["urban_target_tier"], p["rural_target_tier"], p["grid_generation_cost"]) == (ut, rt, gc)


def test_study_reference_scenarios_do_not_override_cost(sc):
    c = sc.load_control(STUDY, check_paths=False)
    for sid in EXPECTED_ORDER[:5]:
        assert "grid_generation_cost" not in c.scenario(sid).overrides


def test_study_defaults_pin_table1_assumptions(sc):
    d = sc.load_control(STUDY, check_paths=False).defaults
    assert d["annual_new_grid_connections_limit_intermediate"] == 127
    assert d["annual_grid_cap_gen_limit_intermediate"] == 90
    assert d["discount_rate"] == 0.08 and d["grid_generation_cost"] == 0.1
    assert d["grid_losses"] == 0.167 and d["pop_threshold"] == 0
    assert d["tech_switches"] == {"sa_pv": 1, "mg_hydro": 1, "mg_pv": 0, "mg_pv_hybrid": 1,
                                  "mg_wind_hybrid": 0}
    assert d["diesel_techs"] == 0 and d["productive_preference"] == "Low"


def test_study_calibration_block(sc):
    cal = sc.load_control(STUDY, check_paths=False).calibration
    assert cal["end_year_pop"] == 27697655 and cal["urban_ratio_end_year"] == 0.45
    assert cal["urban_ratio_start_year"] == 0.387 and cal["min_pop"] == 50


def test_study_paths_point_at_confirmed_input_and_profiles(sc):
    c = sc.load_control(STUDY, check_paths=False)
    assert c.paths["raw_input_csv"].name == "OnSSET_InputFile_20261018_100416.csv"
    assert c.paths["pv_profile"].name == "gn-2-pv.csv" and c.paths["wind_profile"].name == "gn-2-wind.csv"
    assert c.paths["productive_matrix"].name == "productive_uses_matrix.json"


def test_study_meta_records_superseded_runs_and_hydro_rules(sc):
    m = sc.load_control(STUDY, check_paths=False).meta
    notes = " ".join(m["notes"])
    assert "10 km" in notes and "1 MW" in notes
    assert "D2_BOT_0.047_1_10km_H_GL127" in m["superseded_runs"]
    assert len(m["superseded_runs"]) == 5


def test_study_labels_state_grid_cost_role(sc):
    c = sc.load_control(STUDY, check_paths=False)
    assert "reference" in c.scenario("BU_g0.1").label
    assert "low variant" in c.scenario("BU_g0.078").label
    assert "high variant" in c.scenario("BU_g0.22").label
    assert "legacy" in c.scenario("BU_g0.047").label


def test_regression_file(sc):
    c = sc.load_control(REGRESSION, check_paths=False)
    assert c.ids() == ["REF_U3R1_g0.047"]
    p = c.resolved("REF_U3R1_g0.047")
    assert (p["urban_target_tier"], p["rural_target_tier"], p["grid_generation_cost"]) == (3, 1, 0.047)
    assert c.calibration["urban_ratio_start_year"] == 0.45 and c.calibration["urban_ratio_end_year"] == 0.453
    assert c.scenario("REF_U3R1_g0.047").legacy_name == "Scenario_U3R1_0.047"
    assert c.paths["calibrated_csv"].name == "GIN_calibrated.csv"
