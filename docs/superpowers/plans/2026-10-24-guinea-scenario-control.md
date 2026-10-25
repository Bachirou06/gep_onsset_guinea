# Guinea Scenario Control File and Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One JSON control file declaring the fourteen Guinea GEP-OnSSET scenarios, and one runner that executes any subset of them from the command line or the notebook, reproducing the notebook's results bit for bit.

**Architecture:** `gep_onsset/scenario_control.py` loads, validates and resolves the control file (pure, no model). `gep_onsset/scenario_runner.py` holds the notebook's cells 32 to 64 as functions taking a resolved parameter dict, plus calibration, manifest and batch loop. `run_scenarios.py` at the repository root is the command line. The notebook's scenario section becomes a call into the runner. Tests sample the real calibrated file on the fly, never commit data, and a slow regression test reproduces the shared Scenario_U3R1_0.047 run.

**Tech Stack:** Python 3.12 (conda env `gep_guinea`, fallback `OnSSET_SENEGAL` 3.10), pandas 2.3.x, numpy 2.0.x, scipy, matplotlib, openpyxl, pytest. No new orchestration dependency.

**Spec:** `docs/superpowers/specs/2026-10-24-guinea-scenario-control-design.md`

## Global Constraints

- No change to numerics in `gep_onsset/onsset.py`, `hybrids_pv.py`, `hybrids_wind.py`, `guinea_demand_customization.py`.
- Lift notebook cells verbatim; the only edits are notebook globals becoming parameters and paths becoming arguments. Reference: `GEP_Generator.ipynb` at commit `fff30bd`, dumped per cell at `C:\Users\OOdou\AppData\Local\Temp\claude\C--PrivateToolsDevelopment\1dc2d627-b19e-4ac6-a038-2789a74189e8\scratchpad\repro\notebook_cells.py` (regenerate with `json.load` over `nb['cells']` if missing).
- Work on branch `scenario-control` off `main`; commit locally with author Thierry Odou and trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`; never push.
- Data never committed. `GuineaRuns/` is excluded via `.git/info/exclude`; `.gitignore` also ignores `*Results.csv`, `*Summaries.csv`, `*Variables.csv`, `Calibrated/`, `test/`. Tests live in `tests/` (not `test/`). Test caches go to `tests/_cache/` which Task 1 adds to `.gitignore`.
- Package import style is flat: modules in `gep_onsset/` import each other by bare name (`from onsset import *`, `from hybrids_pv import ...`). New modules follow this; callers put `gep_onsset/` on `sys.path`.
- Control file keys use the notebook variable names. Per-year cost dictionaries are JSON objects `{"inf": 2950}` and become `{float("inf"): 2950}` on load.
- Input file: `GuineaRuns/Inputs/OnSSET_InputFile_20261018_100416.csv` (confirmed by the colleague 2026-10-24). Hourly profiles: `GuineaRuns/Inputs/Guinea Data/Solar profile/gn-2-pv.csv`, `GuineaRuns/Inputs/Guinea Data/Wind profile/gn-2-wind.csv`.
- Output file names per scenario: `<id>_Results.csv`, `<id>_Summaries.csv`, `<id>_Variables.csv`, `manifest.json`. Results keep the `index` column the notebook's `reset_index` adds.
- British spelling, no em-dashes, no contractions in any user-facing or file text.
- Scenario ids are filename-safe: `^[A-Za-z0-9_.-]+$`.
- Run each pytest command with the chosen environment's python, from the repository root: `conda run -n gep_guinea python -m pytest ...` (or `-n OnSSET_SENEGAL`).

## Review Focus

1. A scenario id with `/`, `:` or a space would create a broken output folder on Windows; load must refuse it. Test in Task 2.
2. A per-year cost written as a bare number instead of `{"inf": value}` would silently become a wrong `capital_cost` type; load must refuse it. Test in Task 2.
3. A calibrated CSV missing one of the facility count columns makes `guinea_demand_customization` print a warning and continue with zeros, producing wrong demand silently; `run_scenario` must fail before the loop with the missing column named. Test in Task 6.
4. A scenario folder left by an interrupted run (CSV present, no manifest, or manifest without `"status": "complete"`) must be re-run, not skipped. Test in Task 7.
5. `--only` with an unknown id must fail before any run and list the valid ids. Test in Task 7.

---

### Task 1: Environment, branch and test scaffolding

**Files:**
- Create: `environment_guinea.yml`
- Create: `tests/__init__.py` (empty), `tests/conftest.py`, `pytest.ini`
- Modify: `.gitignore` (append `tests/_cache/`)

**Interfaces:**
- Produces: pytest fixtures `repo_root` (Path), `gep_path` (adds `gep_onsset/` to `sys.path`, returns it), `sample_calibrated` (Path to a 500-row seeded sample of `GuineaRuns/Inputs/GIN_calibrated.csv`, cached at `tests/_cache/sample_calibrated_500.csv`), `sample_raw` (same from `OnSSET_InputFile_20261018_100416.csv`), `profiles` (dict with keys `pv`, `wind`, absolute paths). Each data fixture calls `pytest.skip` when its source file is absent. Marker `slow` registered in `pytest.ini`.

- [ ] **Step 1: Create the branch**

Run: `git -C C:/PrivateToolsDevelopment/Projects/GuineaWork checkout -b scenario-control`
Expected: `Switched to a new branch 'scenario-control'`

- [ ] **Step 2: Write `environment_guinea.yml`**

Name `gep_guinea`, channels `conda-forge`, dependencies: `python=3.12`, `pandas=2.3.*`, `numpy=2.0.*`, `scipy`, `matplotlib`, `seaborn`, `openpyxl`, `pytest`, `ipykernel`, `jupyter`. Start from the pins in `OnSSET_GIS_Extraction_notebook-master/onsset_env.yml` where they exist. Do not include geopandas.

- [ ] **Step 3: Create the environment**

Run: `conda env create -f environment_guinea.yml`
Expected: solve succeeds and `conda run -n gep_guinea python -c "import pandas, numpy, scipy; print(pandas.__version__)"` prints a 2.3.x version. If the solve fails after one retry, use `OnSSET_SENEGAL` for every later command and note it in the commit message of this task.

- [ ] **Step 4: Write `pytest.ini`**

```ini
[pytest]
testpaths = tests
markers =
    slow: full-size runs, minutes each
