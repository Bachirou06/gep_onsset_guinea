import json
from pathlib import Path

import pandas as pd
import pytest

from report.constants import DEMAND_CASES, RESULT_COLUMNS, REFERENCE_COST, TECH, TECH_ORDER


def test_constants_are_consistent():
    assert set(TECH) == {1, 2, 3, 5, 7, 99} and TECH_ORDER == [1, 2, 5, 7, 3, 99]
    assert [c[0] for c in DEMAND_CASES] == ["TD_Low_minus", "TD_Low", "TD_High_minus", "TD_High", "TD_High_plus", "BU"]
    assert REFERENCE_COST == 0.1 and "id" in RESULT_COLUMNS and "FinalElecCode2040" in RESULT_COLUMNS
    assert len(set(RESULT_COLUMNS)) == len(RESULT_COLUMNS)


def test_load_settlements_columns_and_dtypes(report_sample_batch, tmp_path):
    from report.data import load_settlements
    df = load_settlements(report_sample_batch / "BU_g0.1", tmp_path / "cache")
    assert list(df.columns) == list(RESULT_COLUMNS) and len(df) == 500
    assert str(df["FinalElecCode2040"].dtype) == "int8" and str(df["FinalElecCode2030"].dtype) == "int8"
    assert str(df["IsUrban"].dtype) == "int8" and str(df["ElecStart"].dtype) == "int8"
    assert str(df["Admin_1"].dtype) == "category" and str(df["id"].dtype) == "int32"
    assert df["X_deg"].dtype == "float64"
    assert df["FinalElecCode2040"].isin([1, 2, 3, 5, 7]).all()


def test_admin_names_decode_as_utf8(report_batch_dir, tmp_path):
    from report.data import load_settlements
    df = load_settlements(report_batch_dir / "BU_g0.1", tmp_path / "cache", use_cache=False)
    assert "Boké" in set(df["Admin_1"].astype(str))
    assert "Nzérékoré" in set(df["Admin_1"].astype(str))


def test_cache_created_reused_and_invalidated(report_sample_batch, tmp_path):
    from report.data import load_settlements
    cache = tmp_path / "cache"
    load_settlements(report_sample_batch / "BU_g0.1", cache)
    parquet = cache / "BU_g0.1.parquet"
    sidecar = cache / "BU_g0.1.cache.json"
    assert parquet.exists() and sidecar.exists()
    t0 = parquet.stat().st_mtime_ns
    load_settlements(report_sample_batch / "BU_g0.1", cache)
    assert parquet.stat().st_mtime_ns == t0                         # reused
    meta = json.loads(sidecar.read_text())
    meta["source_bytes"] = -1
    sidecar.write_text(json.dumps(meta))
    load_settlements(report_sample_batch / "BU_g0.1", cache)
    assert parquet.stat().st_mtime_ns > t0                          # rebuilt
    assert json.loads(sidecar.read_text())["source_bytes"] > 0


def test_load_batch_structure(report_sample_batch, repo_root, tmp_path):
    from report.data import load_batch
    b = load_batch(report_sample_batch, repo_root, cache_dir=tmp_path / "cache", log=lambda *a: None)
    assert b.name == report_sample_batch.name and len(b.scenarios) == 38
    assert list(b.scenarios)[:5] == ["TD_Low_g0.1", "TD_Low_minus_g0.1", "TD_High_g0.1",
                                     "TD_High_plus_g0.1", "BU_g0.1"]       # control-file order
    ref = b.reference()
    present = [c[0] for c in DEMAND_CASES if c[0] in {s.demand_case for s in b.scenarios.values()}]
    assert [s.demand_case for s in ref] == present                        # DEMAND_CASES order
    assert all(s.grid_cost == REFERENCE_COST for s in ref)
    bu = b.by_case("BU")
    assert sorted(bu) == [0.047, 0.06, 0.078, 0.1, 0.12, 0.14, 0.16, 0.18, 0.2, 0.22, 0.25] and bu[0.22].scenario_id == "BU_g0.22"
    s = b.scenarios["TD_High_g0.078"]
    assert (s.urban_tier, s.rural_tier, s.grid_cost) == (4, 3, 0.078)
    assert s.summaries.loc["Total", "Population2040"] > 0
    assert len(b.comparison) >= 38 * 7 * 2 and len(b.control["scenarios"]) >= 38
    p = b.provenance()
    assert p["calibrated_csv_sha256"] and p["n_scenarios"] == 38
    assert isinstance(p["git_commits"], list) and p["git_dirty_any"] in (True, False)
    assert len(p["control_file_sha256"]) == 64


def test_ids_identical_across_scenarios(report_sample_batch, repo_root, tmp_path):
    from report.data import load_batch
    b = load_batch(report_sample_batch, repo_root, cache_dir=tmp_path / "cache", log=lambda *a: None)
    first = b.scenarios["TD_Low_g0.1"].settlements["id"].to_numpy()
    for s in b.scenarios.values():
        assert (s.settlements["id"].to_numpy() == first).all(), s.scenario_id


def test_check_consistency_sample_is_not_expected_to_match(report_sample_batch, repo_root, tmp_path):
    from report.data import check_consistency, load_batch
    b = load_batch(report_sample_batch, repo_root, cache_dir=tmp_path / "cache", log=lambda *a: None)
    res = check_consistency(b)
    assert set(res.columns) >= {"scenario_id", "technology", "year", "metric", "settlements", "summary", "ok"}
    assert not res["ok"].all()          # a 500-row sample cannot reproduce national totals


@pytest.mark.slow
def test_check_consistency_full_batch(report_batch_dir, repo_root):
    from report.data import check_consistency, load_batch
    b = load_batch(report_batch_dir, repo_root, log=lambda *a: None)
    res = check_consistency(b)
    bad = res[~res["ok"]]
    assert bad.empty, bad.head(10).to_string()
