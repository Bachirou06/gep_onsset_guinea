"""Shared fixtures for the scenario runner tests.

Data is never committed. Fixtures sample the real inputs under GuineaRuns/ on the
fly (seeded) and cache the sample under tests/_cache/, which is git-ignored. A
fixture skips its tests when its source file is absent.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE = REPO_ROOT / "tests" / "_cache"
SAMPLE_ROWS = 500
SEED = 42


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def gep_path(repo_root) -> Path:
    p = repo_root / "gep_onsset"
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
    return p


def _sample(source: Path, name: str) -> Path:
    if not source.exists():
        pytest.skip(f"input data not available: {source}")
    import pandas as pd
    CACHE.mkdir(parents=True, exist_ok=True)
    out = CACHE / name
    if not out.exists():
        df = pd.read_csv(source, low_memory=False)
        df.sample(n=SAMPLE_ROWS, random_state=SEED).sort_values("id").to_csv(out, index=False)
    return out


@pytest.fixture(scope="session")
def sample_calibrated(repo_root) -> Path:
    return _sample(repo_root / "GuineaRuns" / "Inputs" / "GIN_calibrated.csv",
                   f"sample_calibrated_{SAMPLE_ROWS}.csv")


@pytest.fixture(scope="session")
def sample_raw(repo_root) -> Path:
    return _sample(repo_root / "GuineaRuns" / "Inputs" / "OnSSET_InputFile_20261018_100416.csv",
                   f"sample_raw_{SAMPLE_ROWS}.csv")


@pytest.fixture(scope="session")
def profiles(repo_root) -> dict:
    base = repo_root / "GuineaRuns" / "Inputs" / "Guinea Data"
    pv = base / "Solar profile" / "gn-2-pv.csv"
    wind = base / "Wind profile" / "gn-2-wind.csv"
    if not (pv.exists() and wind.exists()):
        pytest.skip("hourly profiles not available under GuineaRuns/Inputs/Guinea Data")
    return {"pv": pv, "wind": wind}


# --- controls and runs on the sample ------------------------------------------------
# Every model run costs about two minutes whatever the row count (the hybrid
# sizing simulates 8,760 hours per size combination), so the model tests share
# one batch produced once per session.

@pytest.fixture(scope="session")
def shared_control(gep_path, repo_root, sample_calibrated, profiles, tmp_path_factory):
    """Two scenarios on the sample; outputs under one session-wide folder."""
    from tests.helpers import make_control
    return make_control(repo_root, tmp_path_factory.mktemp("shared"), sample_calibrated,
                        ["BU_g0.1", "TD_Low_g0.1"])


@pytest.fixture(scope="session")
def shared_batch(shared_control):
    """One batch of the two scenarios, run once per session (about four minutes)."""
    from scenario_runner import run_batch
    return run_batch(shared_control, None, "shared", log=lambda *a: None)


@pytest.fixture
def small_control(gep_path, repo_root, sample_calibrated, profiles, tmp_path):
    from tests.helpers import make_control
    return make_control(repo_root, tmp_path, sample_calibrated, ["BU_g0.1"])


# --- results report: a 500-settlement sample of a finished batch ------------------
REPORT_BATCH_ENV = "GUINEA_REPORT_BATCH"
DEFAULT_REPORT_BATCH = "GuineaRuns/Outputs/2026-10-25_table1"


@pytest.fixture(scope="session")
def report_batch_dir(repo_root) -> Path:
    """The real finished batch the report tests sample from; skipped when absent."""
    import os
    p = Path(os.environ.get(REPORT_BATCH_ENV, str(repo_root / DEFAULT_REPORT_BATCH)))
    if not (p / "comparison_summary.csv").exists():
        pytest.skip(f"finished batch not available: {p}")
    return p


@pytest.fixture(scope="session")
def report_sample_batch(repo_root, report_batch_dir) -> Path:
    """A copy of the batch restricted to 500 settlement ids (seed 42) and the columns the
    report reads; manifests, Summaries, comparison and logs copied verbatim. Built once,
    cached under tests/_cache/report_sample_500/<batch name>/."""
    import json
    import shutil
    import pandas as pd
    from report.constants import RESULT_COLUMNS
    out = CACHE / "report_sample_500" / report_batch_dir.name
    marker = out / ".complete"
    if marker.exists():
        return out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    folders = sorted(d for d in report_batch_dir.iterdir()
                     if d.is_dir() and (d / "manifest.json").exists())
    ids = None
    for d in folders:
        m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        if m.get("status") != "complete":
            continue
        sid = d.name
        df = pd.read_csv(d / f"{sid}_Results.csv", usecols=RESULT_COLUMNS)
        if ids is None:
            ids = df["id"].sample(n=SAMPLE_ROWS, random_state=SEED).sort_values().to_numpy()
        (out / sid).mkdir()
        df[df["id"].isin(ids)].to_csv(out / sid / f"{sid}_Results.csv", index=False)
        for name in ("manifest.json", f"{sid}_Summaries.csv", f"{sid}_Variables.csv"):
            if (d / name).exists():
                shutil.copy2(d / name, out / sid / name)
    for name in ("comparison_summary.csv", "batch_log.txt", "CHECKS.md"):
        if (report_batch_dir / name).exists():
            shutil.copy2(report_batch_dir / name, out / name)
    marker.write_text("ok")
    return out


CORE_COSTS = ("0.047", "0.078", "0.085", "0.1", "0.22")


@pytest.fixture(scope="session")
def report_core_sample_batch(report_sample_batch) -> Path:
    """The sample batch restricted to the reference-variant scenarios of the four study
    grid-cost levels (24 scenarios): no cost bins, no supply-side variants. Used by the
    tests that synthesise bins and variants and by the 'without' tests."""
    import json
    import shutil
    import pandas as pd
    out = CACHE / "report_sample_500_core" / report_sample_batch.name
    marker = out / ".complete"
    if marker.exists():
        return out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    keep = []
    for d in sorted(p for p in report_sample_batch.iterdir() if p.is_dir()):
        m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        cost = str(m["parameters"]["grid_generation_cost"])
        if m.get("variant", "reference") == "reference" and cost in CORE_COSTS:
            shutil.copytree(d, out / d.name)
            keep.append(d.name)
    for name in ("batch_log.txt", "CHECKS.md"):
        if (report_sample_batch / name).exists():
            shutil.copy2(report_sample_batch / name, out / name)
    comp = pd.read_csv(report_sample_batch / "comparison_summary.csv")
    comp[comp["scenario_id"].isin(keep)].to_csv(out / "comparison_summary.csv", index=False)
    marker.write_text("ok")
    return out
