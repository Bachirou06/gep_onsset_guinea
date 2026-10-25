import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _notebook():
    return json.loads((REPO / "GEP_Generator.ipynb").read_text(encoding="utf-8"))


def _code(nb):
    return [("".join(c["source"])) for c in nb["cells"] if c["cell_type"] == "code"]


def test_notebook_calls_runner_and_has_no_scenario_loop():
    nb = _notebook()
    src = "\n".join(_code(nb))
    assert "Bachirou" not in src
    assert "for year in yearsofanalysis" not in src
    assert "run_scenario(" in src and "load_control(" in src
    assert "filedialog.askdirectory" not in src
    new = [c for c in _code(nb) if "run_scenario(" in c][0]
    compile(new, "cell", "exec")


def test_notebook_keeps_calibration_cells_and_strips_outputs():
    nb = _notebook()
    src = "\n".join(_code(nb))
    assert "elec_current_and_future(" in src and "GIN_calibrated.csv" in src
    assert all(c.get("outputs", []) == [] for c in nb["cells"] if c["cell_type"] == "code")
    assert all(c.get("execution_count") is None for c in nb["cells"] if c["cell_type"] == "code")


def test_notebook_sys_path_is_relative():
    nb = _notebook()
    first = _code(nb)[0]
    assert "gep_onsset" in first and "C:\\\\Users" not in first and "C:\\Users" not in first
