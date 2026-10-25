gep_onsset
=================================

[![Documentation Status](https://readthedocs.org/projects/gep-onsset/badge/?version=latest)](https://gep-onsset.readthedocs.io/en/latest/?badge=latest)

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/global-electrification-platform/gep-onsset/HEAD)

Documentation: https://gep-onsset.readthedocs.io/en/latest/index.html#



Running the Guinea scenario matrix from the control file
--------------------------------------------------------

All scenarios of the study are declared in `Scenarios/guinea_scenarios.json`
(fourteen scenarios: five demand cases at the reference grid cost of 0.1 USD/kWh,
then the three Table 1 cases at 0.047, 0.078 and 0.22 USD/kWh). Every lever is
explicit in that file, including the ones the notebook never exported
(technology switches, productive-demand preference, tier energies, calibration
thresholds). `gep_onsset/scenario_runner.py` executes the notebook's own model
logic from it; the notebook's section 7 calls the same code.

Environment (once):

    conda env create -f environment_guinea.yml
    conda activate gep_guinea

Inputs are never committed. They are expected under `GuineaRuns/Inputs/`
(the raw extraction `OnSSET_InputFile_20261018_100416.csv`, the hourly
profiles under `Guinea Data/`), outputs go to `GuineaRuns/Outputs/`.

Run:

    python run_scenarios.py Scenarios/guinea_scenarios.json                      # all fourteen, control-file order
    python run_scenarios.py Scenarios/guinea_scenarios.json --only BU_g0.1,BU_g0.22
    python run_scenarios.py Scenarios/guinea_scenarios.json --calibrate           # recalibrate from the raw input first
    python run_scenarios.py Scenarios/guinea_scenarios.json --batch 2026-10-24_table1 --force
    python run_scenarios.py Scenarios/guinea_scenarios.json --dry-run             # print resolved parameters, run nothing

Three keys of the control file (`existing_grid_cost_ratio`, `mv_increase_rate`,
`max_mv_line_dist`) are written to the Variables file for documentation but
never reach the model calls, exactly as in the notebook; `prioritization` must
be 5 because the notebook hard-codes it. A scenario whose folder already holds
a complete manifest with the same parameters and the same calibrated input is
skipped; if either changed, it is re-run. The calibrated file's sibling
`_parameters.json` must match the control file's `calibration` block, otherwise
the run stops and asks for `--calibrate`.

Each scenario writes `<id>_Results.csv`, `<id>_Summaries.csv` and
`<id>_Variables.csv` (the notebook's formats) plus `manifest.json` (every
parameter, input file hash, code version, timings) under
`GuineaRuns/Outputs/<batch>/<id>/`. The batch folder holds
`comparison_summary.csv` (one row per scenario, technology and year) and
`batch_log.txt`. A scenario whose manifest is complete is skipped unless
`--force`. A run takes about two minutes, almost all of it in the hybrid
mini-grid sizing, whatever the number of settlements.

Tests:

    python -m pytest                     # control file, tables, calibration, CLI (seconds)
    python -m pytest -m model            # mechanics on a 500-settlement sample (about ten minutes)
    python -m pytest -m slow             # regression gate: reproduces the shared Scenario_U3R1_0.047 run

The five earlier runs named `D2_*` and `D3_*` in the shared folder were produced
on the extraction from before the fix of 20 October 2026 and are superseded;
the control file records this in `meta.superseded_runs`.