addopts = -m "not slow"
```

- [ ] **Step 5: Write `tests/conftest.py`** with the fixtures listed in Interfaces. Sampling: `pd.read_csv(src, low_memory=False).sample(n=500, random_state=42).sort_values("id")`, written once to the cache path and reused.

- [ ] **Step 6: Write a smoke test `tests/test_environment.py`**

```python
def test_onsset_imports(gep_path):
    import onsset
    assert hasattr(onsset, "SettlementProcessor")

def test_sample_fixture_shape(sample_calibrated):
    import pandas as pd
    df = pd.read_csv(sample_calibrated)
    assert len(df) == 500 and "hc_count_com_hc" in df.columns
```

- [ ] **Step 7: Run the tests**

Run: `conda run -n gep_guinea python -m pytest tests/test_environment.py -v`
Expected: 2 passed.

- [ ] **Step 8: Append `tests/_cache/` to `.gitignore` and commit**

```bash
git add environment_guinea.yml pytest.ini tests/__init__.py tests/conftest.py tests/test_environment.py .gitignore
git commit -m "chore: test scaffolding and pinned environment for the scenario runner"
```

---

### Task 2: Control file loader and validator

**Files:**
- Create: `gep_onsset/scenario_control.py`
- Test: `tests/test_scenario_control.py`

**Interfaces:**
- Produces:
  - `SCENARIO_KEYS: frozenset[str]` of allowed `defaults` keys: `start_year, end_year, intermediate_year, electrification_rate_target, intermediate_electrification_target, urban_target_tier, rural_target_tier, num_people_per_hh_urban, num_people_per_hh_rural, prioritization, auto_intensification, annual_new_grid_connections_limit_intermediate, annual_new_grid_connections_limit_end, annual_grid_cap_gen_limit_intermediate, annual_grid_cap_gen_limit_end, grid_generation_cost, grid_power_plants_capital_cost, grid_losses, existing_grid_cost_ratio, pv_adjustment_factor, discount_rate, pop_threshold, diesel_price, diesel_techs, tech_switches, sa_diesel_capital_cost, mg_diesel_capital_cost, mg_pv_capital_cost, mg_wind_capital_cost, mg_hydro_capital_cost, sa_pv_capital_cost_1 .. sa_pv_capital_cost_5, hv_line_capacity, hv_line_cost, mv_line_cost, mv_line_capacity, mv_line_max_length, mv_increase_rate, max_mv_line_dist, MV_line_amperage_limit, lv_line_capacity, lv_line_max_length, lv_line_cost, service_Transf_type, service_Transf_cost, max_nodes_per_serv_trans, hv_lv_transformer_cost, hv_mv_transformer_cost, mv_lv_transformer_cost, mv_mv_transformer_cost, tier_1, tier_2, tier_3, tier_4, tier_5, productive_demand, productive_preference, cost_choice`.
  - `CALIBRATION_KEYS: frozenset[str]`: `pop_start_year, end_year_pop, urban_ratio_start_year, urban_ratio_end_year, elec_ratio_start_year, urban_elec_ratio, rural_elec_ratio, min_night_lights, min_pop, max_service_transformer_distance, max_mv_line_distance, max_hv_line_distance`.
  - `NOT_OVERRIDABLE: frozenset[str]` = `{start_year, intermediate_year, end_year}` (shared with calibration).
  - `PATH_KEYS` = `raw_input_csv, calibrated_csv, pv_profile, wind_profile, productive_matrix, output_root`.
  - `COST_DICT_KEYS` = the five `*_capital_cost` keys that take `{"inf": value}`.
  - `class ControlError(ValueError)`.
  - `@dataclass Scenario(id: str, demand_case: str, label: str, overrides: dict, legacy_name: str | None)`.
  - `@dataclass Control(path: Path, repo_root: Path, meta: dict, paths: dict[str, Path], calibration: dict, defaults: dict, scenarios: list[Scenario], sha256: str)` with methods `resolved(scenario_id) -> dict` (defaults updated by overrides; cost dicts already converted), `scenario(scenario_id) -> Scenario`, `ids() -> list[str]`.
  - `load_control(path: str | Path, repo_root: str | Path | None = None, check_paths: bool = True) -> Control`. `repo_root` defaults to the parent of the control file's `Scenarios/` folder. `check_paths=True` requires every path except `output_root` and `calibrated_csv` to exist.

- [ ] **Step 1: Write the failing tests** in `tests/test_scenario_control.py` using a `minimal_control(tmp_path, **patch)` helper that writes a valid JSON with one scenario, then:

```python
def test_resolved_applies_overrides(tmp_path):
    c = load_control(minimal_control(tmp_path), check_paths=False)
    p = c.resolved("S1")
    assert p["urban_target_tier"] == 3 and p["grid_generation_cost"] == 0.047

