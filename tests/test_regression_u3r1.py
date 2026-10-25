"""Regression gate: the runner must reproduce the shared Scenario_U3R1_0.047 run.

Runs the full 82,954-settlement calibrated file (about two minutes). Marked slow;
run with `pytest -m slow`.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
SHARED = REPO / "GuineaRuns" / "Outputs" / "Scenario_U3R1_0.047"


@pytest.mark.slow
def test_runner_reproduces_shared_u3r1(gep_path):
    if not (SHARED / "Scenario_U3R1_0.047_Summaries.csv").exists():
        pytest.skip("shared U3R1 outputs not available under GuineaRuns/Outputs")
    from scenario_control import load_control
    from scenario_runner import run_batch

    c = load_control(REPO / "Scenarios" / "regression_u3r1.json")
    b = run_batch(c, ["REF_U3R1_g0.047"], "gate", force=True, log=lambda *a: None)

    got = pd.read_csv(b / "REF_U3R1_g0.047" / "REF_U3R1_g0.047_Summaries.csv", index_col=0)
    exp = pd.read_csv(SHARED / "Scenario_U3R1_0.047_Summaries.csv", index_col=0)
    pd.testing.assert_frame_equal(got, exp.reindex(index=got.index, columns=got.columns),
                                  check_exact=False, atol=0.005)

    gr = pd.read_csv(b / "REF_U3R1_g0.047" / "REF_U3R1_g0.047_Results.csv", low_memory=False).set_index("id")
    er = pd.read_csv(SHARED / "Scenario_U3R1_0.047_Results.csv", low_memory=False).set_index("id")
    assert len(gr) == len(er) == 82954
    assert set(gr.columns) == set(er.columns)
    er = er.loc[gr.index]
    for y in (2030, 2040):
        assert (gr[f"FinalElecCode{y}"] == er[f"FinalElecCode{y}"]).all(), y
    for col in ("InvestmentCost2030", "InvestmentCost2040", "NewConnections2040", "NewCapacity2040",
                "MinimumOverallLCOE2040"):
        assert np.allclose(gr[col], er[col], rtol=1e-9, atol=1e-6, equal_nan=True), col
