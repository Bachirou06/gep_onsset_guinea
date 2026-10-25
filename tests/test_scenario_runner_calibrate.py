import json
from pathlib import Path

import pandas as pd
import pytest

from tests.test_scenario_control import minimal_control


@pytest.fixture
def cal_control(gep_path, sample_raw, tmp_path):
    import scenario_control
    p = minimal_control(tmp_path, paths_patch={
        "raw_input_csv": str(sample_raw),
        "calibrated_csv": str(tmp_path / "cal.csv"),
        "pv_profile": str(sample_raw), "wind_profile": str(sample_raw),
        "productive_matrix": str(sample_raw), "output_root": str(tmp_path / "out"),
    })
    return scenario_control.load_control(p, repo_root=tmp_path, check_paths=False)


def test_calibrate_writes_file_with_calibration_columns(gep_path, cal_control, tmp_path):
    from scenario_runner import calibrate
    out = calibrate(cal_control, tmp_path / "cal.csv")
    assert out == tmp_path / "cal.csv"
    df = pd.read_csv(out)
    for c in ["PopStartYear", "ElecPopCalib", "Pop2030", "Pop2040", "Pop2025", "GridPenalty",
              "WindCF", "ElecStart", "GridDistCalibElec", "FinalElecCode2025"]:
        assert c in df.columns, c
    assert (df["Pop"] > 0).all()
    info = json.loads((tmp_path / "cal_parameters.json").read_text())
    assert info["pop_start_year"] == 17521167 and info["end_year_pop"] == 27697655
    assert info["min_pop"] == 50 and info["pop_threshold_applied"] == 0
    assert len(info["raw_input_sha256"]) == 64
    assert 0 < info["modelled_elec_rate"] < 1


def test_calibrate_population_sums_to_pop_start_year(gep_path, cal_control, tmp_path):
    from scenario_runner import calibrate
    df = pd.read_csv(calibrate(cal_control, tmp_path / "cal.csv"))
    assert abs(df["PopStartYear"].sum() - cal_control.calibration["pop_start_year"]) < 1.0


def test_calibrate_default_output_is_control_path(gep_path, cal_control, tmp_path):
    from scenario_runner import calibrate
    out = calibrate(cal_control)
    assert out == cal_control.paths["calibrated_csv"] and out.exists()
