"""Helpers shared by the scenario runner tests (not a test module)."""
import json
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1] / "Scenarios" / "guinea_scenarios.json"
QUIET = lambda *a: None  # noqa: E731


def make_control(repo_root, tmp_path, calibrated_csv, scenario_ids):
    """The study file's defaults and calibration, real profiles and matrix, a sampled
    calibrated input, outputs under tmp_path, and the requested scenarios only."""
    import scenario_control
    doc = json.loads(STUDY.read_text(encoding="utf-8"))
    base = repo_root / "GuineaRuns" / "Inputs" / "Guinea Data"
    doc["paths"] = {
        "raw_input_csv": str(repo_root / "GuineaRuns" / "Inputs" / "OnSSET_InputFile_20261018_100416.csv"),
        "calibrated_csv": str(calibrated_csv),
        "pv_profile": str(base / "Solar profile" / "gn-2-pv.csv"),
        "wind_profile": str(base / "Wind profile" / "gn-2-wind.csv"),
        "productive_matrix": str(repo_root / "gep_onsset" / "productive_uses_matrix.json"),
        "output_root": str(tmp_path / "out"),
    }
    doc["scenarios"] = [s for s in doc["scenarios"] if s["id"] in scenario_ids]
    d = tmp_path / "Scenarios"
    d.mkdir(exist_ok=True)
    p = d / "control.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return scenario_control.load_control(p, repo_root=tmp_path, check_paths=True)
