"""Supply-side variants (optgrid, optgrid_optmg) in the report's data layer."""
import json
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def batch_with_variants(report_core_sample_batch, tmp_path):
    """The sample batch plus a copy of BU_g0.1 posing as BU_optgrid_g0.1 (variant optgrid)."""
    b = tmp_path / "batch"
    shutil.copytree(report_core_sample_batch, b)
    src, dst = b / "BU_g0.1", b / "BU_optgrid_g0.1"
    shutil.copytree(src, dst)
    for f in list(dst.iterdir()):
        if f.name.startswith("BU_g0.1_"):
            f.rename(dst / f.name.replace("BU_g0.1_", "BU_optgrid_g0.1_"))
    m = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
    m["scenario_id"] = "BU_optgrid_g0.1"
    m["variant"] = "optgrid"
    m["parameters"]["annual_new_grid_connections_limit_intermediate"] = 999999999
    (dst / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    return b


def test_batch_keeps_reference_and_variant_apart(batch_with_variants, repo_root, tmp_path):
    from report.data import load_batch
    bt = load_batch(batch_with_variants, repo_root, cache_dir=tmp_path / "cache", log=lambda *a: None)
    assert len(bt.scenarios) == 21 + 1          # 21 reference-sweep scenarios in the core sample plus the synthetic variant
    assert bt.scenarios["BU_optgrid_g0.1"].variant == "optgrid"
    assert bt.scenarios["BU_g0.1"].variant == "reference"
    ref = [s.scenario_id for s in bt.reference()]
    assert "BU_g0.1" in ref and "BU_optgrid_g0.1" not in ref
    assert set(bt.by_case("BU")) == {0.047, 0.078, 0.1, 0.22}            # reference variant only
    v = bt.variants("BU")
    assert set(v) == {"optgrid"} and v["optgrid"].scenario_id == "BU_optgrid_g0.1"
    assert bt.variant_names() == ["optgrid"]


def test_report_gets_a_supply_variants_section(batch_with_variants, repo_root, tmp_path):
    from report.build import build
    path = build(batch_with_variants, repo_root, out_path=tmp_path / "r.html", inputs_dir=None, maps=False, geo=False,
                 sample=True, log=lambda *a: None)
    html = path.read_text(encoding="utf-8")
    assert 'id="supply-variants"' in html and "Table 9.4" in html and 'id="fig-9-8"' in html
    assert "optgrid" in html and "full grid expansion" in html.lower() or "Optimistic grid expansion" in html


def test_report_without_variants_says_so(report_core_sample_batch, repo_root, tmp_path):
    from report.build import build
    path = build(report_core_sample_batch, repo_root, out_path=tmp_path / "r0.html", inputs_dir=None, maps=False, geo=False,
                 sample=True, log=lambda *a: None)
    html = path.read_text(encoding="utf-8")
    assert 'id="supply-variants"' in html and "No supply-side variant" in html


def test_manifest_without_variant_is_reference(report_core_sample_batch, repo_root, tmp_path):
    from report.data import load_batch
    bt = load_batch(report_core_sample_batch, repo_root, cache_dir=tmp_path / "cache", log=lambda *a: None)
    assert all(s.variant == "reference" for s in bt.scenarios.values())
    assert bt.variant_names() == []
