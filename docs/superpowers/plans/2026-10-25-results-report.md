# Guinea scenario results report (static HTML) — implementation plan

## Context

Fourteen GEP-OnSSET scenarios for the Guinea decentralised-energy study (consultancy for International
Rivers, lead analyst Bachirou Djibo, mission lead Thierry Odou) were run on 25 October 2026 into
`GuineaRuns/Outputs/2026-10-25_table1/` by the new scenario runner (branch `scenario-control`, closed and
reviewed). The colleague's progress deck of 23 October presents three cases at the reference grid cost and a
first Koukoutamba-basin extract, and lists as next steps the grid-cost sensitivity, the protected-area and
basin extracts, and the subsidised-versus-unsubsidised comparison.

The user wants ONE self-contained static HTML report, neutral identity (no logo, no IRENA mention), in
English, that carries every critical insight the study's objectives need: reference results at
0.1 USD/kWh compared across the five demand cases first, a sensitivity chapter, a Koukoutamba corridor
section (10 km), region, urban/rural and hydro-site detail, least-cost maps per case; charts and maps at
the rigour of the IRENA Senegal work (publication maps with boundaries, network overlay, north arrow,
scale bar, data-driven legends with counts and shares, sources, neutral disclaimer; numbered figures and
tables; every number traceable to batch, input hash and code commit). Every chapter below names the ToR
objective it informs (eight tasks in `Guinea_Study_README.md`, read-only reference in
`C:\Users\OOdou\OneDrive - International Renewable Energy Agency - IRENA\Desktop\MyDownload\InternationalWaters`).

Verified facts that shape the design (planner, read-only checks on the batch):
- Results CSVs are UTF-8 (`Boké` decodes correctly with the pandas default); 159 settlements carry
  `Admin_1 == 'Unknown'` (report as "Not assigned"); `id` is unique and identical across all 14 files.
- `comparison_summary.csv` 2030 "Total" new_connections includes the 6.1 M not-yet-electrified people
  (code 99); capacity and investment do not. All per-connection and per-million-USD metrics are computed
  from codes < 99 only, and 2030 LCOE statistics filter `FinalElecCode2030 < 99`.
- Grid densification LCOE equals the grid generation cost by construction (`pre_electrification` sets
  `Grid<year> = grid_price` for start-year electrified settlements: 5,198 settlements, 18.6 M people in
  2040). Headline LCOE is energy-weighted over all served settlements, always shown beside "excluding
  densification", with a footnote.
- `PlannedHVLineDist == CurrentHVLineDist` everywhere: the planned-HV layer used in the extraction is a
  copy of the existing network, so the Koukoutamba line was never in the model's planned grid. Caveat in
  chapter 2; the corridor is computed from `HV_KKT/HV_KKT.shp` directly.
