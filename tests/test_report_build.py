"""End-to-end build on the 500-settlement sample batch, then checks on the HTML."""
import json
import re
from pathlib import Path

import pytest

pytest.importorskip("plotly")
pytest.importorskip("jinja2")

from report.constants import CHAPTERS  # noqa: E402

INPUTS = Path(__file__).resolve().parents[1] / "GuineaRuns" / "Inputs" / "Guinea Data"
EXPECTED_FIGURES = ["fig-4-1", "fig-4-2", "fig-4-3", "fig-4-4", "fig-4-6", "fig-5-1", "fig-7-2",
                    "fig-9-1", "fig-9-2", "fig-9-3", "fig-9-4", "fig-9-5", "fig-9-7"]
EXPECTED_MAPS = ["map-3-1", "map-4-5-BU", "map-4-5-TD_Low", "map-6-1", "map-7-1-BU", "map-9-6"]


@pytest.fixture(scope="session")
def built(report_sample_batch, repo_root, tmp_path_factory):
    from report.build import build
    out_dir = tmp_path_factory.mktemp("report")
    geo = INPUTS.exists()
    path = build(report_sample_batch, repo_root, out_path=out_dir / "report.html", inputs_dir=INPUTS if geo else None,
                 maps=True, geo=geo, sample=True, log=lambda *a: None)
    return path, out_dir


def _body(html: str) -> str:
    html = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    html = re.sub(r"<style.*?</style>", "", html, flags=re.S)
    html = re.sub(r"data:image/png;base64,[A-Za-z0-9+/=]+", "IMG", html)
    return html


def test_build_writes_html_and_manifest(built):
    path, out_dir = built
    assert path.exists() and path.stat().st_size > 5_000_000      # plotly.js inlined
    m = json.loads((out_dir / "build_manifest.json").read_text(encoding="utf-8"))
    assert m["batch"] and m["n_scenarios"] == 14 and m["sample"] is True
    assert "assets" in m and m["html_bytes"] == path.stat().st_size
    assert m["consistency"] == "skipped (sample)"


def test_html_has_every_chapter_and_figure(built):
    html = built[0].read_text(encoding="utf-8")
    for anchor, title in CHAPTERS:
        assert f'id="{anchor}"' in html, anchor
        assert title in html, title
    for fid in EXPECTED_FIGURES:
        assert f'id="{fid}"' in html, fid
    for mid in EXPECTED_MAPS:
        assert f'id="{mid}"' in html, mid
    assert html.count("<figcaption") >= 25


def test_html_body_has_no_nan_none_dashes_or_branding(built):
    body = _body(built[0].read_text(encoding="utf-8"))
    assert not re.search(r"\bnan\b|\bNaN\b|\bNone\b", body)
    assert "—" not in body and "IRENA" not in body


def test_html_provenance_box(built):
    html = built[0].read_text(encoding="utf-8")
    assert "Provenance" in html and "sha256" in html.lower()
    assert "git" in html.lower() and "comparison_summary.csv" in html


def test_html_key_messages_and_tables(built):
    html = built[0].read_text(encoding="utf-8")
    assert html.count('class="key-message"') >= 8
    assert "Table 4.1" in html and "Table 5.1" in html and "Table 9.3" in html
    assert "Table 8.1" in html or INPUTS.exists() is False


@pytest.mark.slow
def test_full_build_on_real_batch(report_batch_dir, repo_root, tmp_path):
    from report.build import build
    path = build(report_batch_dir, repo_root, out_path=tmp_path / "full.html", inputs_dir=INPUTS,
                 maps=True, geo=True, log=lambda *a: None)
    m = json.loads((tmp_path / "build_manifest.json").read_text(encoding="utf-8"))
    assert m["consistency"] == "PASS"
    assert path.stat().st_size < 25_000_000
    html = path.read_text(encoding="utf-8")
    assert "1,752" in html            # TD_Low_g0.1 cumulative investment 420.59 + 1,331.83
