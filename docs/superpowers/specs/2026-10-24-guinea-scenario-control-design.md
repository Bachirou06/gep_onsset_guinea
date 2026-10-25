# Guinea scenario control file and runner: design

Date: 2026-10-24
Status: approved 2026-10-24 (builder check done, three decisions taken by the owner)
Owner: Thierry Odou (IRENA), working on Bachirou's `gep_onsset_guinea` repository

## 1. Intent

The Guinea DRE study has so far produced six GEP-OnSSET runs by hand-editing
`GEP_Generator.ipynb` once per run and exporting three CSVs each time. The
parameters that distinguish a run are only partly written down (the
`_Variables.csv` export omits technology switches, the hydro distance rule,
the productive-demand preference, the calibration thresholds and the input
file used), the run names encode levers in an ad-hoc grammar, and the five
"D2/D3" runs were produced on a calibrated file that is not in the shared
folder, so they cannot be reproduced today.

The study now needs a full scenario matrix (Table 1 of the study document:
three demand cases times a grid-generation-cost sensitivity), and will need
to re-run it whenever an input, a cost or a bug fix changes. Editing a
notebook fourteen times per iteration is not sustainable, and nothing about it
is auditable.

This design introduces one **scenario control file** that declares every
scenario and every lever explicitly, and one **runner** that executes any
subset of those scenarios from the command line or from the notebook, using
exactly the model logic the notebook uses today. It follows the pattern of
the Senegal project (`Model/Cases/scenarios.json` driving
`runner_reto.scenarionew()`), adapted to the upstream GEP-OnSSET codebase.

## 2. Goals

1. One control file, `Scenarios/guinea_scenarios.json`, lists all scenarios
   of the study with every lever explicit, including the levers the notebook
   never exported.
2. One command runs one, several or all scenarios and writes, per scenario,
   the same three CSVs the colleague's workflow produces (`_Results.csv`,
   `_Summaries.csv`, `_Variables.csv`) so that downstream maps and tables
   keep working unchanged.
3. Every run leaves a machine-readable manifest: full resolved parameters,
   SHA-256 of the calibrated input, git commit of the code, timestamps,
   package versions.
4. A batch of runs produces one comparison table across scenarios
   (population, new connections, capacity and investment by technology and
   year), ready for the report.
5. The notebook stays the interactive front end for calibration and
   exploration, but its scenario section calls the runner rather than
   duplicating it. One code path.
6. Acceptance is numeric: running the runner with the parameters of the
   existing `Scenario_U3R1_0.047` run on the `GIN_calibrated.csv` in the
   shared folder must reproduce that run's `_Summaries.csv`.

## 3. Non-goals

- No change to the model numerics in `gep_onsset/onsset.py`,
  `hybrids_pv.py`, `hybrids_wind.py` or
  `guinea_demand_customization.py`. The runner calls them as the notebook
  does.
- No parallel execution in v1. Scenarios run sequentially; the loop must be
  resumable (skip a scenario whose outputs and manifest already exist unless
  `--force`).
- No maps, charts or Word tables. Those are a later step that reads the
  comparison table.
- No replacement of the GIS extraction notebooks.
- No Excel interface. The control file is JSON, edited in a text editor.

## 4. Anti-goals

- A control file that only covers "the six levers" and still leaves hidden
  state in notebook cells. If a parameter can change a number in the
  outputs, it is in the control file or in the manifest.
- A runner whose outputs differ from a notebook run with the same inputs.
  Any divergence is a bug in the runner, not a feature.
- A second copy of the scenario loop living on in the notebook.

## 5. Constraints