def test_cost_dict_converted(tmp_path):
    c = load_control(minimal_control(tmp_path), check_paths=False)
    assert c.resolved("S1")["mg_pv_capital_cost"] == {float("inf"): 2950}

def test_unknown_default_key_rejected(tmp_path):
    with pytest.raises(ControlError, match="unknown key 'grid_lossess'"):
        load_control(minimal_control(tmp_path, defaults_extra={"grid_lossess": 0.1}), check_paths=False)

def test_duplicate_id_rejected(tmp_path): ...  # match="duplicate scenario id 'S1'"
def test_unsafe_id_rejected(tmp_path): ...     # id "TD Low/g0.1" -> match="not filename-safe"
def test_bare_number_cost_rejected(tmp_path): ...  # mg_pv_capital_cost: 2950 -> match="must be an object with key 'inf'"
def test_calibration_key_override_rejected(tmp_path): ...  # overrides {"urban_ratio_end_year": 0.5} -> match="calibration-stage key"
def test_year_override_rejected(tmp_path): ...  # overrides {"end_year": 2035} -> match="cannot be overridden"
def test_missing_path_rejected(tmp_path): ...  # check_paths=True with absent pv_profile -> match="pv_profile"
def test_sha256_and_order(tmp_path): ...  # c.sha256 is 64 hex chars; c.ids() preserves file order
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n gep_guinea python -m pytest tests/test_scenario_control.py -v`
Expected: FAIL, `ModuleNotFoundError: scenario_control`.

- [ ] **Step 3: Implement `gep_onsset/scenario_control.py`** per Interfaces. Validation order: top-level blocks present (`meta, paths, calibration, defaults, scenarios`), unknown keys in `defaults` and `calibration`, every key of `SCENARIO_KEYS` present in `defaults` (missing key is an error naming it), scenario ids, override keys, cost dicts, paths. `tech_switches` must be a dict with exactly the keys `sa_pv, mg_hydro, mg_pv, mg_pv_hybrid, mg_wind_hybrid` and 0/1 values.

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n gep_guinea python -m pytest tests/test_scenario_control.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add gep_onsset/scenario_control.py tests/test_scenario_control.py
git commit -m "feat: scenario control file loader and validator"
```

---

### Task 3: The study control file and the regression control file

**Files:**
- Create: `Scenarios/guinea_scenarios.json`, `Scenarios/regression_u3r1.json`
- Test: `tests/test_scenario_files.py`

**Interfaces:**
- Consumes: `load_control` (Task 2).
- Produces: the two files. Defaults values copied from `GuineaRuns/Outputs/D2_BOT_0.047_1_10km_H_GL127/D2_BOT_0.047_1_10km_H_GL127_Variables.csv` and from notebook cells 26 to 32, 47, 48, 50, 52 for the keys that file lacks (`tech_switches = {"sa_pv":1,"mg_hydro":1,"mg_pv":0,"mg_pv_hybrid":1,"mg_wind_hybrid":0}`, `diesel_techs 0`, `hv_line_capacity 69`, `MV_line_amperage_limit 8`, `service_Transf_type 50`, `service_Transf_cost 4250`, `max_nodes_per_serv_trans 300`, `hv_mv_transformer_cost 25000`, `mv_lv_transformer_cost 10000`, `mv_mv_transformer_cost 10000`, `tier_1..5 = 38.7, 219, 803, 2117, 2993`, `productive_demand 1`, `productive_preference "Low"`, `cost_choice 2`, `grid_generation_cost 0.1`, `pop_threshold 0`, `grid_losses 0.167`).

- [ ] **Step 1: Write the failing tests**

