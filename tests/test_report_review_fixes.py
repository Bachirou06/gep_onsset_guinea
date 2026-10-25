"""Tests pinning the whole-branch review findings on the report (2026-10-25)."""
import io
import re

import numpy as np
import pandas as pd
import pytest

from report import figures as F
from report import maps as MP
from report import messages as MS
from report import metrics as M
from report.constants import SERVED_CODES, TECH_COLOUR, TECH_ORDER
from report.render import table_html
from tests.test_report_metrics import frame


def _hex_to_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _colour_present(png: bytes, hex_colour: str, tol: int = 12) -> bool:
    from PIL import Image
    im = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))
    target = np.array(_hex_to_rgb(hex_colour))
    return bool((np.abs(im.astype(int) - target).max(axis=2) <= tol).any())


# --- Critical 1: quantisation must keep every technology colour ------------------------
def test_shrink_png_keeps_every_technology_colour():
    df = frame()
    df = pd.concat([df] * 400, ignore_index=True)
    df = df[(df["FinalElecCode2040"] != 7) | (df.index < 6)]        # a single hydro point among 2,000
    df["X_deg"] = np.random.default_rng(1).uniform(-14.5, -8.0, len(df))
    df["Y_deg"] = np.random.default_rng(2).uniform(7.5, 12.5, len(df))
    png = MP.technology_map(df, 2040, None, title="t", subtitle="s", source_note="n")
    small = MP.shrink_png(png, colours=96)
    assert len(small) < len(png)
    for code in SERVED_CODES:
        assert _colour_present(small, TECH_COLOUR[code]), TECH_COLOUR[code]


def test_shrink_png_refuses_palettes_too_small_for_the_classes():
    with pytest.raises(ValueError, match="at least"):
        MP.shrink_png(b"\x89PNG", colours=8)


# --- Critical 2: draw order, grid on top, in every map --------------------------------
def test_draw_order_constant_puts_grid_last():
    assert MP.DRAW_ORDER[-2:] == [2, 1] and MP.DRAW_ORDER[0] == 99
    assert MP.zorder_of(1) > MP.zorder_of(2) > MP.zorder_of(5) > MP.zorder_of(3) > MP.zorder_of(99)


# --- Critical 3: the LCOE histogram keeps every served person -------------------------
def test_lcoe_histogram_keeps_people_above_the_last_regular_bin():
    df = frame()
    df.loc[df.id == 4, "MinimumOverallLCOE2040"] = 1.4         # far above 0.6
    h = M.lcoe_histogram(df, 2040)
    served = M.lcoe_mask(df, 2040)
    assert h["people"].sum() == pytest.approx(df.loc[served, "Pop2040"].sum())
    assert h["bin_right"].iloc[-1] >= 1.4 and bool(h["overflow"].iloc[-1])


def test_lcoe_histogram_newly_electrified_only_excludes_densification():
    df = frame()
    h = M.lcoe_histogram(df, 2040, newly_electrified_only=True)
    assert h["people"].sum() == pytest.approx(df.loc[M.lcoe_mask(df, 2040, True), "Pop2040"].sum())


# --- Important 8 and 13: corridor and hydro tables carry the densification-free LCOE and cumulative hydro
def test_corridor_and_subset_tables_report_newly_electrified_metrics():
    df = frame()
    geo = pd.DataFrame({"id": df.id, "kkt_main_dist_km": [1, 8, 4, 30, 90, 12]})
    t = M.corridor_table(df, geo, radius_km=10)                 # ids 1 (densification), 2, 3
    assert t["settlements"] == 3 and t["electrified_start_settlements"] == 1
    assert t["lcoe_energy_w_excl_dens"] == pytest.approx((0.11 * 120 + 0.32 * 40) / 160)
    assert t["people_newly_electrified_2040"] == pytest.approx(850)
    assert t["grid_share_newly_electrified"] == pytest.approx(600 / 850)
    s = M.subset_table(df, df["Admin_1"] == "Boke")
    assert "lcoe_energy_w_excl_dens" in s and "people_newly_electrified_2040" in s


def test_hydro_table_has_cumulative_columns():
    h = M.hydro_table(frame(), 2040)
    assert h["investment_musd_cum"] == pytest.approx((1e5 + 2e4) / 1e6)
    assert h["capacity_mw_cum"] == pytest.approx((10 + 2) / 1000)


