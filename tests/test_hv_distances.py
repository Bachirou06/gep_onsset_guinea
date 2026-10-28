"""tools/hv_distances.py: recompute CurrentHVLineDist and PlannedHVLineDist from line layers with the
GIS extraction notebook's method (clip to the admin boundary, densify every 100 m, nearest point to the
settlement centroid, zero where the settlement polygon crossed the line)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

gpd = pytest.importorskip("geopandas")
from shapely.geometry import LineString, Point, box  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import hv_distances as hv  # noqa: E402

CRS = "EPSG:32628"
X0, Y0 = 500_000.0, 1_100_000.0   # a point in Guinea in UTM 28N


def _to_4326(x, y):
    p = gpd.GeoSeries([Point(x, y)], crs=CRS).to_crs(4326).iloc[0]
    return p.x, p.y


@pytest.fixture
def world(tmp_path):
    """Admin square 20 km wide; line A runs west to east through its middle and 10 km beyond its
    eastern edge; line B runs north to south 5 km east of the square's centre."""
    admin = gpd.GeoDataFrame(geometry=[box(X0 - 10_000, Y0 - 10_000, X0 + 10_000, Y0 + 10_000)], crs=CRS).to_crs(4326)
    line_a = gpd.GeoDataFrame({"name": ["A"], "status": ["Existing"]},
                              geometry=[LineString([(X0 - 10_000, Y0), (X0 + 20_000, Y0)])], crs=CRS).to_crs(4326)
    line_b = gpd.GeoDataFrame({"name": ["B"], "status": ["Planned"]},
                              geometry=[LineString([(X0 + 5_000, Y0 - 10_000), (X0 + 5_000, Y0 + 10_000)])], crs=CRS).to_crs(4326)
    pa, pb, pc = tmp_path / "admin.gpkg", tmp_path / "a.gpkg", tmp_path / "b.gpkg"
    admin.to_file(pa, driver="GPKG"); line_a.to_file(pb, driver="GPKG"); line_b.to_file(pc, driver="GPKG")
    # settlements: s1 one km north of A; s2 on A; s3 outside the square, 15 km east, 2 km north of A
    # (A is clipped at the square's edge; the densified points stop 100 m short of the clipped end,
    # as in the notebook, so s3's nearest point is (X0+9900, Y0), 5.478 km away)
    pts = [(X0, Y0 + 1_000), (X0 - 3_000, Y0), (X0 + 15_000, Y0 + 2_000)]
    rows = []
    for i, (x, y) in enumerate(pts, 1):
        lon, lat = _to_4326(x, y)
        rows.append({"id": i, "X_deg": lon, "Y_deg": lat, "Pop": 100 * i,
                     "CurrentHVLineDist": [1.0, 0.0, 5.478][i - 1], "PlannedHVLineDist": [1.0, 0.0, 5.478][i - 1],
                     "Other": "keep"})
    csv = tmp_path / "in.csv"
    pd.DataFrame(rows).to_csv(csv, index=False)
    return {"admin": pa, "a": pb, "b": pc, "csv": csv, "dir": tmp_path}


def test_distances_clip_densify_and_measure(world):
    df = pd.read_csv(world["csv"])
    admin = gpd.read_file(world["admin"])
    d = hv.distances_km(df, [gpd.read_file(world["a"])], admin, CRS)
    assert d == pytest.approx([1.0, 0.0, 5.478], abs=0.06)   # 100 m densification: error below 50 m


def test_read_layer_spec_filters_on_a_field(world):
    both = pd.concat([gpd.read_file(world["a"]), gpd.read_file(world["b"])])
    p = world["dir"] / "both.gpkg"
    gpd.GeoDataFrame(both, crs=4326).to_file(p, driver="GPKG")
    assert list(hv.read_layer(f"{p}|status=Existing")["name"]) == ["A"]
    assert len(hv.read_layer(str(p))) == 2


def test_zero_rule_keeps_zero_only_when_the_same_line_remains():
    old_col = np.array([0.0, 0.0, 2.0])
    old_centroid = np.array([0.3, 0.3, 2.0])      # the polygon crossed a line 0.3 km from its centroid
    new_d = np.array([0.3, 4.0, 2.0])             # row 1: same line still there; row 2: that line removed
    out = hv.apply_zero_rule(new_d, old_col, old_centroid)
    assert out.tolist() == [0.0, 4.0, 2.0]


def test_recompute_replaces_the_two_columns_and_writes_a_sidecar(world):
    out = world["dir"] / "out.csv"
    summary = hv.recompute(world["csv"], out, existing=[str(world["a"])], planned=[str(world["b"])],
                           admin=str(world["admin"]), old_layers=[str(world["a"])], crs=CRS, note="test")
    df = pd.read_csv(out)
    assert df["CurrentHVLineDist"].tolist() == pytest.approx([1.0, 0.0, 5.478], abs=0.06)
    assert df["PlannedHVLineDist"].tolist() == pytest.approx([5.0, 8.0, 10.0], abs=0.06)
    assert df["Other"].tolist() == ["keep"] * 3 and df["Pop"].tolist() == [100, 200, 300]
    side = json.loads(out.with_suffix(".hv_distances.json").read_text(encoding="utf-8"))
    assert side["crs"] == CRS and side["note"] == "test"
    assert side["existing"][0]["sha256"] and side["existing"][0]["features"] == 1
    assert side["stats"]["CurrentHVLineDist"]["zero_rows"] == 1
    assert summary["rows"] == 3