```python
STUDY = Path("Scenarios/guinea_scenarios.json")

def test_study_file_loads_and_has_fourteen_in_order():
    c = load_control(STUDY)
    assert c.ids() == ["TD_Low_g0.1","TD_Low_minus_g0.1","TD_High_g0.1","TD_High_plus_g0.1","BU_g0.1",
                       "TD_Low_g0.047","TD_High_g0.047","BU_g0.047",
                       "TD_Low_g0.078","TD_High_g0.078","BU_g0.078",
                       "TD_Low_g0.22","TD_High_g0.22","BU_g0.22"]

@pytest.mark.parametrize("sid,ut,rt,gc", [
    ("TD_Low_g0.1",3,2,0.1),("TD_Low_minus_g0.1",3,1,0.1),("TD_High_g0.1",4,3,0.1),
    ("TD_High_plus_g0.1",5,3,0.1),("BU_g0.1",6,6,0.1),("BU_g0.22",6,6,0.22),("TD_High_g0.047",4,3,0.047)])
def test_study_levers(sid, ut, rt, gc):
    p = load_control(STUDY).resolved(sid)
    assert (p["urban_target_tier"], p["rural_target_tier"], p["grid_generation_cost"]) == (ut, rt, gc)

def test_study_defaults_pin_table1_assumptions():
    d = load_control(STUDY).defaults
    assert d["annual_new_grid_connections_limit_intermediate"] == 127
    assert d["annual_grid_cap_gen_limit_intermediate"] == 90
    assert d["discount_rate"] == 0.08 and d["grid_generation_cost"] == 0.1
    assert d["tech_switches"] == {"sa_pv":1,"mg_hydro":1,"mg_pv":0,"mg_pv_hybrid":1,"mg_wind_hybrid":0}

def test_study_meta_records_superseded_runs_and_hydro_rules():
    m = load_control(STUDY).meta
    notes = " ".join(m["notes"])
    assert "10 km" in notes and "1 MW" in notes and "D2_BOT_0.047_1_10km_H_GL127" in m["superseded_runs"]

def test_regression_file():
    c = load_control(Path("Scenarios/regression_u3r1.json"))
    p = c.resolved("REF_U3R1_g0.047")
    assert (p["urban_target_tier"], p["rural_target_tier"], p["grid_generation_cost"]) == (3, 1, 0.047)
    assert c.calibration["urban_ratio_start_year"] == 0.45 and c.calibration["urban_ratio_end_year"] == 0.453
    assert c.scenario("REF_U3R1_g0.047").legacy_name == "Scenario_U3R1_0.047"
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: FAIL, file not found.

- [ ] **Step 3: Write `Scenarios/guinea_scenarios.json`** with `meta` (`schema_version "1.0"`, `study`, `created "2026-10-24"`, `notes` listing the hard-coded 10 km hydro viability rule and the 1 MW upstream filter, `superseded_runs` listing the five D-run names with the reason "pre-fix extraction"), `paths` as in the spec section 7 with `calibrated_csv` = `GuineaRuns/Calibrated/GIN_calibrated_20261018_100416.csv`, `calibration` (U3R1-era values replaced by the D-run values: `pop_start_year 17521167, end_year_pop 27697655, urban_ratio_start_year 0.387, urban_ratio_end_year 0.45, elec_ratio_start_year 0.538, urban_elec_ratio 0.91, rural_elec_ratio 0.23, min_night_lights 0, min_pop 50, max_service_transformer_distance 2, max_mv_line_distance 2, max_hv_line_distance 5`), `defaults`, and the fourteen scenarios in the spec's table order with labels naming the grid-cost role; `legacy_name` only where the spec's table gives a non-superseded one (none in this file).

- [ ] **Step 4: Write `Scenarios/regression_u3r1.json`**: `paths.calibrated_csv` = `GuineaRuns/Inputs/GIN_calibrated.csv`, `paths.raw_input_csv` = the 18 October file, `output_root` = `GuineaRuns/Outputs/_regression`, calibration from `Scenario_U3R1_0.047_Variables.csv` (urban ratios 0.45 / 0.453), defaults as the study file, one scenario `REF_U3R1_g0.047` with overrides tiers 3 and 1, cost 0.047, `legacy_name "Scenario_U3R1_0.047"`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `conda run -n gep_guinea python -m pytest tests/test_scenario_files.py -v`
Expected: all passed.

- [ ] **Step 6: Commit**

```bash
git add Scenarios/guinea_scenarios.json Scenarios/regression_u3r1.json tests/test_scenario_files.py
git commit -m "feat: Guinea scenario control file (14 scenarios) and U3R1 regression file"
```

---

### Task 4: Technologies, variables table and summary table

**Files:**
- Create: `gep_onsset/scenario_runner.py`
- Test: `tests/test_scenario_runner_tables.py`

**Interfaces:**
- Consumes: `Control`, `Scenario` (Task 2).
- Produces in `scenario_runner.py`:
  - `TECH_CONSTANTS: dict` holding every literal of notebook cell 32 that is not a control-file key (for example `grid.om_of_td_lines 0.02`, `grid.connection_cost_per_hh 125`, `grid.tech_life 30`, `mg_pv_hybrid.capacity_factor 0.5`, `sa_pv.capital_cost_bins [0.020, 0.050, 0.100, 1, 5]`, diesel truck figures).
  - `build_technologies(params: dict) -> dict[str, Technology]` with keys `grid, mg_pv_hybrid, mg_wind_hybrid, mg_hydro, mg_wind, mg_pv, sa_pv, mg_diesel, sa_diesel` plus `sa_diesel_cost` and `mg_diesel_cost` dicts under keys `sa_diesel_cost`, `mg_diesel_cost`; also calls `Technology.set_default_values(...)` exactly as cell 53 does.
  - `summary_table(df: pd.DataFrame, yearsofanalysis: list[int], cost_choice: int) -> pd.DataFrame`: cell 55 verbatim; index `Grid_dens, Grid_ext, SA_PV, MG_PV_Battery, MG_Hydro, Non-electrified, Total`.
  - `variables_table(control: Control, scenario: Scenario, params: dict, technologies: dict, extra: dict) -> pd.DataFrame`: cell 62's list verbatim (columns `Variable, Value, Source, Comments, Description`), then rows for the hidden levers: `tech_switches, diesel_techs, productive_preference, tier_1..tier_5, cost_choice, hydro_viability_km (10, hard-coded in onsset.py), hydro_site_filter (1 MW, applied upstream), control_file_sha256, calibrated_csv_sha256, scenario_id, legacy_name`.

- [ ] **Step 1: Write the failing tests**

```python
def test_build_technologies_keys_and_values(gep_path):
    from scenario_control import load_control
    from scenario_runner import build_technologies
    p = load_control("Scenarios/guinea_scenarios.json", check_paths=False).resolved("BU_g0.1")
    t = build_technologies(p)
    assert set(t) >= {"grid","mg_pv_hybrid","mg_wind_hybrid","mg_hydro","mg_wind","mg_pv","sa_pv","mg_diesel","sa_diesel","sa_diesel_cost","mg_diesel_cost"}
    assert t["grid"].grid_price == 0.1 and t["grid"].distribution_losses == 0.167
    assert t["sa_pv"].capital_cost[0.020] == 9620 * p["pv_adjustment_factor"]

