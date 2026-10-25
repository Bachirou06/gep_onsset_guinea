import numpy as np
import pandas as pd
import pytest

pytest.importorskip("plotly")

from report import figures as F  # noqa: E402
from report.constants import CASE_ORDER, COST_LEVELS, SERVED_CODES  # noqa: E402


def long_frame():
    rows = []
    for case in CASE_ORDER:
        for year in (2030, 2040):
            for i, code in enumerate(SERVED_CODES + [99]):
                rows.append({"demand_case": case, "year": year, "code": code, "value": (i + 1) * 100.0})
    return pd.DataFrame(rows)


def test_stacked_by_tech_two_panels_one_trace_per_tech_per_panel():
    fig = F.stacked_by_tech(long_frame(), "value", "Population by technology", "people", CASE_ORDER)
    assert len(fig.data) == 2 * 6                      # 6 codes x 2 year panels
    assert fig.layout.title.text == "Population by technology"
    names = {t.name for t in fig.data}
    assert "Grid extension" in names and "Not yet electrified" in names
    html = F.fig_to_div(fig, "fig-4-1")
    assert 'id="fig-4-1"' in html and "plotly.min.js" not in html and "<script" in html


def test_lines_vs_cost_marks_reference():
    from report.constants import SENSITIVITY_CASES
    sens = pd.DataFrame([{"demand_case": c, "grid_cost": g, "investment_musd_cum": 1000 + 100 * g}
                         for c in SENSITIVITY_CASES for g in COST_LEVELS])
    fig = F.lines_vs_cost(sens, "investment_musd_cum", "Cumulative investment (million USD)")
    assert len(fig.data) == len(SENSITIVITY_CASES)
    assert any(s.type == "line" for s in fig.layout.shapes)       # reference cost marker
    assert list(fig.data[0].x) == COST_LEVELS


def test_grouped_metric_bars_small_multiples():
    n = len(CASE_ORDER)
    df = pd.DataFrame({"demand_case": CASE_ORDER, "a": list(range(1, n + 1)), "b": list(range(n, 0, -1))})
    fig = F.grouped_metric_bars(df, ["a", "b"], ["A title", "B title"], CASE_ORDER)
    assert len(fig.data) == 2 and fig.layout.annotations[0].text == "A title"


def test_shares_vs_cost_stacks_to_100():
    rows = [{"demand_case": "BU", "grid_cost": g, "code": c, "population": p}
            for g in COST_LEVELS for c, p in zip(SERVED_CODES, [50, 10, 20, 15, 5])]
    fig = F.shares_vs_cost(pd.DataFrame(rows), ["BU"])
    assert len(fig.data) == 5
    total = sum(np.asarray(t.y) for t in fig.data)
    assert np.allclose(total, 100)


def test_lcoe_histograms_switch_matrix_delta_bars():
    hist = pd.DataFrame({"demand_case": ["BU"] * 3 + ["TD_Low"] * 3, "bin_left": [0.0, 0.1, 0.2] * 2,
                         "people": [10, 20, 30, 5, 25, 10]})
    assert len(F.lcoe_histograms(hist).data) == 2
    flows = pd.DataFrame({"from_code": [2, 2, 3], "to_code": [5, 3, 5], "settlements": [10, 2, 1], "people": [600, 50, 20]})
    fig = F.switch_matrix(flows, "Switches")
    assert fig.data[0].type == "heatmap"
    delta = pd.DataFrame({"metric": ["investment_musd_cum", "lcoe_energy_w"], "base": [1, 2], "variant": [2, 1],
                          "delta_abs": [1, -1], "delta_pct": [100.0, -50.0]})
    fig = F.delta_bars(delta, "Deltas")
    assert fig.data[0].type == "bar"


def test_plotly_js_bundle_is_available_once():
    js = F.plotly_js()
    assert len(js) > 1_000_000 and "Plotly" in js[:5000] or "plotly" in js[:5000].lower()
