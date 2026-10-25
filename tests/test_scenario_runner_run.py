import json
from pathlib import Path

import pandas as pd
import pytest

STUDY = Path(__file__).resolve().parents[1] / "Scenarios" / "guinea_scenarios.json"


def make_control(gep_path, repo_root, tmp_path, calibrated_csv, scenario_ids):
    """The study file's defaults and calibration, real profiles and matrix, a sampled
    calibrated input, outputs under tmp_path, and the requested scenarios only."""
    import scenario_control
    doc = json.loads(STUDY.read_text(encoding="utf-8"))
    base = repo_root / "GuineaRuns" / "Inputs" / "Guinea Data"
    doc["paths"] = {
        "raw_input_csv": str(repo_root / "GuineaRuns" / "Inputs" / "OnSSET_InputFile_20261018_100416.csv"),
        "calibrated_csv": str(calibrated_csv),
        "pv_profile": str(base / "Solar profile" / "gn-2-pv.csv"),
        "wind_profile": str(base / "Wind profile" / "gn-2-wind.csv"),
        "productive_matrix": str(repo_root / "gep_onsset" / "productive_uses_matrix.json"),
        "output_root": str(tmp_path / "out"),
    }
    doc["scenarios"] = [s for s in doc["scenarios"] if s["id"] in scenario_ids]
    d = tmp_path / "Scenarios"
    d.mkdir(exist_ok=True)
    p = d / "control.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return scenario_control.load_control(p, repo_root=tmp_path, check_paths=True)


@pytest.fixture
def small_control(gep_path, repo_root, sample_calibrated, profiles, tmp_path):
    return make_control(gep_path, repo_root, tmp_path, sample_calibrated, ["BU_g0.1"])


def test_run_scenario_writes_three_csvs_and_manifest(gep_path, small_control, tmp_path):
    from scenario_runner import run_scenario
    m = run_scenario(small_control, "BU_g0.1", tmp_path / "b1", log=lambda *a: None)
    d = tmp_path / "b1" / "BU_g0.1"
    for suffix in ("Results", "Summaries", "Variables"):
        assert (d / f"BU_g0.1_{suffix}.csv").exists(), suffix
    assert m["status"] == "complete" and m["rows_out"] == 500 and m["rows_in"] == 500
    assert len(m["calibrated_csv_sha256"]) == 64 and m["scenario_id"] == "BU_g0.1"
    assert m["parameters"]["grid_generation_cost"] == 0.1
    assert m["parameters"]["mg_pv_capital_cost"] == {"inf": 2950.0}
    assert m["technology_constants"]["grid"]["connection_cost_per_hh"] == 125
    assert m["outputs"]["results"]["bytes"] > 0 and m["seconds"] > 0
    saved = json.loads((d / "manifest.json").read_text())
    assert saved["status"] == "complete"
    res = pd.read_csv(d / "BU_g0.1_Results.csv")
    assert res.columns[0] == "index" and "FinalElecCode2040" in res.columns
    assert res["FinalElecCode2040"].isin([1, 2, 3, 5, 7]).all()
    s = pd.read_csv(d / "BU_g0.1_Summaries.csv", index_col=0)
    assert list(s.index) == ["Grid_dens", "Grid_ext", "SA_PV", "MG_PV_Battery", "MG_Hydro",
                             "Non-electrified", "Total"]
    assert s.loc["Total", "Population2040"] == pytest.approx(res["Pop2040"].sum(), abs=1.0)
    assert s.loc["Non-electrified", "Population2040"] == 0
    v = pd.read_csv(d / "BU_g0.1_Variables.csv").set_index("Variable").Value
    assert v["scenario_id"] == "BU_g0.1" and v["Urban target tier"] == "6"


def test_run_scenario_skips_when_complete_and_reruns_on_force(gep_path, small_control, tmp_path):
    from scenario_runner import run_scenario
    quiet = lambda *a: None
    run_scenario(small_control, "BU_g0.1", tmp_path / "b1", log=quiet)
    again = run_scenario(small_control, "BU_g0.1", tmp_path / "b1", log=quiet)
    assert again["skipped"] is True and again["status"] == "complete"
    forced = run_scenario(small_control, "BU_g0.1", tmp_path / "b1", force=True, log=quiet)
    assert forced.get("skipped", False) is False


def test_run_scenario_fails_fast_on_missing_column(gep_path, small_control, tmp_path, sample_calibrated):
    from scenario_control import ControlError
    from scenario_runner import run_scenario
    df = pd.read_csv(sample_calibrated, low_memory=False).drop(columns=["hc_count_com_hc"])
    bad = tmp_path / "bad.csv"
    df.to_csv(bad, index=False)
    small_control.paths["calibrated_csv"] = bad
    with pytest.raises(ControlError, match="hc_count_com_hc"):
        run_scenario(small_control, "BU_g0.1", tmp_path / "b2", log=lambda *a: None)
    assert not (tmp_path / "b2" / "BU_g0.1" / "BU_g0.1_Results.csv").exists()


def test_summary_from_manifest_reads_back(gep_path, small_control, tmp_path):
    from scenario_runner import run_scenario, summary_from_manifest
    run_scenario(small_control, "BU_g0.1", tmp_path / "b3", log=lambda *a: None)
    s = summary_from_manifest(tmp_path / "b3", "BU_g0.1")
    assert s.loc["Total", "Population2030"] > 0