def test_summary_table_shape_on_sample(gep_path, sample_calibrated):
    # a frame with FinalElecCode2030/2040, Pop2030/2040, NewConnections*, NewCapacity*, InvestmentCost* columns
    # built by hand with 3 rows (codes 1, 3, 99) must give the 7-row, 8-column table with Total = sum
    ...
    assert list(tbl.index) == ["Grid_dens","Grid_ext","SA_PV","MG_PV_Battery","MG_Hydro","Non-electrified","Total"]
    assert list(tbl.columns)[:4] == ["Population2030","NewConnections2030","Capacity2030 (MW)","Investment2030 (million USD)"]

def test_variables_table_has_notebook_rows_then_hidden_levers(gep_path):
    ...
    assert df.columns.tolist() == ["Variable","Value","Source","Comments","Description"]
    assert df.Variable.iloc[0] == "Start_year" and "GIS data: Wind velocity" in df.Variable.values
    assert {"tech_switches","productive_preference","control_file_sha256","hydro_viability_km"} <= set(df.Variable)
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: FAIL, `ModuleNotFoundError: scenario_runner`.

- [ ] **Step 3: Implement the three functions and `TECH_CONSTANTS`** in `gep_onsset/scenario_runner.py`. Cell 32 and cell 55 bodies are copied; replace each bare notebook name with `params["name"]` or a `TECH_CONSTANTS` entry.

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n gep_guinea python -m pytest tests/test_scenario_runner_tables.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add gep_onsset/scenario_runner.py tests/test_scenario_runner_tables.py
git commit -m "feat: technologies, summary and variables tables lifted from the notebook"
```

---

### Task 5: Calibration step

**Files:**
- Modify: `gep_onsset/scenario_runner.py`
- Test: `tests/test_scenario_runner_calibrate.py`

**Interfaces:**
- Produces: `calibrate(control: Control, out_path: Path | None = None) -> Path`. Reproduces cells 34, 36, 37, 39, 40 on `paths.raw_input_csv` with the `calibration` block, writes `out_path` (default `control.paths["calibrated_csv"]`, parent created) and a sibling `<stem>_parameters.json` with the same keys the notebook writes in cell 40 plus `raw_input_sha256`. Returns the CSV path. Also `calibration_params_json(path) -> dict`.

- [ ] **Step 1: Write the failing tests** (on `sample_raw`, with a control whose `raw_input_csv` points to the sample and `calibrated_csv` to `tmp_path`)

```python
def test_calibrate_writes_file_with_calibration_columns(gep_path, sample_raw, tmp_path):
    out = calibrate(control, tmp_path / "cal.csv")
    df = pd.read_csv(out)
    for c in ["PopStartYear","ElecPopCalib","Pop2030","Pop2040","Pop2025","GridPenalty","WindCF","ElecStart","FinalElecCode2025"]:
        assert c in df.columns
    assert (df["Pop"] > 0).all()
    info = json.loads((tmp_path / "cal_parameters.json").read_text())
    assert info["pop_start_year"] == 17521167 and len(info["raw_input_sha256"]) == 64

def test_calibrate_population_sums_to_pop_start_year(gep_path, sample_raw, tmp_path):
    df = pd.read_csv(calibrate(control, tmp_path / "cal.csv"))
    assert abs(df["PopStartYear"].sum() - control.calibration["pop_start_year"]) < 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: FAIL, `ImportError: cannot import name 'calibrate'`.

- [ ] **Step 3: Implement `calibrate`**. Cell 40's note on the swapped return order of `elec_current_and_future` is preserved as is.

