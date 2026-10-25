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
