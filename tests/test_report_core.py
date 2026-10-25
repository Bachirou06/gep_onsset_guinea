"""The final scenario set: three key cases x three grid-cost regimes as the report's core."""
import pandas as pd
import pytest

from report import constants as C


def test_core_constants():
    assert C.REGIME_ORDER == [0.22, 0.085, 0.1] and C.PRIMARY_COST == 0.22
    assert C.REGIME_NAME == {0.22: "Cost-reflective", 0.085: "Hydro cost", 0.1: "Current tariff"}
    assert C.REGIME_KEY == {0.22: "cost_reflective", 0.085: "hydro_cost", 0.1: "current_tariff"}
    assert all(cost in C.REGIME_SOURCE for cost in C.REGIME_ORDER)
    assert C.CORE_CELLS == [(case, cost) for case in C.KEY_CASES for cost in C.REGIME_ORDER]
    assert len(C.CORE_CELLS) == 9
    assert C.COST_LEVELS == [0.047, 0.078, 0.085, 0.1, 0.22] and C.REFERENCE_COST == 0.1
    assert C.COST_ROLE[0.085]


def test_core_label_format():
    assert C.core_label("BU", 0.22) == "BU, Cost-reflective"
    assert C.core_label("TD_Low_minus", 0.085) == "U3R1, Hydro cost"
    assert C.core_label("TD_High_minus", 0.1) == "U4R2, Current tariff"


def test_batch_core_returns_present_cells_in_order(report_sample_batch, repo_root, tmp_path):
    from report.data import load_batch
    b = load_batch(report_sample_batch, repo_root, cache_dir=tmp_path / "cache", log=lambda *a: None)
    core = b.core()
    keys = list(core)
    assert keys == [k for k in C.CORE_CELLS if k in core]                 # CORE_CELLS order
    for case in C.KEY_CASES:
        assert (case, 0.22) in core and (case, 0.1) in core
        assert core[(case, 0.22)].grid_cost == 0.22 and core[(case, 0.22)].variant == "reference"
    labels = b.core_labels()
    assert list(labels) == keys and labels[("BU", 0.22)] == "BU, Cost-reflective"