- [ ] **Step 4: Run tests to verify they pass**

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add gep_onsset/scenario_runner.py tests/test_scenario_runner_calibrate.py
git commit -m "feat: calibration step from the control file"
```

---

### Task 6: Single scenario run with manifest

**Files:**
- Modify: `gep_onsset/scenario_runner.py`
- Test: `tests/test_scenario_runner_run.py`

**Interfaces:**
- Consumes: `build_technologies`, `summary_table`, `variables_table` (Task 4).
- Produces:
  - `REQUIRED_INPUT_COLUMNS: tuple[str, ...]` = the columns cells 44 to 53 read: `id, Pop, PopStartYear, Pop2030, Pop2040, Pop2025, IsUrban, GHI, WindVel, Hydropower, HydropowerDist, HydropowerFID, TravelHours, ElecPopCalib, ElecStart, GridPenalty, WindCF, CurrentMVLineDist, CurrentHVLineDist, PlannedMVLineDist, PlannedHVLineDist, SubstationDist, TransformerDist, RoadDist, NightLights, ResidentialDemandTierCustom, hc_count_com_hc, hc_count_primary_hc, hc_count_referral_hc, edu_count_col_edu, edu_count_lyc_edu, edu_count_uni_edu, FinalElecCode2025`. Note: the extraction writes `edu_count_sch_edu` and no `edu_count_lyc_edu`; the module tolerates absence of the three `edu_count_*` names exactly as the notebook does (warning only), so they are excluded from the required tuple; everything else is required.
  - `run_scenario(control: Control, scenario_id: str, batch_dir: Path, force: bool = False, log=print) -> dict` returning the manifest dict. Behaviour: if `batch_dir/<id>/manifest.json` exists with `"status": "complete"` and not `force`, return it with `"skipped": True`. Otherwise load `paths.calibrated_csv` through `SettlementProcessor`, check `REQUIRED_INPUT_COLUMNS` (raise `ControlError` naming the missing ones), run cells 44, 47, 48 (`matrix_path = paths.productive_matrix`, `preference = params["productive_preference"]`), 50, 52, 53 (with `pv_path`, `wind_path` from `paths`), 55, 62, 64 into `batch_dir/<id>/`. Manifest keys: `scenario_id, label, demand_case, legacy_name, status, started, finished, seconds, parameters (JSON-safe), calibration, control_file, control_file_sha256, calibrated_csv, calibrated_csv_sha256, rows_in, rows_out, git_commit, git_dirty, python, pandas, numpy, outputs {results, summaries, variables: {path, bytes}}, technology_constants`.
  - `summary_from_manifest(batch_dir, scenario_id) -> pd.DataFrame` reading the Summaries CSV back.

- [ ] **Step 1: Write the failing tests** (control built in a fixture: study defaults, one scenario `BU_g0.1`, `calibrated_csv` = `sample_calibrated`, `output_root` = `tmp_path`)

```python
def test_run_scenario_writes_three_csvs_and_manifest(gep_path, small_control, tmp_path):
    m = run_scenario(small_control, "BU_g0.1", tmp_path / "b1")
    d = tmp_path / "b1" / "BU_g0.1"
    assert (d / "BU_g0.1_Results.csv").exists() and (d / "BU_g0.1_Summaries.csv").exists() and (d / "BU_g0.1_Variables.csv").exists()
    assert m["status"] == "complete" and m["rows_out"] == 500 and len(m["calibrated_csv_sha256"]) == 64
    res = pd.read_csv(d / "BU_g0.1_Results.csv")
    assert res.columns[0] == "index" and "FinalElecCode2040" in res.columns
    s = pd.read_csv(d / "BU_g0.1_Summaries.csv", index_col=0)
    assert list(s.index) == ["Grid_dens","Grid_ext","SA_PV","MG_PV_Battery","MG_Hydro","Non-electrified","Total"]
    assert s.loc["Total","Population2040"] == pytest.approx(res["Pop2040"].sum(), rel=1e-6)

def test_run_scenario_skips_when_complete_and_reruns_on_force(gep_path, small_control, tmp_path):
    run_scenario(small_control, "BU_g0.1", tmp_path / "b1")
    assert run_scenario(small_control, "BU_g0.1", tmp_path / "b1")["skipped"] is True
    assert run_scenario(small_control, "BU_g0.1", tmp_path / "b1", force=True).get("skipped", False) is False

def test_run_scenario_fails_fast_on_missing_column(gep_path, small_control, tmp_path, sample_calibrated):
    df = pd.read_csv(sample_calibrated).drop(columns=["hc_count_com_hc"]); bad = tmp_path / "bad.csv"; df.to_csv(bad, index=False)
    small_control.paths["calibrated_csv"] = bad
    with pytest.raises(ControlError, match="hc_count_com_hc"):
        run_scenario(small_control, "BU_g0.1", tmp_path / "b2")
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: FAIL, `ImportError: cannot import name 'run_scenario'`.