- **Repository.** Work lands in `C:\PrivateToolsDevelopment\Projects\GuineaWork`,
  a clone of `github.com/Bachirou06/gep_onsset_guinea`, branch `main`.
  Commit locally on a feature branch; do not push (the remote is the
  colleague's; sharing is a separate decision).
- **Inputs and outputs live outside git.** Everything under `GuineaRuns/`
  is excluded via `.git/info/exclude`. The repository `.gitignore` also
  ignores `*Results.csv`, `*Summaries.csv`, `*Variables.csv`, `Calibrated/`
  and `GIN Data/`. The control file and the runner are tracked; data never
  is.
- **Reference behaviour is the notebook**, `GEP_Generator.ipynb` at commit
  `fff30bd`, cells 36 to 64 (demand placeholders, conditioning,
  calibration, population threshold, MTF tier columns, customised demand,
  scenario loop, summary table, export). The code in those cells is lifted
  into the runner as-is, with notebook globals turned into function
  parameters. The hidden rule found during exploration stays as it is in
  `onsset.py` (hydro viable within 10 km, hard-coded) and is documented in
  the control file's `meta` block rather than re-implemented.
- **Python environment.** The notebook was last executed with Python 3.12.
  `gep_onsset_env.yml` pins Python 3.8 and pandas 1.0 and is not usable.
  The user's `base` Anaconda has pandas 3.0.3 and no geopandas. The builder
  creates a dedicated conda environment (`gep_guinea`) with Python 3.12 and
  pins that `onsset.py` actually runs on, starting from the colleague's own
  `OnSSET_GIS_Extraction_notebook-master/onsset_env.yml` (Python 3.12.13, the
  environment the notebook outputs reference); `geopandas` is not required by
  the runner. The environment file is tracked.
- **Data available now.** `GuineaRuns/Inputs/GIN_calibrated.csv` (82,954
  rows, the calibration behind `Scenario_U3R1_0.047`),
  `GuineaRuns/Inputs/OnSSET_InputFile_20261018_100416.csv` (83,010 rows,
  the raw extraction behind the five D-runs, with the per-settlement custom
  residential demand column populated), PV and wind hourly profiles under
  `GuineaRuns/Inputs/Guinea Data/Solar profile/gn-2-pv.csv` and
  `.../Wind profile/gn-2-wind.csv`, and the six existing run outputs under
  `GuineaRuns/Outputs/<run>/`.
- **Style.** Plain Python, standard library plus pandas/numpy. No new
  heavyweight dependency for orchestration (no papermill). British
  spelling in user-facing text. No em-dashes in output files.

## 6. The scenario matrix (decided)

Five demand cases: the three of Table 1 of the study plus two
demand-sensitivity variants that shift the top-down tiers by one step.
Fourteen scenarios in all.

| Demand case | Urban tier | Rural tier | Meaning | Grid cost levels run |
|---|---|---|---|---|
| `TD_Low` | 3 | 2 | Top-down low, MTF tiers (Table 1) | all four |
| `TD_Low_minus` | 3 | 1 | Lower demand variant; same tiers as the earlier U3R1 run | reference only |
| `TD_High` | 4 | 3 | Top-down high, MTF tiers (Table 1) | all four |
| `TD_High_plus` | 5 | 3 | Higher demand variant | reference only |
| `BU` | 6 | 6 | Bottom-up, per-settlement custom demand from GDP-PPP and poverty (Table 1) | all four |

Run order inside the control file, which is also the default batch order:
first the five demand cases at the reference cost 0.1, then the three
Table 1 cases at the other cost levels in ascending order (0.047, 0.078,
0.22). The reference block therefore comes out first in any partial run.

Grid generation cost levels, USD/kWh, with their role in the study:

| Level | Role | Note |
|---|---|---|
| `0.1` | Reference | the `defaults` value; the reference scenario of each demand case overrides nothing on cost |
| `0.078` | Low variant | sensitivity |
| `0.22` | High variant | sensitivity |
| `0.047` | Legacy | continuity with the six earlier runs; not part of Table 1 |

Scenario identifiers: `<demand_case>_g<cost>`, e.g. `TD_Low_g0.078`,
`BU_g0.22`. Identifiers are also the output file prefixes. Each scenario's
`label` states the role in words ("grid cost reference 0.1 USD/kWh",
"grid cost low variant 0.078 USD/kWh", and so on) so the comparison table
reads without a key.

The full list, in control-file order:

| # | Scenario id | Demand case | Urban tier | Rural tier | Grid cost | Role | Legacy run with the same levers |
|---|---|---|---|---|---|---|---|
| 1 | `TD_Low_g0.1` | TD_Low | 3 | 2 | 0.1 | reference | none |
| 2 | `TD_Low_minus_g0.1` | TD_Low_minus | 3 | 1 | 0.1 | reference | none (U3R1 tiers, other cost) |
| 3 | `TD_High_g0.1` | TD_High | 4 | 3 | 0.1 | reference | none |
| 4 | `TD_High_plus_g0.1` | TD_High_plus | 5 | 3 | 0.1 | reference | none |
| 5 | `BU_g0.1` | BU | 6 | 6 | 0.1 | reference | none |
| 6 | `TD_Low_g0.047` | TD_Low | 3 | 2 | 0.047 | legacy | none (U3R1 was rural tier 1) |
| 7 | `TD_High_g0.047` | TD_High | 4 | 3 | 0.047 | legacy | `D3_U4R3_0.047_1_10km_H_GL127` (superseded) |
| 8 | `BU_g0.047` | BU | 6 | 6 | 0.047 | legacy | `D2_BOT_0.047_1_10km_H_GL127` (superseded) |
| 9 | `TD_Low_g0.078` | TD_Low | 3 | 2 | 0.078 | low variant | none |
| 10 | `TD_High_g0.078` | TD_High | 4 | 3 | 0.078 | low variant | `D3_U4R3_0.078_1_10km_H_GL127` (superseded) |
| 11 | `BU_g0.078` | BU | 6 | 6 | 0.078 | low variant | `D2_BOT_0.078_1_10km_H_GL127` (superseded) |
| 12 | `TD_Low_g0.22` | TD_Low | 3 | 2 | 0.22 | high variant | none |
| 13 | `TD_High_g0.22` | TD_High | 4 | 3 | 0.22 | high variant | none |
| 14 | `BU_g0.22` | BU | 6 | 6 | 0.22 | high variant | none |

The legacy column is informative only: the four matching D-runs were
produced on a calibrated file that is not available, so they are a
plausibility check, not a regression gate (see section 9).

Shared assumptions (the `defaults` block), all from the existing runs and
Table 1 unless marked:

| Lever | Value |
|---|---|
| Start, intermediate, end year | 2025, 2030, 2040 |
| Electrification targets | 0.70 in 2030, 1.00 in 2040 |
| Population 2040 | 27,697,655 |
| Urban ratio start / end | 0.387 / 0.45 (my call, see section 10); calibration-stage, lives in the `calibration` block |
| People per household urban / rural | 6.6 / 6.3 |
| Electrification rate start, urban, rural | 0.538, 0.91, 0.23 |
| Discount rate | 0.08 |
| Grid connections cap to 2030 | 127 thousand households per year; unlimited after |
| Grid generation capacity cap to 2030 | 90 MW per year; unlimited after |
| Prioritisation | 5 (nationwide least cost), auto-intensification 0 km |
| Technology switches | `sa_pv` on, `mg_hydro` on, `mg_pv` off, `mg_pv_hybrid` on, `mg_wind_hybrid` off; `diesel_techs` 0 |
| Hydro site cap | none as a lever. The 1 MW rule of Table 1 is already applied upstream (the hydro potential column holds 0 to 1,000 kW only); documented in `meta.notes` beside the 10 km rule. Decided 2026-10-24 |
| PV cost adjustment factor | 1 |
| Productive demand | on, matrix `gep_onsset/productive_uses_matrix.json`, preference `Low` |
| Population threshold | 0 (as recorded in the six runs' Variables files) |
| MTF tier kWh per household per year | 38.7, 219, 803, 2117, 2993 |
| Grid losses | 0.167 (value in the six runs; the notebook cell currently says 0.18) |
| All capital, line and transformer costs | as in the six runs' Variables files |
| Calibration thresholds | min night lights 0, min pop 50, transformer 2 km, MV 2 km, HV 5 km; calibration-stage, `calibration` block |

Population 2040, people per household, start-year urban and electrification ratios and the
calibration thresholds act only in the calibration step. They live in the `calibration` block,
not in `defaults`, and a scenario override of any of them is a validation error: one control
file has one calibration. A different calibration is a different control file (the regression
file already works this way). This was the reviewer's question 3, settled as my call.

A scenario entry may override any default. The fourteen entries override only
`urban_target_tier`, `rural_target_tier` and `grid_generation_cost`; the
five reference scenarios (`*_g0.1`) override the tiers only, since 0.1 is
the default.

## 7. Control file

Path: `Scenarios/guinea_scenarios.json` (tracked). Shape:

```json
{
  "meta": {
    "schema_version": "1.0",
    "study": "Guinea DRE study, GEP-OnSSET",
    "created": "2026-10-24",
    "notes": [
      "Hydro mini-grids are only viable within 10 km of a site (hard-coded in onsset.py).",
      "Results and inputs are never committed."
    ]
  },
  "paths": {
    "raw_input_csv":   "GuineaRuns/Inputs/OnSSET_InputFile_20261018_100416.csv",
    "calibrated_csv":  "GuineaRuns/Calibrated/GIN_calibrated_2026-10-24.csv",
    "pv_profile":      "GuineaRuns/Inputs/Guinea Data/Solar profile/gn-2-pv.csv",
    "wind_profile":    "GuineaRuns/Inputs/Guinea Data/Wind profile/gn-2-wind.csv",
    "productive_matrix": "gep_onsset/productive_uses_matrix.json",
    "output_root":     "GuineaRuns/Outputs"
  },
  "calibration": { "...the calibration levers..." },
  "defaults":    { "...every scenario lever, flat key/value..." },
  "scenarios": [
    { "id": "TD_Low_g0.047", "demand_case": "TD_Low", "label": "Top-down low demand, grid 0.047 USD/kWh",
      "overrides": { "urban_target_tier": 3, "rural_target_tier": 2, "grid_generation_cost": 0.047 } },
    "... eleven more ..."
  ]
}
```

Rules:
- Paths are relative to the repository root; the runner resolves them.
- Build on `OnSSET_InputFile_20261018_100416.csv`, the post-fix extraction (commit fff30bd
  corrected a row misalignment of raster attributes). Confirmed by the colleague on
  2026-10-24 as the file to use.
- Keys in `defaults` use the notebook's variable names (`grid_generation_cost`,
  `annual_new_grid_connections_limit_intermediate`, `tech_switches`, ...) so
  a reader can map the file to the notebook cell by cell.
- Per-year cost dictionaries keep the notebook's `{inf: value}` meaning,
  written in JSON as `{"inf": 2950}` and converted on load.
- The runner validates the file on load: unknown keys are an error, a
  scenario `id` must be unique and filename-safe, every referenced path
  must exist.

## 8. Runner

New module `gep_onsset/scenario_runner.py` and a thin command
`run_scenarios.py` at the repository root.

Functions (names are suggestions, the builder may rename):

- `load_control(path) -> Control` reads, validates and resolves the control
  file; `Control.resolved(scenario_id)` returns the flat parameter dict
  (defaults plus overrides).
- `calibrate(control) -> Path` reproduces notebook cells 34 to 40 from
  `paths.raw_input_csv` and writes `paths.calibrated_csv` plus a sibling
  `_parameters.json` (same content the notebook writes today). Runs only on
  `--calibrate` or when the calibrated file is missing.
- `run_scenario(control, scenario_id, batch_dir, force=False) -> dict`
  reproduces cells 44 to 64: load calibrated CSV, population threshold, MTF
  tier columns, customised demand, hydro site cap, scenario loop, summary
  table, three CSV exports, manifest. Returns the summary table.
- `run_batch(control, ids, batch_name, force=False) -> Path` loops
  `run_scenario`, writes `comparison_summary.csv` and `batch_log.txt`.

Command line:

```
python run_scenarios.py Scenarios/guinea_scenarios.json              # all fourteen, control-file order
python run_scenarios.py Scenarios/guinea_scenarios.json --only BU_g0.078,BU_g0.22
python run_scenarios.py Scenarios/guinea_scenarios.json --calibrate   # recalibrate first
python run_scenarios.py Scenarios/guinea_scenarios.json --batch 2026-10-24_table1 --force
python run_scenarios.py Scenarios/guinea_scenarios.json --dry-run     # print resolved parameters, run nothing
```

Output layout, all under `paths.output_root`:

```
GuineaRuns/Outputs/<batch_name>/
  comparison_summary.csv          one row per scenario x technology x year
  batch_log.txt
  TD_Low_g0.047/
    TD_Low_g0.047_Results.csv     identical columns to the notebook export
    TD_Low_g0.047_Summaries.csv   identical shape to the notebook export
    TD_Low_g0.047_Variables.csv   the notebook's table, extended with the hidden levers
    manifest.json
```

`batch_name` defaults to today's date. A scenario folder with a complete
manifest is skipped unless `--force`.

Manifest content: scenario id and label, resolved parameters, control file
SHA-256, calibrated CSV SHA-256 and row count, git commit and dirty flag,
Python and pandas/numpy versions (no numba in gep_onsset), start and end time,
wall-clock seconds, output file sizes. The `index` column that `reset_index` adds in the
notebook is kept so Results columns stay identical to the shared runs.

Notebook integration: cells 44 to 64 of `GEP_Generator.ipynb` (population threshold through
export; cells 47 to 52 are scenario-stage levers too) are replaced
by one markdown cell and two code cells: choose a scenario id from the
control file, then call `run_scenario`. The calibration cells (34 to 44)
stay so the colleague keeps the interactive calibration map. The old cells
remain in git history. The notebook's hard-coded `sys.path.append` to the
colleague's home directory is replaced by a path relative to the notebook.

## 9. Verification

Alignment check of 2026-10-24 (`GuineaRuns/Repro/ALIGNMENT_REPORT.md`): a headless execution
of the notebook cells reproduced Scenario_U3R1_0.047 from the shared calibrated file bit for
bit (142 of 143 columns identical, the 143rd being the row-order `index`; summaries identical).
The five D-runs, re-run from the corrected 18 October input, differ by 6 to 12 percent on
total investment and on 18,000 to 29,000 technology choices, as expected from their pre-fix
input. Each run takes about 95 seconds in the OnSSET_SENEGAL environment (Python 3.10,
pandas 2.3.3), which is therefore a workable environment for the runner as well.

1. **Regression against the shared run.** A scenario `_ref_U3R1_0.047`
   (kept in a separate `Scenarios/regression_u3r1.json`, not in the study
   matrix) runs the runner on `GuineaRuns/Inputs/GIN_calibrated.csv` with
   the parameters recorded in `Scenario_U3R1_0.047_Variables.csv` (urban
   tier 3, rural tier 1, grid cost 0.047, urban ratios 0.45 / 0.453,
   connection cap 127, no hydro site cap). Its `_Summaries.csv` must equal
   the shared one to the rounding of that file. This is the gate for
   "the runner is the notebook".
2. **Fast tests** under `tests/` (the repository `.gitignore` ignores `test/`) on a 2,000-settlement sample extracted from
   the calibrated file: control-file validation (unknown key, duplicate id,
   missing path), resolution of overrides, manifest completeness, resume
   and `--force` behaviour, comparison table shape. They must run in under
   a minute.
3. **Full matrix smoke.** One full batch of fourteen on the real data, timing
   recorded in the batch log, before the branch is considered done.

## 10. Calls I made, open to veto

- Rural tier for `TD_Low` is 2 (Table 1), not 1 (the earlier U3R1 run).
- Urban ratio 2040 stays 0.45 as in the five D-runs. Table 1 says 63.3 %
  urban, which contradicts the RGPH-4 figure of 38.7 % urban today and
  looks inverted; to be confirmed with the colleague, one number to change
  in `defaults` when it is.
- The "mini-hydro above 1 MW excluded" rule is not a runner lever: the data is
  already filtered upstream (decided 2026-10-24, reviewer question 1, option a).
  `meta.notes` records it; no `hydro_site_max_kw` key exists.
- The fourteen scenarios are listed explicitly in the control file rather
  than generated from a matrix block, so the file is the reviewable
  record.
- Scenario ids use the readable `TD_Low_g0.078` form rather than the
  colleague's `D2_BOT_0.078_1_10km_H_GL127` grammar. The manifest records a
  legacy name only for the U3R1 run; the five D-runs are recorded as superseded
  in `meta.notes` (pre-fix extraction, decided 2026-10-24, reviewer question 2,
  option a).
- The notebook's scenario cells are replaced, not duplicated.
- Calibration-stage keys cannot be overridden per scenario (section 6).
- The `index` column from `reset_index` is kept in Results for column parity.

## 11. Left to the builder

- Exact module and function names, argument parsing library (argparse is
  fine), logging format.
- How the hidden levers are appended to `_Variables.csv` (extra rows at the
  end, same five columns).
- Pinned package versions in the new environment file, found by running the
  regression test.
- Whether to read the calibrated CSV once per batch and copy the frame per
  scenario, or re-read per scenario. Correctness first; memory on an
  83,000-row frame with 144 columns is not a concern.
- Sample extraction method for the fast tests (deterministic, seeded).

## 12. Out of scope but noted for later

- Parallel scenario execution.
- IRENA-branded maps and charts from the comparison table.
- Reproducing the five D-runs bit for bit is dropped: they are superseded
  (section 13). The regression gate uses the U3R1 run.

## 13. Reviewer questions (builder check, 2026-10-24)

Two questions only the owner can answer; both change numbers.

1. **Hydro site cap.** The `Hydropower` column is in kW and takes only the values 0, 100, ...,
   1000; 100 sites, 11 of them at exactly 1000 kW, none above. The extraction already used a
   layer pre-filtered at 1 MW or below (none of the three layers in the shared Hydro_potential
   folder has 100 rows). A cap written as "above 1,000 kW" is therefore inert, and a cap at
   "1,000 kW or above" removes 11 sites and changes MG_Hydro in every scenario. Options:
   (a) treat the 1 MW rule as applied upstream, document it in `meta` beside the 10 km rule, no
   lever; (b) exclude sites at or above 1,000 kW; (c) name the real source layer and threshold.
   Decision 2026-10-24: (a).
2. **Status of the five D-runs.** They were computed on the pre-fix extraction
   (`..._071327.csv`, total population 11,247,027): ids, coordinates, hydro and facility counts
   match the corrected file, but population, night lights, solar and travel time match on only
   10 percent of rows (values shifted to neighbouring ids). U3R1 and the regression gate stand
   on the corrected file. Recommendation: record the D-runs as superseded in `meta.notes`, map
   legacy names only for U3R1, and drop section 12's "recover the missing calibrated file".
   Decision 2026-10-24: superseded, as recommended. The colleague confirmed on 2026-10-24
   that `OnSSET_InputFile_20261018_100416.csv` is the file to use (decision 3); the five
   runs are redone by the runner on that file.

