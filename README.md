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

The final scenario set (team decision, 25 October 2026)
-------------------------------------------------------

The study's final scenarios are the three key demand cases, U3R1
(`TD_Low_minus`), U4R2 (`TD_High_minus`) and BU, at three grid generation cost
regimes:

| Regime | Grid cost | Meaning |
|---|---|---|
| Cost-reflective | 0.22 USD/kWh | the cost-reflective generation cost of the Mission 300 compact, no subsidy |
| Hydro cost | 0.085 USD/kWh | the generation cost of a hydro-dominant supply, subsidised |
| Current tariff | 0.1 USD/kWh | the current subsidised tariff-based level, the reference of the earlier runs |

Nine core scenarios, each with two supply-side variants (`optgrid`: the 2030
connection and capacity caps removed; `optgrid_optmg`: plus mini-grid PV
panels 25 percent cheaper). The report presents the core matrix first; the
cost-reflective regime is the primary one (maps, phasing, KPI tiles), set by
`PRIMARY_COST` in `report/constants.py`. The earlier cost sweep (0.047,
0.078, 0.1, 0.22), the bottom-up cost bins and the other demand cases stay in
the batch as the extended sensitivity of chapter 9. All of it lives in the
same control file and the same batch.

The HV correction (28 October 2026)
-----------------------------------

The 2026-10-18 extraction had used the full line layer `HT_existing_line.shp`
(66 features, existing and planned mixed) for both HV distance columns, so the
model treated every planned line as built. The colleague's corrected layers
split the 225 kV network into built sections (`Existing_HV_2026-10-28.gpkg`)
and unbuilt sections (`Planned_HV_2026-10-28.gpkg`, under `HV_Planned_lines/`).
`tools/hv_distances.py` recomputes the two columns with the extraction
notebook's own method (clip to the country, a point every 100 m, nearest point
to the settlement centroid in EPSG:32628; it reproduces the previous column to
within a metre) and writes a sidecar JSON with layer hashes and statistics:

    python tools/hv_distances.py GuineaRuns/Inputs/OnSSET_InputFile_20261018_100416.csv GuineaRuns/Inputs/OnSSET_InputFile_20261028_hv.csv         --admin "GuineaRuns/Inputs/Guinea Data/Boundaries/gadm41_GIN_0.shp"         --existing "GuineaRuns/Inputs/Guinea Data/HV_Existing_lines/Existing_HV_2026-10-28.gpkg"         --existing "GuineaRuns/Inputs/Guinea Data/HV_Existing_lines/HT_existing_line.shp|status=Existing"         --planned "GuineaRuns/Inputs/Guinea Data/HV_Planned_lines/Planned_HV_2026-10-28.gpkg"         --old "GuineaRuns/Inputs/Guinea Data/HV_Existing_lines/HT_existing_line.shp"

Two choices are recorded in the control file's notes. The existing network
adds the source's Existing-status features (the Conakry-area 110 and 60 kV
lines, Kaleta-Maneah, Kindia-Linsan, Linsan-Mamou, Garafari-Linsan), which
the corrected layer leaves out but which serve 3.2 million people within
10 km. The planned network holds the unbuilt sections only, as the colleague
delivered them; the model reaches existing lines through the settlements
already electrified. `Scenarios/guinea_scenarios_noKKT.json` is the paired
control file (nine core scenarios, the Linsan to Manantali feature removed
from the planned network, input `OnSSET_InputFile_20261028_hv_noKKT.csv`);
its batch feeds the with and without comparison of chapter 8 through the
report's `--paired` option.

Building the results report
---------------------------

`report/` turns a finished batch into one self-contained HTML file (charts in
Plotly, maps as PNG, every number traceable to the batch, the input hash and
the code commit), organised by the objectives of the study:

    python -m report.build GuineaRuns/Outputs/2026-10-25_table1 --inputs "GuineaRuns/Inputs/Guinea Data"
    python -m report.build GuineaRuns/Outputs/2026-10-25_table1 --inputs "GuineaRuns/Inputs/Guinea Data" --sample 500   # quick check
    python -m report.build GuineaRuns/Outputs/2026-10-25_table1 --no-maps --no-geo                                        # charts and tables only
    python -m report.build GuineaRuns/Outputs/2026-10-28_hvfix --inputs "GuineaRuns/Inputs/Guinea Data" --paired GuineaRuns/Outputs/2026-10-28_hvfix_noKKT

Output: `GuineaRuns/Outputs/<batch>/report/guinea_scenarios_report_<batch>.html`
plus `build_manifest.json` (asset sizes, versions, consistency result) and a
`cache/` of compact per-settlement tables that makes rebuilds fast. Options:
`--corridor-km` (default 10, measured from the Linsan to Manantali feature of
the Koukoutamba line), `--map-dpi`, `--map-colours N` (palette-quantise the
maps to shrink the file), `--no-cache`.

Environment note (October 2026): in the `gep_guinea` environment any
matplotlib save crashes once a GDAL-based library has been imported (a
Windows delay-load DLL conflict between the conda-forge builds of matplotlib
and pyogrio). Until that is resolved, build the report and run the report
tests with the `OnSSET_SENEGAL` environment (Python 3.10, geopandas 1.1.2,
plotly 6.5.2), which renders everything; the model itself keeps running in
`gep_guinea`.

Report tests:

    python -m pytest tests/test_report_*.py          # sample-based, about a minute
    python -m pytest tests/test_report_build.py -m slow   # full build on the real batch
