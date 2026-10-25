"""Single-scenario runs on a 500-settlement sample.

Every model run costs about two minutes whatever the row count: the hybrid
sizing in hybrids_pv.py and hybrids_wind.py simulates 8,760 hours per size
combination. Tests therefore share one batch produced once per session
(fixture shared_batch) and are marked `model`; run them with `pytest -m model`.
"""
import json
from pathlib import Path

import pandas as pd
import pytest

from tests.helpers import QUIET, make_control  # noqa: F401


@pytest.mark.model
def test_run_scenario_writes_three_csvs_and_manifest(shared_control, shared_batch):
    d = shared_batch / "BU_g0.1"
    for suffix in ("Results", "Summaries", "Variables"):
        assert (d / f"BU_g0.1_{suffix}.csv").exists(), suffix
    m = json.loads((d / "manifest.json").read_text())
    assert m["status"] == "complete" and m["rows_out"] == 500 and m["rows_in"] == 500
    assert len(m["calibrated_csv_sha256"]) == 64 and m["scenario_id"] == "BU_g0.1"
    assert m["parameters"]["grid_generation_cost"] == 0.1
    assert m["parameters"]["mg_pv_capital_cost"] == {"inf": 2950.0}
    assert m["technology_constants"]["grid"]["connection_cost_per_hh"] == 125
    assert m["outputs"]["results"]["bytes"] > 0 and m["seconds"] > 0
    assert m["control_file_sha256"] == shared_control.sha256
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


@pytest.mark.model
def test_run_scenario_skips_when_complete(shared_control, shared_batch):
    from scenario_runner import run_scenario
    again = run_scenario(shared_control, "BU_g0.1", shared_batch, log=QUIET)
    assert again["skipped"] is True and again["status"] == "complete"


@pytest.mark.model
def test_run_scenario_force_reruns(small_control, tmp_path):
    from scenario_runner import run_scenario
    first = run_scenario(small_control, "BU_g0.1", tmp_path / "b1", log=QUIET)
    forced = run_scenario(small_control, "BU_g0.1", tmp_path / "b1", force=True, log=QUIET)
    assert forced.get("skipped", False) is False
    assert forced["started"] >= first["finished"]


def test_run_scenario_fails_fast_on_missing_column(small_control, tmp_path, sample_calibrated):
    from scenario_control import ControlError
    from scenario_runner import run_scenario
    df = pd.read_csv(sample_calibrated, low_memory=False).drop(columns=["hc_count_com_hc"])
    bad = tmp_path / "bad.csv"
    df.to_csv(bad, index=False)
    small_control.paths["calibrated_csv"] = bad
    with pytest.raises(ControlError, match="hc_count_com_hc"):
        run_scenario(small_control, "BU_g0.1", tmp_path / "b2", log=QUIET)
    assert not (tmp_path / "b2" / "BU_g0.1" / "BU_g0.1_Results.csv").exists()


def test_run_scenario_fails_when_calibrated_file_missing(small_control, tmp_path):
    from scenario_control import ControlError
    from scenario_runner import run_scenario
    small_control.paths["calibrated_csv"] = tmp_path / "absent.csv"
    with pytest.raises(ControlError, match="calibrate first"):
        run_scenario(small_control, "BU_g0.1", tmp_path / "b3", log=QUIET)


@pytest.mark.model
def test_summary_from_manifest_reads_back(shared_batch):
    from scenario_runner import summary_from_manifest
    s = summary_from_manifest(shared_batch, "BU_g0.1")
    assert s.loc["Total", "Population2030"] > 0
