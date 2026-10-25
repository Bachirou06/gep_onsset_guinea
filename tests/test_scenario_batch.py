import datetime
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from tests.helpers import QUIET, make_control

REPO = Path(__file__).resolve().parents[1]

COMPARISON_COLUMNS = ["scenario_id", "label", "demand_case", "grid_generation_cost",
                      "urban_target_tier", "rural_target_tier", "technology", "year",
                      "population", "new_connections", "capacity_mw", "investment_musd"]


@pytest.mark.model
def test_run_batch_two_scenarios_comparison_and_log(shared_control, shared_batch):
    assert shared_batch == shared_control.paths["output_root"] / "shared"
    comp = pd.read_csv(shared_batch / "comparison_summary.csv")
    assert list(comp.columns) == COMPARISON_COLUMNS
    assert len(comp) == 2 * 7 * 2
    assert comp.scenario_id.iloc[0] == "TD_Low_g0.1"          # control-file order
    assert set(comp.year) == {2030, 2040} and "Total" in set(comp.technology)
    bu = comp[(comp.scenario_id == "BU_g0.1") & (comp.technology == "Total") & (comp.year == 2040)]
    assert bu.population.iloc[0] > 0 and bu.urban_target_tier.iloc[0] == 6
    assert bu.grid_generation_cost.iloc[0] == 0.1
    log = (shared_batch / "batch_log.txt").read_text()
    assert log.count("complete") == 2 and "TD_Low_g0.1" in log


@pytest.mark.model
def test_run_batch_subset_rebuilds_comparison_for_subset_without_rerun(shared_control, shared_batch):
    from scenario_runner import run_batch
    before = (shared_batch / "BU_g0.1" / "BU_g0.1_Summaries.csv").stat().st_mtime_ns
    b = run_batch(shared_control, ["BU_g0.1"], "shared", log=QUIET)
    assert b == shared_batch
    assert (shared_batch / "BU_g0.1" / "BU_g0.1_Summaries.csv").stat().st_mtime_ns == before
    comp = pd.read_csv(b / "comparison_summary.csv")
    assert set(comp.scenario_id) == {"BU_g0.1"} and len(comp) == 7 * 2
    assert "skipped" in (b / "batch_log.txt").read_text()


@pytest.mark.model
def test_run_batch_reruns_interrupted_scenario(gep_path, repo_root, sample_calibrated, profiles, tmp_path):
    from scenario_runner import run_batch
    c = make_control(repo_root, tmp_path, sample_calibrated, ["BU_g0.1"])
    b = run_batch(c, ["BU_g0.1"], "t3", log=QUIET)
    summaries = b / "BU_g0.1" / "BU_g0.1_Summaries.csv"
    (b / "BU_g0.1" / "manifest.json").unlink()
    before = summaries.stat().st_mtime_ns
    run_batch(c, ["BU_g0.1"], "t3", log=QUIET)
    assert summaries.stat().st_mtime_ns > before
    assert (b / "BU_g0.1" / "manifest.json").exists()


def test_run_batch_unknown_id_fails_before_running(shared_control):
    from scenario_control import ControlError
    from scenario_runner import run_batch
    with pytest.raises(ControlError, match="BU_g0.1"):
        run_batch(shared_control, ["nope"], "t2", log=QUIET)
    assert not (shared_control.paths["output_root"] / "t2").exists()


def test_resolve_batch_dir_default_is_today(shared_control):
    from scenario_runner import resolve_batch_dir
    assert resolve_batch_dir(shared_control, None).name == datetime.date.today().isoformat()
    assert resolve_batch_dir(shared_control, "x") == shared_control.paths["output_root"] / "x"


def test_cli_dry_run_and_bad_id(shared_control):
    cli = REPO / "run_scenarios.py"
    out = subprocess.run([sys.executable, str(cli), str(shared_control.path), "--dry-run"],
                         capture_output=True, text=True, cwd=REPO)
    assert out.returncode == 0, out.stderr
    assert "BU_g0.1" in out.stdout and "TD_Low_g0.1" in out.stdout and "grid_generation_cost" in out.stdout
    bad = subprocess.run([sys.executable, str(cli), str(shared_control.path), "--only", "nope", "--dry-run"],
                         capture_output=True, text=True, cwd=REPO)
    assert bad.returncode == 1 and "TD_Low_g0.1" in bad.stderr