# --- Important 11: consistency check uses the report's served mask ----------------------
def test_check_consistency_reports_rows_served_without_connections(report_sample_batch, repo_root, tmp_path):
    from report.data import check_consistency, load_batch
    b = load_batch(report_sample_batch, repo_root, cache_dir=tmp_path / "cache", log=lambda *a: None)
    res = check_consistency(b)
    guard = res[res["metric"] == "served_rows_without_connections"]
    assert len(guard) == 2 * len(b.scenarios)              # one per scenario and year
    assert (guard["settlements"] == 0).all() and guard["ok"].all()


# --- Important 4 and 5: computed clauses, densification-free demand comparison -------------
def _h(case_values):
    base = {"population_2040": 27.7e6, "people_reached_cum": 18.28e6, "investment_musd_cum": 1752.4, "capacity_mw_cum": 400.0,
            "usd_per_new_connection": 95.9, "people_per_musd": 10430.0, "lcoe_energy_w": 0.168, "lcoe_pop_w": 0.15,
            "lcoe_energy_w_excl_dens": 0.25, "grid_share_2040": 0.74, "offgrid_share_2040": 0.26, "sa_pv_people_2040": 5.7e6,
            "mg_pv_people_2040": 1.6e6, "mg_hydro_people_2040": 3.1e4, "grid_ext_people_2040": 2.1e6, "grid_ext_settlements_2040": 1200,
            "unserved_2030": 6.11e6, "investment_musd_2030": 420.6, "investment_musd_2040": 1331.8}
    out = {}
    for case, patch in case_values.items():
        d = dict(base)
        d.update(patch)
        out[case] = d
    return out


def test_demand_sensitivity_message_uses_densification_free_lcoe_and_computed_comparison():
    deltas = {"TD_High_plus": {"investment_musd_cum": 9.0, "lcoe_energy_w": -6.0, "lcoe_energy_w_excl_dens": 0.0}}
    sens = pd.DataFrame([{"demand_case": "BU", "grid_cost": g, "investment_musd_cum": 1800 + 60 * k, "switched_people": 3e6 * k,
                          "grid_ext_people": 5e6 - 1e6 * k, "lcoe_energy_w": 0.15 + 0.02 * k, "grid_ext_settlements": 1000 - 300 * k}
                         for k, g in enumerate([0.047, 0.078, 0.1, 0.22])])
    m = MS.km_demand_sensitivity(deltas, sens)
    assert "lowers the delivered cost" not in m["text"]             # the -6% all-settlements artefact is not reported
    assert "leaves unchanged" in m["text"] or "unchanged" in m["text"]
    assert "Demand tiers" not in m["text"] or "than the grid cost" not in m["text"] or "9%" in m["text"]


def test_cost_per_connection_message_has_no_uncomputed_causal_clause():
    m = MS.km_cost_per_connection(_h({"TD_Low": {"usd_per_new_connection": 90}, "TD_High": {"usd_per_new_connection": 140}}))
    assert "driven by" not in m["text"]


def test_new_key_messages_grid_extension_and_newly_electrified_lcoe():
    sens = pd.DataFrame([{"demand_case": c, "grid_cost": g, "investment_musd_cum": 1800, "switched_people": 0, "grid_ext_people": p,
                          "lcoe_energy_w": 0.15, "grid_ext_settlements": s}
                         for c in ("TD_Low", "TD_High", "BU") for g, p, s in zip([0.047, 0.078, 0.1, 0.22], [4e6, 3e6, 2e6, 0], [2000, 1500, 1200, 0])])
    m = MS.km_grid_extension_vanishes(sens)
    assert "0.22" in m["text"] and ("no settlement" in m["text"] or "disappears" in m["text"])
    h = _h({"TD_Low_minus": {"lcoe_energy_w_excl_dens": 0.499}, "TD_Low": {"lcoe_energy_w_excl_dens": 0.315}, "TD_High": {"lcoe_energy_w_excl_dens": 0.230}})
    m2 = MS.km_newly_electrified_lcoe(h)
    assert "0.23" in m2["text"] and "0.50" in m2["text"]


# --- Presentation: totals marked explicitly, per-metric formats, no empty legend entries ---
def test_table_html_marks_total_rows_explicitly():
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0]}, index=["x", "Total", "y"])
    html = table_html(df, {"a": "{:.0f}"}, total_rows=["Total"])
    assert html.count('class="total"') == 1 and 'class="total"><th>Total' in html


def test_stacked_by_tech_drops_all_zero_codes():
    rows = [{"demand_case": "BU", "year": y, "code": c, "value": (0.0 if c == 99 else 10.0)} for y in (2030, 2040) for c in TECH_ORDER]
    fig = F.stacked_by_tech(pd.DataFrame(rows), "value", "t", "y", ["BU"])
    assert "Not yet electrified" not in {t.name for t in fig.data}
