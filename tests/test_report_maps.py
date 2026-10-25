from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("matplotlib")

from report import maps as MP  # noqa: E402

INPUTS = Path(__file__).resolve().parents[1] / "GuineaRuns" / "Inputs" / "Guinea Data"


@pytest.fixture(scope="session")
def layers():
    gpd = pytest.importorskip("geopandas")
    from report.geo import load_layers
    if not (INPUTS / "Boundaries" / "gadm41_GIN_1.shp").exists():
        pytest.skip("GIS inputs not available")
    return load_layers(INPUTS)


@pytest.fixture(scope="session")
def sample_df(report_sample_batch, tmp_path_factory):
    from report.data import load_settlements
    return load_settlements(report_sample_batch / "BU_g0.1", tmp_path_factory.mktemp("cache"))


def _is_png(b: bytes) -> bool:
    return isinstance(b, bytes) and b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) > 20_000


def test_legend_entries_cover_all_people(sample_df):
    entries = MP.legend_entries(sample_df, 2040)
    assert [e["code"] for e in entries] == [c for c in (1, 2, 5, 7, 3) if (sample_df["FinalElecCode2040"] == c).any()]
    assert sum(e["people"] for e in entries) == pytest.approx(sample_df["Pop2040"].sum())
    assert sum(e["settlements"] for e in entries) == len(sample_df)
    assert abs(sum(e["share"] for e in entries) - 100.0) < 1e-6
    assert "Grid densification" in entries[0]["label"] and "(" in MP.legend_text(entries[0])


def test_technology_map_renders_png_with_layers(sample_df, layers):
    png = MP.technology_map(sample_df, 2040, layers, title="Least-cost technology 2040",
                            subtitle="Bottom-up demand, grid cost 0.1 USD/kWh", source_note="test")
    assert _is_png(png)
    uri = MP.png_data_uri(png)
    assert uri.startswith("data:image/png;base64,")
    small = MP.shrink_png(png, colours=64)
    assert _is_png(small) and len(small) < len(png)


def test_technology_map_renders_without_layers(sample_df):
    assert _is_png(MP.technology_map(sample_df, 2040, None, title="t", subtitle="s", source_note="n"))


def test_other_maps_render(sample_df, layers, tmp_path):
    from report.geo import settlement_geo_attributes
    assert _is_png(MP.two_panel_map(sample_df, layers, title="2030 and 2040", source_note="n"))
    alt = sample_df.copy()
    alt.loc[alt.index[:50], "FinalElecCode2040"] = 5
    assert _is_png(MP.switch_map(sample_df, alt, 2040, layers, "0.1", "0.22", title="Switches", source_note="n"))
    assert _is_png(MP.status_map(sample_df, layers, title="Start year", source_note="n"))
    assert _is_png(MP.hydro_map(sample_df, layers, title="Hydro", source_note="n"))
    geo = settlement_geo_attributes(sample_df[["id", "X_deg", "Y_deg"]], layers, tmp_path / "geo")
    assert _is_png(MP.corridor_map(sample_df, geo, layers, 10, title="Corridor", source_note="n"))
