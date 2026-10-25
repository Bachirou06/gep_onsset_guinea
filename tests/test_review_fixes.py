"""Tests pinning the whole-branch review findings (2026-10-25)."""
import json
from pathlib import Path

import pandas as pd
import pytest

from tests.helpers import QUIET, make_control
from tests.test_scenario_control import minimal_control

STUDY = Path(__file__).resolve().parents[1] / "Scenarios" / "guinea_scenarios.json"


@pytest.fixture
def sc(gep_path):
    import scenario_control
    return scenario_control


# --- Important 4: numeric levers must have numeric JSON types ----------------------
@pytest.mark.parametrize("key,value,msg", [
    ("discount_rate", "0.08", "must be a number"),
    ("urban_target_tier", "3", "must be an integer"),
    ("urban_target_tier", 7, "between 1 and 6"),
    ("cost_choice", 3, "must be 1 or 2"),
    ("productive_demand", 2, "must be 0 or 1"),
    ("productive_preference", 2, "must be a string"),
    ("productive_preference", "Loww", "Low, Medium or High"),
])
def test_default_type_errors(sc, tmp_path, key, value, msg):
    with pytest.raises(sc.ControlError, match=f"'{key}'.*{msg}"):
        sc.load_control(minimal_control(tmp_path, defaults_extra={key: value}), check_paths=False)


def test_override_type_error(sc, tmp_path):
    with pytest.raises(sc.ControlError, match="'grid_generation_cost'.*must be a number"):
        sc.load_control(minimal_control(tmp_path, scenario_overrides={"grid_generation_cost": "0.1"}),
                        check_paths=False)


# --- Important 5: prioritization is hard-coded to 5 in the model calls -------------
def test_prioritization_other_than_5_rejected(sc, tmp_path):
    with pytest.raises(sc.ControlError, match="prioritization.*hard-codes 5"):
        sc.load_control(minimal_control(tmp_path, defaults_extra={"prioritization": 4}), check_paths=False)


def test_study_meta_names_the_inert_keys(sc):
    notes = " ".join(sc.load_control(STUDY, check_paths=False).meta["notes"])
    for k in ("existing_grid_cost_ratio", "mv_increase_rate", "max_mv_line_dist", "prioritization"):
        assert k in notes, k


# --- Important 1: a complete manifest is skipped only when nothing behind it changed
def test_skip_reason_rules(gep_path):
    from scenario_runner import skip_reason
    params = {"a": 1, "mg_pv_capital_cost": {float("inf"): 2950.0}}
    good = {"status": "complete", "parameters": {"a": 1, "mg_pv_capital_cost": {"inf": 2950.0}},
            "calibrated_csv_sha256": "x" * 64}
    assert skip_reason(good, params, "x" * 64) == "complete"
    assert skip_reason(None, params, "x" * 64) is None
    assert skip_reason({**good, "status": "running"}, params, "x" * 64) is None
    assert skip_reason({**good, "parameters": {"a": 2}}, params, "x" * 64) is None
    assert skip_reason(good, params, "y" * 64) is None


def test_stale_manifest_is_rerun_not_skipped(small_control, tmp_path):
    """A complete manifest with other parameters must not be skipped. The re-run is
    cut short by pointing the calibrated file at a missing path after the hash."""
    from scenario_control import ControlError
    from scenario_runner import run_scenario
    d = tmp_path / "b" / "BU_g0.1"
    d.mkdir(parents=True)
    stale = {"status": "complete", "parameters": {"grid_generation_cost": 0.5},
             "calibrated_csv_sha256": "0" * 64, "scenario_id": "BU_g0.1"}
    (d / "manifest.json").write_text(json.dumps(stale))
    small_control.paths["calibrated_csv"] = tmp_path / "absent.csv"
    with pytest.raises(ControlError, match="calibrate first"):
        run_scenario(small_control, "BU_g0.1", tmp_path / "b", log=QUIET)


# --- Important 2: the calibrated file must come from this control file's calibration
def test_calibration_provenance_mismatch_rejected(small_control, sample_calibrated, tmp_path):
    from scenario_control import ControlError
    from scenario_runner import check_calibration_provenance
    cal = tmp_path / "cal.csv"
    cal.write_bytes(Path(sample_calibrated).read_bytes())
    info = dict(small_control.calibration)
    info["urban_ratio_end_year"] = 0.5
    (tmp_path / "cal_parameters.json").write_text(json.dumps(info))
    with pytest.raises(ControlError, match="urban_ratio_end_year.*--calibrate"):
        check_calibration_provenance(small_control, cal)


def test_calibration_provenance_verified_and_unverified(small_control, sample_calibrated, tmp_path):
    from scenario_runner import check_calibration_provenance
    cal = tmp_path / "cal.csv"
    cal.write_bytes(Path(sample_calibrated).read_bytes())
    assert check_calibration_provenance(small_control, cal) == "unverified"
    (tmp_path / "cal_parameters.json").write_text(json.dumps(dict(small_control.calibration)))
    assert check_calibration_provenance(small_control, cal) == "verified"


# --- Important 3: the comparison table covers every complete scenario of the batch
def test_comparison_covers_all_complete_scenarios(gep_path, shared_control, tmp_path):
    from scenario_runner import comparison_table, complete_scenarios
    b = tmp_path / "batch"
    cols = ["Population2030", "NewConnections2030", "Capacity2030 (MW)", "Investment2030 (million USD)",
            "Population2040", "NewConnections2040", "Capacity2040 (MW)", "Investment2040 (million USD)"]
    idx = ["Grid_dens", "Grid_ext", "SA_PV", "MG_PV_Battery", "MG_Hydro", "Non-electrified", "Total"]
    for sid in ("BU_g0.1", "TD_Low_g0.1"):
        (b / sid).mkdir(parents=True)
        pd.DataFrame(1.0, index=idx, columns=cols).to_csv(b / sid / f"{sid}_Summaries.csv")
        (b / sid / "manifest.json").write_text(json.dumps({"status": "complete"}))
    (b / "TD_Low_g0.1" / "manifest.json").write_text(json.dumps({"status": "running"}))
    assert complete_scenarios(shared_control, b) == ["BU_g0.1"]
    (b / "TD_Low_g0.1" / "manifest.json").write_text(json.dumps({"status": "complete"}))
    assert complete_scenarios(shared_control, b) == ["TD_Low_g0.1", "BU_g0.1"]   # control-file order
    comp = comparison_table(shared_control, b, complete_scenarios(shared_control, b))
    assert set(comp.scenario_id) == {"TD_Low_g0.1", "BU_g0.1"} and len(comp) == 28