- `HV_KKT.shp` has two features: Linsan to Manantali (370.6 km) and Maneah to Grandes Chutes (40.8 km,
  next to Conakry). Within 10 km of both: 4,598 settlements, 9.54 M people (Conakry). Decision: corridor
  = Linsan to Manantali only, 10 km (user's choice), with 5 km and 25 km rows as sensitivity.
- Manifests: all complete, one calibrated input sha (`1bd32749…`), commits `bcb76a7` (2) and `13fbc80`
  (12), `git_dirty: true`; the report prints this honestly.
- Protected-area layers exist: 117 polygons (EPSG:3857), Moyen-Bafing park (593 settlements, 67.7 k
  people), 9 areas spanned by the HV line, and `Localité_affected_BR.gpkg` (the 5 localities named in the
  deck: 1,380 settlements, 141.5 k people).
- Switch example BU 0.1 vs 0.22 USD/kWh: 1,303 settlements, 3.0 M people change technology, 1,264 of
  them from grid extension to mini-grid PV. Grid extension is the sensitive quantity.

## Decisions (made; veto at approval)

| Topic | Decision |
|---|---|
| Form | One HTML file, plotly.js inlined (4.84 MB), charts Plotly, maps matplotlib PNG as data URIs, sticky chapter nav, figure and table numbering, captions and sources. Target under 15 MB. |
| Code | Self-contained package `report/` in GuineaWork; no runtime import from the Senegal project nor from `gep_onsset` (manifests and the control JSON carry what is needed). Patterns borrowed: extent computation, draw order, legend with population per class, stacked-bar trace loop. |
| Environment | Extend `environment_guinea.yml` with plotly, geopandas, pyarrow, jinja2 (conda-forge); `conda env update`; re-run `pytest` and `pytest -m slow` once to prove the model numerics did not move. Code stays 3.10-compatible so `OnSSET_SENEGAL` works as fallback. |
| Palette | Okabe-Ito colour-blind-safe: 1 Grid densification #0072B2, 2 Grid extension #56B4E9, 3 Stand-alone PV #E69F00, 5 Mini-grid PV with battery #009E73, 7 Mini-grid hydro #CC79A7, 99 Not yet electrified #BBBBBB. Demand cases on a blue ramp, BU in #D55E00. |
| Maps | Neatline frame: title band (no logo), full-width map, legend overlay with "label — n settlements (x% of people)", two-tone north arrow, 0-50-100 km scale bar (lat_center 10.5), footer with source note (batch, scenario, columns, build time) and neutral disclaimer ("Boundaries and names shown do not imply any opinion on the part of the authors concerning the legal status of any territory or the delimitation of its frontiers"). Guinea only (gadm41_GIN_0/1), no neighbouring countries; existing HV solid dark grey, Koukoutamba line dashed, mini-hydro sites used as markers where relevant. Draw order stand-alone, mini-grid, grid on top. 150 dpi, 10 x 8.5 in; `--map-colours` quantisation option. |
| Headline LCOE | Energy-weighted delivered LCOE 2040 over served settlements, with "excluding densification" beside it. |
| Corridor | Linsan to Manantali feature only, 10 km, plus 5 km and 25 km sensitivity rows; subsets for the 5 affected localities, Moyen-Bafing park and the 9 protected areas spanned by the line. The paired with/without-Koukoutamba scenario is out of scope (not run). |
| Maps per case | 2040 least-cost map per demand case, plus a 2030/2040 two-panel map for the phasing chapter (BU and TD_Low). |
| Language, style | English, British spelling, no em-dashes (test enforced), no IRENA mention, no logo. |

## Chapters mapped to the study objectives

| # | Chapter | Objective informed (ToR task) | Main exhibits |
|---|---|---|---|
| 1 | Key messages | all | KPI tiles per demand case; 8 templated sentences from the numbers |
| 2 | Scope, scenarios, data, caveats | method transparency (open-access selling point) | Table 2.1 scenario matrix (ids and study names U3R1/U3R2/U4R3/U5R3/BU); 2.2 assumptions from manifests; 2.3 calibration and input file; 2.4 superseded runs; caveats list (planned-HV copy, densification LCOE, 2030 totals) |
| 3 | Energy access today and the un-served | task 1 (access and poverty, communities unlikely to reach the grid) | Table 3.1 start-year electrification by region and urban/rural (ElecStart, PopStartYear); Fig 3.1 map of start-year status; Table 3.2 settlements never served by grid in any scenario (people, regions) |
| 4 | Least-cost options at the reference cost | tasks 2 and 3 (best options; solar for households and productive uses) | Figs 4.1-4.4 stacked bars (population, new connections, capacity, investment; 2030 and 2040) across the 5 cases; Fig 4.5 a-e least-cost maps 2040; Table 4.1 headline per case; Table 4.2 region x case (population by category, investment); Table 4.3 urban/rural; Fig 4.6 LCOE distributions |
| 5 | The three study metrics | task 6 (costs and benefits vs grid and utility scale) and the proposal's comparison metrics | Tables 5.1-5.3 by technology and case: investment per new connection, people per million USD, energy-weighted LCOE (with excl.-densification line); Fig 5.1 grouped bars of the three totals; Table 5.4 grid vs off-grid shares, all and newly electrified only |
| 6 | Hydro mini-grids | task 5 (micro-hydro and mini-grid hydro feasibility, indicative) | Table 6.1 sites, settlements, people, MW, MUSD, distance per case; Fig 6.1 map of sites used with the 304-site potential layer in the background; note on the 10 km and 1 MW rules |
| 7 | Phased roadmap 2030 and 2040 | deliverable 3 (phased roadmap by area and horizon) | Table 7.1 new connections, capacity and investment by period, technology and region (BU and TD_Low); Fig 7.1 two-panel 2030/2040 maps; Fig 7.2 cumulative investment by period and technology |
| 8 | Koukoutamba corridor and protected areas | task 4 (Koukoutamba comparison, preparatory) | Table 8.1 corridor (10 km, with 5 and 25 km rows): settlements, people, technology mix, LCOE, investment, USD per connection per case; Table 8.2 same for the 5 affected localities, Moyen-Bafing, the 9 spanned areas; Fig 8.1 corridor map; statement of what the paired scenario will add (dam capacity, cost, dry-season firm output) |
| 9 | Sensitivity analysis | task 6 (risks), deck next step (subsidised 0.1 vs unsubsidised 0.22) | Figs 9.1-9.3 investment, capacity, USD per connection and LCOE vs grid cost (TD_Low, TD_High, BU; reference marked); Fig 9.4 technology shares vs cost; Table 9.1 grid extension by cost level; Table 9.2 switching vs reference with top flows; Fig 9.5 switch heatmap BU 0.1 vs 0.22; Fig 9.6 switch map; Table 9.3 demand variants (TD_Low_minus vs TD_Low, TD_High_plus vs TD_High) with deltas; Fig 9.7 delta bars |
| 10 | What the model does and does not say | tasks 7 and 8 (barriers, policy, recommendations) | Short list of evidence the report supplies for the policy chapters, and what is outside the model (tariffs, financing, institutions, dam's firm output) |
| 11 | Annex | reproducibility | A.1 overrides; A.2 manifests (commit, dirty, sha, rows, seconds); A.3 consistency check of per-settlement aggregates vs comparison_summary.csv; A.4 Summaries tables (collapsible); glossary; method notes with formulae; batch_log and CHECKS.md verbatim |

## Module layout (new package `report/` at the repository root)

- `report/constants.py`: TECH map, TECH_ORDER [1,2,5,7,3,99], CATEGORY colours, DEMAND_CASES order with
  study names, COST_LEVELS, REFERENCE_COST 0.1, SENSITIVITY_CASES, YEARS, RESULT_COLUMNS (usecols),
  CHAPTERS (anchors and titles), CACHE_SCHEMA_VERSION, DISCLAIMER text.
- `report/data.py`: `discover_scenarios(batch_dir)`, `load_manifest`, `load_control(manifest, repo_root)`
  (json; fallback `Scenarios/guinea_scenarios.json`), `load_settlements(scenario_dir, cache_dir,
  columns, id_subset, use_cache)` with parquet cache + sidecar `{source_path, bytes, mtime_ns,
  calibrated_csv_sha256, columns, schema}`, dtype shrink (codes int8, Admin category), `load_batch(...)
  -> Batch` (dataclass: scenarios in control order, comparison, control, provenance()), and
  `check_consistency(batch)` (per-settlement aggregates vs comparison_summary.csv; hard error on the full
  build, skipped on samples).
- `report/metrics.py` (pure, every number in the report): `tech_table(df, year)`, `cumulative_table`,
  `weighted_lcoe(df, year, weight, exclude_densification)`, `lcoe_by_tech`, `consultancy_metrics`,
  `headline`, `category_shares(newly_electrified_only)`, `region_table`, `urban_rural_table`,
  `hydro_table`, `start_year_table` (ElecStart by region and urban/rural), `never_grid_table(batch)`,
  `phasing_table(df)` (by period, technology, region), `lcoe_histogram`, `switches(df_ref, df_alt)`,
  `sensitivity_table(batch)`, `demand_delta(df_var, df_base)`, `corridor_table(df, geo_attr, radius)`.
- `report/geo.py` (geopandas lazy, `HAS_GEO`): `load_layers(inputs_dir)` (adm0, adm1, hv existing, kkt
  main feature, protected to EPSG:4326, moyen_bafing, affected_localities, mini_hydro),
  `settlement_geo_attributes(points, layers, cache_dir, radii_km=(5,10,25))` computed once per batch
  in EPSG:32629 (`sjoin_nearest`, `within`), cached with sidecar.
- `report/figures.py` (Plotly, template simple_white): `stacked_by_tech`, `grouped_metric_bars`,
  `lines_vs_cost`, `shares_vs_cost`, `lcoe_histograms`, `switch_matrix`, `delta_bars`,
  `fig_to_div(fig, div_id)` (include_plotlyjs False, responsive, no logo).
- `report/maps.py` (matplotlib): `technology_map(df, year, layers, title)`, `two_panel_map(df, layers)`,
  `switch_map`, `corridor_map`, `status_map` (start year), `hydro_map`; shared `neatline_frame()`,
  `draw_north_arrow`, `draw_scale_bar(lat_center=10.5)`, `legend_entries(df, year)` with counts and
  shares, `png_data_uri`, `shrink_png`.
- `report/messages.py`: formatters (`fmt_people`, `fmt_musd`, `fmt_lcoe`, `fmt_pct`, `direction`) and one
  small function per key message; a NaN input raises.
- `report/render.py`: `table_html(df, formats, caption)` (never emits "nan"), jinja2 `render(context)`
  with StrictUndefined; `report/templates/report.html.j2`, `style.css` (inlined).
- `report/build.py`: `build(batch_dir, repo_root, out_path, inputs_dir, id_subset, maps, geo,
  corridor_km, map_dpi, map_colours, log)`; CLI `python -m report.build <batch> [--out] [--inputs]
  [--no-maps] [--no-geo] [--corridor-km 10] [--map-dpi 150] [--map-colours 0] [--sample 500]
  [--no-cache]`; writes `report/guinea_scenarios_report_<batch>.html` and `build_manifest.json` (asset
  sizes, hashes, report commit, versions, consistency result).
- Tests: `tests/test_report_data.py`, `test_report_metrics.py` (six-row synthetic frame with
  hand-computed answers), `test_report_messages.py`, `test_report_maps.py`, `test_report_build.py` (fast
  sample build: every chapter anchor and figure id present; no `nan`, `None`, `IRENA` or em-dash outside
  script and style blocks), plus a `slow` full build (consistency PASS, TD_Low_g0.1 cumulative
  investment equals 420.59 + 1,331.83, file under 25 MB). `tests/conftest.py` gains a session fixture
  `report_sample_batch` (500 ids, seed 42, Results restricted to RESULT_COLUMNS, manifests copied).

Reference files: `gep_onsset/scenario_runner.py` (summary semantics lines 119-212, manifest fields
617-645, COMPARISON_COLUMNS), `tests/conftest.py` (`_sample` pattern), Senegal
`Model/onsset/tech_map.py` (`draw_scale_bar`, `_draw_north_arrow`, `build_tech_legend_entries`,
`build_legend_sections` as pattern sources only), `Model/onsset/charts.py` (`plotly_grouped_stack_bar`).

## Metric definitions (pinned)

Served rows in year y: `FinalElecCode_y < 99 and NewConnections_y > 0`. Codes C = {1,2,3,5,7}.
- Population by technology, year y: sum `Pop_y` over code t (99 reported separately for 2030).
- New connections, capacity (MW = kW/1000), investment (MUSD = USD/1e6) by technology and year over served rows; cumulative = 2030 + 2040.
- Investment per new connection (USD/person) = MUSD_cum x 1e6 / NC_cum; per household uses `NewConnections_y / NumPeoplePerHH`.
- People reached per million USD = NC_cum / MUSD_cum.
- Delivered LCOE 2040 (headline) = sum(MinimumOverallLCOE2040 x EnergyPerSettlement2040) / sum(Energy) over served rows with LCOE < 99; population-weighted variant; "excluding densification" = same over `ElecStart == 0`.
- Candidate-technology LCOE columns (Grid2040, SA_PV2040, MG_PV_Hybrid2040, MG_Hydro2040): 99 -> NaN, annex only, axis clipped at 1.0 USD/kWh.
- Grid vs off-grid share: codes {1,2} vs {3,5,7}, population 2040; and among `ElecStart == 0`.
- Hydro: nunique HydropowerFID where code 7, with settlements, people, MW, MUSD, mean HydropowerDist.
- Switching: inner join on id of FinalElecCode2040 reference vs alternative; counts and reference Pop2040 by (From, To).
- Corridor: settlements with `kkt_main_dist_km <= radius`; same metrics as chapter 5 per demand case.

## Implementation sequence (TDD per step, commit per step, branch `results-report` off `scenario-control`)

1. Environment: extend `environment_guinea.yml`; `conda env update -n gep_guinea`; run `pytest` and `pytest -m slow` to confirm the regression gate still passes. Commit.
2. `report/constants.py`, `report/data.py` (cache, consistency check), conftest sample fixture, `test_report_data.py`.
3. `report/metrics.py` with `test_report_metrics.py` on the synthetic frame (including the code-99, NewConnections 0 and LCOE 99 filters, and the densification exclusion).
4. `report/geo.py` with tests on the sample (corridor distances, within-polygon flags).
5. `report/maps.py` (neatline frame, legend with counts and shares, north arrow, scale bar, disclaimer) and `report/figures.py`; tests on the sample (PNG bytes, legend sums, figure ids).
6. `report/messages.py` with tests.
7. `report/templates`, `report/render.py`, `report/build.py`, `test_report_build.py`; first full build on the real batch; record size and timings in `build_manifest.json`.
8. README section "Building the report"; design note under `docs/superpowers/specs/`.
9. Fresh-reviewer pass on the whole branch (figures reviewed rendered, not only code), fix pass, then hand the HTML path to the user.

## Verification

- `python -m pytest` (fast suite including the sample report build, under a minute for the report tests).
- `python -m pytest -m slow` (regression gate + full report build consistency check).
- `python -m report.build GuineaRuns/Outputs/2026-10-25_table1 --inputs "GuineaRuns/Inputs/Guinea Data"`; open the HTML offline in a browser; check the sticky nav, hover a chart, confirm each map legend sums to 27.7 M people for 2040, confirm the provenance box shows the batch, input sha, commits and dirty flag; file size under 15 MB (quantise maps if not).
- Spot-check three numbers against the colleague's deck at 0.1 USD/kWh (BU investment 2040, U3R2 stand-alone PV population, U4R3 grid share) and explain any difference by the corrected input.
