"""Wording defects found in the rendered 38-scenario report (second draft)."""
import pandas as pd
import pytest

pytest.importorskip("plotly")

from report import messages as MS  # noqa: E402
from report import metrics as M  # noqa: E402
from tests.test_report_variants import batch_with_variants  # noqa: E402,F401  (fixture)


def _vc(inv_pct, grid_abs, mg_abs):
    rows = []
    for metric, ref, dabs, dpct in [("investment_musd_cum", 2307.4, 2307.4 * inv_pct / 100, inv_pct),
                                    ("grid_share_2040", 0.782, grid_abs, 100 * grid_abs / 0.782),
                                    ("mg_pv_people_2040", 2085423.0, mg_abs, 100 * mg_abs / 2085423.0)]:
        rows.append({"demand_case": "BU", "variant": "optgrid", "scenario_id": "BU_optgrid_g0.1", "metric": metric,
                     "reference": ref, "variant_value": ref + dabs, "delta_abs": dabs, "delta_pct": dpct})
    return pd.DataFrame(rows)


def test_supply_variant_message_drops_the_amount_when_nothing_changes():
    m = MS.km_supply_variants(_vc(inv_pct=-0.02, grid_abs=-0.002, mg_abs=-11949))
    assert "leaves total investment unchanged" in m["text"]
    assert "leaves the grid share of the 2040 population unchanged" in m["text"]
    assert "by 0%" not in m["text"] and "by 0 points" not in m["text"]
    assert "removes 11,949 people on mini-grid PV" in m["text"]


def test_supply_variant_message_keeps_the_amount_when_it_changes():
    m = MS.km_supply_variants(_vc(inv_pct=-0.3, grid_abs=-0.023, mg_abs=570024))
    assert "lowers the grid share of the 2040 population by 2 points" in m["text"]
    assert "adds 570,000 people on mini-grid PV" in m["text"]


def test_grid_extension_message_says_people():
    sens = pd.DataFrame([{"demand_case": c, "grid_cost": g, "grid_ext_people": p}
                         for c in ("TD_Low_minus", "TD_High_minus", "BU")
                         for g, p in zip([0.1, 0.25], [3.0e6, 3872])])
    m = MS.km_grid_extension_vanishes(sens)
    assert "3,872 people" in m["text"] and "3.0 million people" in m["text"]


def test_tech_mix_message_keeps_pv_capitalised():
    from tests.test_report_metrics import frame
    hs = {c: M.headline(frame()) for c in ("TD_Low_minus", "BU")}
    m = MS.km_tech_mix(hs, key_cases=("TD_Low_minus", "BU"))
    assert "stand-alone PV" in m["text"] and "mini-grid PV with battery" in m["text"]
    assert " pv " not in m["text"]


def test_variant_table_uses_readable_metric_labels(batch_with_variants, repo_root, tmp_path):
    from report.build import build
    path = build(batch_with_variants, repo_root, out_path=tmp_path / "r.html", inputs_dir=None, maps=False, geo=False,
                 sample=True, log=lambda *a: None)
    html = path.read_text(encoding="utf-8")
    i = html.find("Table 9.4. Supply-side variants")
    sec = html[i:i + 60000]
    assert "People on grid extension 2040" in sec and "People not yet electrified 2030" in sec
    for raw in ("grid ext people", "mg pv people", "sa pv people", "unserved 2030"):
        assert raw not in sec, raw


def test_switch_map_subtitle_is_short_enough_for_the_title_band():
    from report import build as B
    assert B._variant_subtitle("optgrid_optmg") == "grid caps removed and mini-grid PV panels 25 percent cheaper"
    assert B._variant_subtitle("optgrid") == "grid caps removed"
    assert len(B._variant_subtitle("optgrid_optmg")) <= 70
