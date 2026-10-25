import json
from pathlib import Path

import pytest

DEFAULTS = {
    "start_year": 2025, "end_year": 2040, "intermediate_year": 2030,
    "electrification_rate_target": 1, "intermediate_electrification_target": 0.7,
    "urban_target_tier": 6, "rural_target_tier": 6,
    "num_people_per_hh_urban": 6.6, "num_people_per_hh_rural": 6.3,
    "prioritization": 5, "auto_intensification": 0,
    "annual_new_grid_connections_limit_intermediate": 127,
    "annual_new_grid_connections_limit_end": 999999999,
    "annual_grid_cap_gen_limit_intermediate": 90, "annual_grid_cap_gen_limit_end": 999999999,
    "grid_generation_cost": 0.1, "grid_power_plants_capital_cost": 1363, "grid_losses": 0.167,
    "existing_grid_cost_ratio": 0.1, "pv_adjustment_factor": 1, "discount_rate": 0.08,
    "pop_threshold": 0, "diesel_price": 0.5, "diesel_techs": 0,
    "tech_switches": {"sa_pv": 1, "mg_hydro": 1, "mg_pv": 0, "mg_pv_hybrid": 1, "mg_wind_hybrid": 0},
    "sa_diesel_capital_cost": {"inf": 938}, "mg_diesel_capital_cost": {"inf": 721},
    "mg_pv_capital_cost": {"inf": 2950}, "mg_wind_capital_cost": {"inf": 3750},
    "mg_hydro_capital_cost": {"inf": 3000},
    "sa_pv_capital_cost_1": 9620, "sa_pv_capital_cost_2": 8780, "sa_pv_capital_cost_3": 6380,
    "sa_pv_capital_cost_4": 4470, "sa_pv_capital_cost_5": 6950,
    "hv_line_capacity": 69, "hv_line_cost": 53000, "mv_line_cost": 7000, "mv_line_capacity": 33,
    "mv_line_max_length": 50, "mv_increase_rate": 0.1, "max_mv_line_dist": 50,
    "MV_line_amperage_limit": 8, "lv_line_capacity": 0.24, "lv_line_max_length": 0.5,
    "lv_line_cost": 4250, "service_Transf_type": 50, "service_Transf_cost": 4250,
    "max_nodes_per_serv_trans": 300, "hv_lv_transformer_cost": 25000,
    "hv_mv_transformer_cost": 25000, "mv_lv_transformer_cost": 10000,
    "mv_mv_transformer_cost": 10000,
    "tier_1": 38.7, "tier_2": 219, "tier_3": 803, "tier_4": 2117, "tier_5": 2993,
    "productive_demand": 1, "productive_preference": "Low", "cost_choice": 2,
}

CALIBRATION = {
    "pop_start_year": 17521167, "end_year_pop": 27697655,
    "urban_ratio_start_year": 0.387, "urban_ratio_end_year": 0.45,
    "elec_ratio_start_year": 0.538, "urban_elec_ratio": 0.91, "rural_elec_ratio": 0.23,
    "min_night_lights": 0, "min_pop": 50, "max_service_transformer_distance": 2,
    "max_mv_line_distance": 2, "max_hv_line_distance": 5,
}


def minimal_control(tmp_path, defaults_extra=None, scenarios=None, scenario_overrides=None,
                    paths_patch=None):
    defaults = dict(DEFAULTS)
    defaults.update(defaults_extra or {})
    overrides = {"urban_target_tier": 3, "rural_target_tier": 2, "grid_generation_cost": 0.047}
    overrides.update(scenario_overrides or {})
    paths = {
        "raw_input_csv": "raw.csv", "calibrated_csv": "cal.csv", "pv_profile": "pv.csv",
        "wind_profile": "wind.csv", "productive_matrix": "matrix.json", "output_root": "out",
    }
    paths.update(paths_patch or {})
    doc = {
        "meta": {"schema_version": "1.0", "study": "test", "created": "2026-10-24", "notes": []},
        "paths": paths,
        "calibration": CALIBRATION,
        "defaults": defaults,
        "scenarios": scenarios if scenarios is not None else [
            {"id": "S1", "demand_case": "TD_Low", "label": "test", "overrides": overrides}],
    }
    d = tmp_path / "Scenarios"
    d.mkdir(exist_ok=True)
    p = d / "control.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


@pytest.fixture
def sc(gep_path):
    import scenario_control
    return scenario_control


