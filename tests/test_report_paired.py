"""With and without the Koukoutamba line: the paired comparison of two batches (chapter 8)."""
import copy

import pandas as pd
import pytest

pytest.importorskip("plotly")

from report import metrics as M  # noqa: E402
from report import messages as MS  # noqa: E402
from report.constants import PRIMARY_COST, core_label  # noqa: E402
from report.data import load_batch  # noqa: E402


@pytest.fixture(scope="session")
def batch(report_sample_batch, repo_root, tmp_path_factory):
    return load_batch(report_sample_batch, repo_root, cache_dir=tmp_path_factory.mktemp("cache"), log=lambda *a: None)


def _altered(batch):
    """A copy of the batch where the BU primary scenario moves its first 20 grid settlements
    (grid extension, code 2, or densification, code 1, whichever the sample holds) to mini-grid PV
    (code 5) in 2040. Returns the copy, the number moved and the code they left."""
    alt = copy.deepcopy(batch)
    s = alt.core()[("BU", PRIMARY_COST)]
    code = 2 if (s.settlements["FinalElecCode2040"] == 2).any() else 1
    idx = s.settlements.index[s.settlements["FinalElecCode2040"] == code][:20]
    assert len(idx) > 0
    s.settlements.loc[idx, "FinalElecCode2040"] = 5
    return alt, len(idx), code


def test_paired_comparison_against_itself_has_zero_deltas(batch):
    df = M.paired_comparison(batch, batch)
    assert set(df["label"]) == set(batch.core_labels().values())
    assert list(df.columns[:3]) == ["label", "demand_case", "grid_cost"]
    assert (df["investment_musd_cum_pct"] == 0).all() and (df["switched_settlements"] == 0).all()
    assert (df["grid_ext_people_2040_with"] == df["grid_ext_people_2040_without"]).all()


def test_paired_comparison_counts_switches_and_people(batch):
    alt, n, code = _altered(batch)
    df = M.paired_comparison(batch, alt).set_index("label")
    row = df.loc[core_label("BU", PRIMARY_COST)]
    assert row["switched_settlements"] == n and row["switched_people"] > 0
    assert row["dre_share_new_connections_without"] > row["dre_share_new_connections_with"]
    assert row["top_flow"] == (code, 5)
    assert (df.drop(index=core_label("BU", PRIMARY_COST))["switched_settlements"] == 0).all()


def test_paired_comparison_restricted_to_a_corridor(batch):
    alt, n, _ = _altered(batch)
    ids = batch.core()[("BU", PRIMARY_COST)].settlements["id"]
    geo = pd.DataFrame({"id": ids, "kkt_main_dist_km": 5.0})
    geo.loc[geo.index[:10], "kkt_main_dist_km"] = 50.0
    df = M.paired_comparison(batch, alt, geo_attr=geo, radius_km=10).set_index("label")
    row = df.loc[core_label("BU", PRIMARY_COST)]
    assert row["corridor_settlements"] == len(ids) - 10
    assert row["corridor_switched_settlements"] <= n


def test_km_koukoutamba_names_the_primary_case_and_direction(batch):
    alt, n, _ = _altered(batch)
    df = M.paired_comparison(batch, alt)
    m = MS.km_koukoutamba(df)
    assert m["id"] == "km-koukoutamba" and "BU" in m["text"] and f"{n}" in m["text"]
    assert "Koukoutamba" in m["text"] and "nan" not in m["text"].lower().split()   # word-level: Manantali contains nan
    zero = MS.km_koukoutamba(M.paired_comparison(batch, batch))
    assert "no settlement" in zero["text"].lower()
