"""Grid-cost bins for one demand case: heat maps of the technology mix against the grid cost."""
import json
import shutil

import pandas as pd
import pytest

from report import figures as F
from report import metrics as M


@pytest.fixture
def batch_with_bins(report_core_sample_batch, tmp_path):
    """The sample batch plus three extra BU cost levels cloned from BU_g0.1 (0.12, 0.16, 0.2)."""
    b = tmp_path / "batch"
    shutil.copytree(report_core_sample_batch, b)
    for cost in (0.12, 0.16, 0.2):
        sid = f"BU_g{cost}"
        dst = b / sid
        shutil.copytree(b / "BU_g0.1", dst)
        for f in list(dst.iterdir()):
            if f.name.startswith("BU_g0.1_"):
                f.rename(dst / f.name.replace("BU_g0.1_", f"{sid}_"))
        m = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
        m["scenario_id"] = sid
        m["parameters"]["grid_generation_cost"] = cost
        (dst / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    return b


def test_cost_bin_table_has_one_row_per_cost_and_shares_sum_to_one(batch_with_bins, repo_root, tmp_path):
    from report.data import load_batch
    bt = load_batch(batch_with_bins, repo_root, cache_dir=tmp_path / "cache", log=lambda *a: None)
    t = M.cost_bin_table(bt, "BU")
    assert sorted(t.index) == [0.047, 0.078, 0.085, 0.1, 0.12, 0.16, 0.2, 0.22]
    share_cols = [c for c in t.columns if c.startswith("pop_share_")]
    assert len(share_cols) == 5 and (abs(t[share_cols].sum(axis=1) - 1) < 1e-9).all()
    nc_cols = [c for c in t.columns if c.startswith("nc_share_")]
    assert (abs(t[nc_cols].sum(axis=1) - 1) < 1e-9).all()
    for c in ("investment_musd_cum", "grid_ext_people_2040", "lcoe_energy_w_excl_dens", "usd_per_new_connection"):
        assert c in t.columns
    r = M.cost_bin_region_table(bt, "BU")
    assert list(r.columns) == sorted(t.index) and (r.values >= 0).all() and (r.values <= 1).all()


def test_heatmap_figure_shape():
    z = pd.DataFrame([[0.5, 0.3], [0.4, 0.4], [0.1, 0.3]], index=["Grid", "Mini-grid", "Stand-alone"], columns=[0.1, 0.22])
    fig = F.heatmap(z, "t", x_title="Grid cost (USD/kWh)", y_title="Technology", fmt=".0%")
    assert fig.data[0].type == "heatmap" and list(fig.data[0].x) == ["0.1", "0.22"]
    assert fig.data[0].text[0][0] == "50%"


def test_report_gets_the_bins_section(batch_with_bins, repo_root, tmp_path):
    from report.build import build
    path = build(batch_with_bins, repo_root, out_path=tmp_path / "r.html", inputs_dir=None, maps=False, geo=False,
                 sample=True, log=lambda *a: None)
    html = path.read_text(encoding="utf-8")
    assert 'id="cost-bins"' in html and 'id="fig-9-10"' in html and 'id="fig-9-10b"' in html and 'id="fig-9-11"' in html
    assert "Table 9.6" in html


def test_report_without_bins_says_so(report_core_sample_batch, repo_root, tmp_path):
    from report.build import build
    path = build(report_core_sample_batch, repo_root, out_path=tmp_path / "r0.html", inputs_dir=None, maps=False, geo=False,
                 sample=True, log=lambda *a: None)
    html = path.read_text(encoding="utf-8")
    assert 'id="cost-bins"' in html and "No cost bins" in html