def test_resolved_applies_overrides(sc, tmp_path):
    c = sc.load_control(minimal_control(tmp_path), check_paths=False)
    p = c.resolved("S1")
    assert p["urban_target_tier"] == 3 and p["grid_generation_cost"] == 0.047
    assert p["discount_rate"] == 0.08


def test_cost_dict_converted(sc, tmp_path):
    c = sc.load_control(minimal_control(tmp_path), check_paths=False)
    assert c.resolved("S1")["mg_pv_capital_cost"] == {float("inf"): 2950}


def test_unknown_default_key_rejected(sc, tmp_path):
    with pytest.raises(sc.ControlError, match="unknown key 'grid_lossess'"):
        sc.load_control(minimal_control(tmp_path, defaults_extra={"grid_lossess": 0.1}),
                        check_paths=False)


def test_missing_default_key_rejected(sc, tmp_path):
    p = minimal_control(tmp_path)
    doc = json.loads(p.read_text())
    del doc["defaults"]["discount_rate"]
    p.write_text(json.dumps(doc))
    with pytest.raises(sc.ControlError, match="missing key 'discount_rate'"):
        sc.load_control(p, check_paths=False)


def test_duplicate_id_rejected(sc, tmp_path):
    s = {"id": "S1", "demand_case": "TD_Low", "label": "t", "overrides": {}}
    with pytest.raises(sc.ControlError, match="duplicate scenario id 'S1'"):
        sc.load_control(minimal_control(tmp_path, scenarios=[s, dict(s)]), check_paths=False)


def test_unsafe_id_rejected(sc, tmp_path):
    s = {"id": "TD Low/g0.1", "demand_case": "TD_Low", "label": "t", "overrides": {}}
    with pytest.raises(sc.ControlError, match="not filename-safe"):
        sc.load_control(minimal_control(tmp_path, scenarios=[s]), check_paths=False)


def test_bare_number_cost_rejected(sc, tmp_path):
    with pytest.raises(sc.ControlError, match="must be an object with key 'inf'"):
        sc.load_control(minimal_control(tmp_path, defaults_extra={"mg_pv_capital_cost": 2950}),
                        check_paths=False)


def test_calibration_key_override_rejected(sc, tmp_path):
    with pytest.raises(sc.ControlError, match="calibration-stage key"):
        sc.load_control(minimal_control(tmp_path, scenario_overrides={"urban_ratio_end_year": 0.5}),
                        check_paths=False)


def test_year_override_rejected(sc, tmp_path):
    with pytest.raises(sc.ControlError, match="cannot be overridden"):
        sc.load_control(minimal_control(tmp_path, scenario_overrides={"end_year": 2035}),
                        check_paths=False)


def test_tech_switches_shape_rejected(sc, tmp_path):
    bad = {"sa_pv": 1, "mg_hydro": 1}
    with pytest.raises(sc.ControlError, match="tech_switches"):
        sc.load_control(minimal_control(tmp_path, defaults_extra={"tech_switches": bad}),
                        check_paths=False)


def test_missing_path_rejected(sc, tmp_path):
    p = minimal_control(tmp_path)
    for name in ("raw.csv", "wind.csv", "matrix.json"):
        (tmp_path / name).write_text("x")
    with pytest.raises(sc.ControlError, match="pv_profile"):
        sc.load_control(p, repo_root=tmp_path, check_paths=True)


def test_paths_resolved_against_repo_root(sc, tmp_path):
    c = sc.load_control(minimal_control(tmp_path), check_paths=False)
    assert c.repo_root == tmp_path
    assert c.paths["output_root"] == tmp_path / "out"
    assert isinstance(c.paths["calibrated_csv"], Path)


def test_sha256_and_order(sc, tmp_path):
    a = {"id": "A", "demand_case": "BU", "label": "a", "overrides": {}}
    b = {"id": "B", "demand_case": "BU", "label": "b", "overrides": {}, "legacy_name": "Old_B"}
    c = sc.load_control(minimal_control(tmp_path, scenarios=[b, a]), check_paths=False)
    assert len(c.sha256) == 64 and int(c.sha256, 16) >= 0
    assert c.ids() == ["B", "A"]
    assert c.scenario("B").legacy_name == "Old_B" and c.scenario("A").legacy_name is None
    with pytest.raises(sc.ControlError, match="unknown scenario id 'Z'"):
        c.resolved("Z")
