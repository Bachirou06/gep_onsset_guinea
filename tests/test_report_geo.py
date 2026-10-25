from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("geopandas")

INPUTS = Path(__file__).resolve().parents[1] / "GuineaRuns" / "Inputs" / "Guinea Data"


@pytest.fixture(scope="session")
def layers():
    from report.geo import load_layers
    if not (INPUTS / "Boundaries" / "gadm41_GIN_1.shp").exists():
        pytest.skip("GIS inputs not available")
    return load_layers(INPUTS)


def test_layers_loaded_in_wgs84_with_expected_counts(layers):
    assert len(layers["adm0"]) == 1 and len(layers["adm1"]) == 8
    assert layers["adm1"].crs.to_epsg() == 4326 and layers["protected"].crs.to_epsg() == 4326
    assert len(layers["kkt"]) == 2 and len(layers["kkt_main"]) == 1
    assert "Manantali" in str(layers["kkt_main"].iloc[0]["Name"]) or "Linsan" in str(layers["kkt_main"].iloc[0]["Name"])
    assert len(layers["protected"]) == 117 and len(layers["moyen_bafing"]) == 1
    assert len(layers["affected_localities"]) == 5 and len(layers["protected_span_hv"]) == 9
    assert len(layers["hv_existing"]) > 0 and len(layers["mini_hydro"]) > 0


def test_settlement_geo_attributes_on_sample(layers, report_sample_batch, tmp_path):
    from report.data import load_settlements
    from report.geo import settlement_geo_attributes
    df = load_settlements(report_sample_batch / "BU_g0.1", tmp_path / "cache")
    g = settlement_geo_attributes(df[["id", "X_deg", "Y_deg"]], layers, tmp_path / "geo", radii_km=(5, 10, 25))
    assert list(g.columns) == ["id", "kkt_main_dist_km", "kkt_any_dist_km", "in_protected_area",
                               "protected_area_name", "in_moyen_bafing", "affected_locality",
                               "in_protected_span_hv", "region_gadm"]
    assert len(g) == 500 and g["id"].is_unique
    assert (g["kkt_main_dist_km"] >= 0).all() and (g["kkt_any_dist_km"] <= g["kkt_main_dist_km"] + 1e-9).all()
    assert g["kkt_main_dist_km"].max() > 100          # the sample spans the country
    assert g["in_protected_area"].dtype == bool
    assert (tmp_path / "geo" / "geo_attributes.parquet").exists()
    # second call reuses the cache
    t0 = (tmp_path / "geo" / "geo_attributes.parquet").stat().st_mtime_ns
    settlement_geo_attributes(df[["id", "X_deg", "Y_deg"]], layers, tmp_path / "geo", radii_km=(5, 10, 25))
    assert (tmp_path / "geo" / "geo_attributes.parquet").stat().st_mtime_ns == t0


def test_distance_known_point(layers, tmp_path):
    """A point placed on the Linsan to Manantali line must be at distance about 0."""
    from report.geo import settlement_geo_attributes
    line = layers["kkt_main"].geometry.iloc[0]
    p = line.interpolate(0.5, normalized=True)
    df = pd.DataFrame({"id": [1, 2], "X_deg": [p.x, -8.8], "Y_deg": [p.y, 7.75]})   # second near Nzerekore
    g = settlement_geo_attributes(df, layers, tmp_path / "geo2")
    assert g.loc[g.id == 1, "kkt_main_dist_km"].iloc[0] < 0.5
    assert g.loc[g.id == 2, "kkt_main_dist_km"].iloc[0] > 200
    assert g.loc[g.id == 2, "region_gadm"].iloc[0].startswith("Nz")