- [ ] **Step 3: Implement `run_scenario`, `REQUIRED_INPUT_COLUMNS`, `summary_from_manifest`**. Git commit and dirty flag via `subprocess.run(["git","rev-parse","HEAD"])` and `git status --porcelain`, both tolerant of failure (value `None`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n gep_guinea python -m pytest tests/test_scenario_runner_run.py -v`
Expected: 3 passed in under 90 seconds.

- [ ] **Step 5: Commit**

```bash
git add gep_onsset/scenario_runner.py tests/test_scenario_runner_run.py
git commit -m "feat: run one scenario from the control file with manifest"
```

---

### Task 7: Batch loop, comparison table and command line

**Files:**
- Modify: `gep_onsset/scenario_runner.py`
- Create: `run_scenarios.py`
- Test: `tests/test_scenario_batch.py`

**Interfaces:**
- Consumes: `run_scenario`, `calibrate`.
- Produces:
  - `run_batch(control: Control, ids: list[str] | None, batch_name: str | None, force: bool = False, calibrate_first: bool = False, log=print) -> Path` returning the batch directory `paths.output_root / batch_name` (default `batch_name` = `datetime.date.today().isoformat()`). Unknown ids raise `ControlError` listing `control.ids()` before any run. If `paths.calibrated_csv` is missing or `calibrate_first`, calls `calibrate`. Writes `comparison_summary.csv` (long format, columns `scenario_id, label, demand_case, grid_generation_cost, urban_target_tier, rural_target_tier, technology, year, population, new_connections, capacity_mw, investment_musd`, one row per scenario x technology x year, scenarios in control-file order) and appends to `batch_log.txt` one line per scenario: timestamp, id, status, seconds.
  - `run_scenarios.py`: argparse with positional `control`, options `--only ID[,ID]`, `--batch NAME`, `--force`, `--calibrate`, `--dry-run` (prints the resolved parameters of every selected scenario as JSON and exits 0). Puts `gep_onsset/` on `sys.path` relative to its own location. Exit code 1 on `ControlError` with the message on stderr.

- [ ] **Step 1: Write the failing tests** (control with two scenarios `BU_g0.1` and `TD_Low_g0.1` on `sample_calibrated`)

```python
def test_run_batch_two_scenarios_comparison_and_log(gep_path, two_control, tmp_path):
    b = run_batch(two_control, None, "t1")
    comp = pd.read_csv(b / "comparison_summary.csv")
    assert set(comp.scenario_id) == {"BU_g0.1","TD_Low_g0.1"} and len(comp) == 2 * 7 * 2
    assert comp.scenario_id.iloc[0] == "BU_g0.1"
    assert (b / "batch_log.txt").read_text().count("complete") == 2

def test_run_batch_unknown_id_fails_before_running(gep_path, two_control, tmp_path):
    with pytest.raises(ControlError, match="BU_g0.1"):
        run_batch(two_control, ["nope"], "t2")
    assert not (two_control.paths["output_root"] / "t2").exists()

def test_run_batch_reruns_interrupted_scenario(gep_path, two_control, tmp_path):
    b = run_batch(two_control, ["BU_g0.1"], "t3")
    (b / "BU_g0.1" / "manifest.json").unlink()
    before = (b / "BU_g0.1" / "BU_g0.1_Summaries.csv").stat().st_mtime
    run_batch(two_control, ["BU_g0.1"], "t3")
    assert (b / "BU_g0.1" / "BU_g0.1_Summaries.csv").stat().st_mtime > before

def test_cli_dry_run_and_bad_id(gep_path, two_control_path):
    out = subprocess.run([sys.executable, "run_scenarios.py", str(two_control_path), "--dry-run"], capture_output=True, text=True)
    assert out.returncode == 0 and "BU_g0.1" in out.stdout and "grid_generation_cost" in out.stdout
    bad = subprocess.run([sys.executable, "run_scenarios.py", str(two_control_path), "--only", "nope", "--dry-run"], capture_output=True, text=True)
    assert bad.returncode == 1 and "TD_Low_g0.1" in bad.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: FAIL, `ImportError: cannot import name 'run_batch'`.

- [ ] **Step 3: Implement `run_batch` and `run_scenarios.py`**.

- [ ] **Step 4: Run the whole fast suite**

Run: `conda run -n gep_guinea python -m pytest -v`
Expected: all passed; total under four minutes.

- [ ] **Step 5: Commit**

```bash
git add gep_onsset/scenario_runner.py run_scenarios.py tests/test_scenario_batch.py
git commit -m "feat: batch runner, comparison table and command line"
```

---

### Task 8: Regression gate against the shared Scenario_U3R1_0.047

**Files:**
- Test: `tests/test_regression_u3r1.py`

**Interfaces:**
- Consumes: `run_batch`, `Scenarios/regression_u3r1.json`, `GuineaRuns/Outputs/Scenario_U3R1_0.047/*`.

- [ ] **Step 1: Write the test** (marked `slow`, skipped when the shared outputs are absent)

```python
@pytest.mark.slow
def test_runner_reproduces_shared_u3r1(gep_path):
    c = load_control("Scenarios/regression_u3r1.json")
    b = run_batch(c, ["REF_U3R1_g0.047"], "gate", force=True)
    got = pd.read_csv(b / "REF_U3R1_g0.047" / "REF_U3R1_g0.047_Summaries.csv", index_col=0)
    exp = pd.read_csv("GuineaRuns/Outputs/Scenario_U3R1_0.047/Scenario_U3R1_0.047_Summaries.csv", index_col=0)
    pd.testing.assert_frame_equal(got, exp.reindex(index=got.index, columns=got.columns), check_exact=False, atol=0.005)
    gr = pd.read_csv(b / "REF_U3R1_g0.047" / "REF_U3R1_g0.047_Results.csv").set_index("id")
    er = pd.read_csv("GuineaRuns/Outputs/Scenario_U3R1_0.047/Scenario_U3R1_0.047_Results.csv").set_index("id")
    assert len(gr) == len(er) == 82954
    for y in (2030, 2040):
        assert (gr[f"FinalElecCode{y}"] == er.loc[gr.index, f"FinalElecCode{y}"]).all()
    assert np.allclose(gr["InvestmentCost2040"], er.loc[gr.index, "InvestmentCost2040"], rtol=1e-9, atol=1e-6)
```

- [ ] **Step 2: Run it**

Run: `conda run -n gep_guinea python -m pytest tests/test_regression_u3r1.py -m slow -v`
Expected: 1 passed in about two minutes. If it fails, the runner diverged from the notebook; diff the Results columns against the shared file (the spike's `compare_runs.py` in the scratchpad `repro` folder does this) and fix the runner, never the model.

- [ ] **Step 3: Commit**

```bash
git add tests/test_regression_u3r1.py
git commit -m "test: regression gate reproducing the shared Scenario_U3R1_0.047 run"
```

---

### Task 9: Notebook integration

**Files:**
- Modify: `GEP_Generator.ipynb` (cell 2 sys.path; cells 43 to 64 replaced)
- Create: `tools/patch_notebook.py` (the nbformat script that performs the edit, kept so the change is reproducible)
- Test: `tests/test_notebook_integration.py`

**Interfaces:**
- Consumes: `run_scenario`, `load_control`.

- [ ] **Step 1: Write the failing test**

```python
def test_notebook_calls_runner_and_has_no_scenario_loop():
    nb = json.loads(Path("GEP_Generator.ipynb").read_text(encoding="utf-8"))
    src = "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")
    assert "Bachirou" not in src
    assert "for year in yearsofanalysis" not in src
    assert "run_scenario(" in src and "load_control(" in src
    assert "filedialog.askdirectory" not in src
    new = [c for c in nb["cells"] if c["cell_type"] == "code" and "run_scenario(" in "".join(c["source"])][0]
    compile("".join(new["source"]), "cell", "exec")
```

- [ ] **Step 2: Run it to verify it fails**

Expected: FAIL on the `Bachirou` assertion.

- [ ] **Step 3: Write `tools/patch_notebook.py`** using `nbformat`: replace in cell 2 the `sys.path.append(r'C:\Users\Bachirou\...')` line with `sys.path.append(os.path.join(os.getcwd(), 'gep_onsset'))` preceded by `import os`; delete cells 43 to 64 inclusive; append one markdown cell "7. Run a scenario from the control file" explaining that the levers in sections 2 to 4 above apply to calibration only and that scenario levers come from `Scenarios/guinea_scenarios.json`; one code cell:

```python
from scenario_control import load_control
from scenario_runner import run_scenario, summary_from_manifest
control = load_control('Scenarios/guinea_scenarios.json')
print('Scenarios:', control.ids())
scenario_id = 'BU_g0.1'          # change to any id listed above
batch_dir = control.paths['output_root'] / 'notebook'
manifest = run_scenario(control, scenario_id, batch_dir, force=True)
summary_from_manifest(batch_dir, scenario_id)
```

and one code cell that re-creates the bar chart of former cell 58 from the returned summary table (lift the cell's body, with `summary_table` bound to the returned frame and `yearsofanalysis` to `[control.defaults['intermediate_year'], control.defaults['end_year']]`). Strip all outputs from the notebook. Run the script.

- [ ] **Step 4: Run the test**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add GEP_Generator.ipynb tools/patch_notebook.py tests/test_notebook_integration.py
git commit -m "feat: notebook scenario section calls the runner from the control file"
```

---

### Task 10: Full matrix batch and README

**Files:**
- Modify: `README.md` (section "Running the scenario matrix")

- [ ] **Step 1: Calibrate once and run the fourteen scenarios**

Run: `conda run -n gep_guinea python run_scenarios.py Scenarios/guinea_scenarios.json --calibrate --batch 2026-10-24_table1`
Expected: `batch_log.txt` shows fourteen `complete` lines; `comparison_summary.csv` has 14 x 7 x 2 = 196 rows; wall clock about 25 minutes.

- [ ] **Step 2: Sanity-check the batch**

Run a one-off Python check: for every scenario, `Total` `Population2040` equals 27,697,654 within 2 persons and `Non-electrified` `Population2040` is 0; the five `_g0.1` scenarios differ from each other only through the tiers; `BU_g0.078` total investment 2040 lies within 5 percent of the spike's reproduction of `D2_BOT_0.078_1_10km_H_GL127` in `GuineaRuns/Repro` (1,806 million USD). Record the numbers in the batch folder as `CHECKS.md`.

- [ ] **Step 3: Write the README section**: how to create the environment, how to run all, a subset, dry-run, recalibrate; where outputs land; that the regression gate is `pytest -m slow`; that the five D-runs are superseded.

- [ ] **Step 4: Run the full test suite, fast and slow**

Run: `conda run -n gep_guinea python -m pytest -m "slow or not slow" -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: running the Guinea scenario matrix from the control file"
```
