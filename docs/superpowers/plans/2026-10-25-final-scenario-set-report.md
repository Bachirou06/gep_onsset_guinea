# Final scenario set report restructure, implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use checkbox syntax.

**Goal:** Present the nine core scenarios (three key cases x three grid-cost regimes) as the core of the report, with the supply-side sensitivity at every regime, and keep the earlier sweep, bins and other demand cases as extended sensitivity.

**Architecture:** Add regime constants and a `Batch.core()` accessor; key every core table and figure by a core label `"<study name>, <regime name>"` so the existing figure functions work unchanged; add three metric builders (core headlines, regime switch table, variant summary); generalise `variant_comparison` to a list of costs; restructure `build.py` and the template chapter by chapter.

**Tech stack:** as the report package (pandas, plotly, matplotlib, jinja2). Tests in `OnSSET_SENEGAL`.

**Spec:** `docs/superpowers/specs/2026-10-25-final-scenario-set-report-design.md`

## Global constraints

- Primary regime 0.22; `REFERENCE_COST` stays 0.1. `COST_LEVELS = [0.047, 0.078, 0.085, 0.1, 0.22]`.
- Core label format: `f"{CASE_STUDY_NAME[case]}, {REGIME_NAME[cost]}"`, for example `"BU, Cost-reflective"`.
- A missing core cell never fails the build.
- British spelling, no em-dash, no IRENA, no raw metric names in the body.
- Commit per task, author Thierry Odou, trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review focus

- A batch with the 0.085 regime absent (the current 38-scenario sample until the runs finish): tables show "not run", figures skip, ids of the present cells unchanged.
- A core scenario whose variant is missing at one regime: Table 9.2 row absent, no exception.
- Regime switch when no settlement changes: table row with zeros and "none", heat map replaced by a note with the same id.
- `lines_vs_cost` x axis now has five levels; the reference marker stays at 0.1.
- Key messages over nine headlines: min and max name the core label, not a bare case name.

---

### Task 1: Regime constants and `Batch.core()`

**Files:** modify `report/constants.py`, `report/data.py`; test `tests/test_report_core.py`.

**Produces:** `REGIMES`, `REGIME_ORDER = [0.22, 0.085, 0.1]`, `PRIMARY_COST = 0.22`, `REGIME_NAME`, `REGIME_KEY` (`cost_reflective`, `hydro_cost`, `current_tariff`), `REGIME_SOURCE`, `CORE_CELLS = [(case, cost) for case in KEY_CASES for cost in REGIME_ORDER]`, `core_label(case, cost) -> str`, `COST_LEVELS` with 0.085, `COST_ROLE[0.085] = "hydro cost regime"`. `Batch.core() -> dict[(case, cost), ScenarioData]` in `CORE_CELLS` order, present cells only; `Batch.core_labels() -> dict[(case, cost), str]`.

- [ ] Step 1: write tests `test_core_constants`, `test_batch_core_returns_present_cells_in_order` (on `report_sample_batch`: the 0.22 and 0.1 cells present for all three cases; 0.085 present only once the sample is refreshed, so assert membership for the two certain regimes and that keys are a subset of `CORE_CELLS` in order), `test_core_label_format`.
- [ ] Step 2: run, expect ImportError / AttributeError.
- [ ] Step 3: implement.
- [ ] Step 4: run `pytest tests/test_report_core.py tests/test_report_data.py tests/test_report_figures.py`; the `lines_vs_cost` test must still pass with five levels.
- [ ] Step 5: commit `feat(report): regime constants and Batch.core()`.

### Task 2: Core metric builders

**Files:** modify `report/metrics.py`; test `tests/test_report_core.py` (append).

**Produces:**
- `core_headlines(batch) -> dict[str, dict]` keyed by core label, in `CORE_CELLS` order (`headline` of each present cell).
- `regime_switch_table(batch) -> pd.DataFrame` columns `demand_case, from_cost, to_cost, settlements, people, flows` (flows = list of `(from_code, to_code, people)` top three), one row per key case and subsidised regime, from the primary regime; rows only for present pairs.
- `variant_comparison(batch, grid_costs=None)` where `None` means `REGIME_ORDER`; output gains a `grid_cost` column.
- `variant_summary(vc) -> pd.DataFrame` wide: index `(demand_case, grid_cost, variant)`, columns `<metric>_ref, <metric>_var, <metric>_pct` for `investment_musd_cum, grid_ext_people_2040, mg_pv_people_2040, dre_share_new_connections, lcoe_energy_w_excl_dens`; `dre_share_new_connections` added to `VARIANT_METRICS`.

- [ ] Step 1: tests on the sample batch and on the synthetic `frame()`: `test_core_headlines_keys_are_core_labels`, `test_regime_switch_table_rows_and_flow_shape`, `test_variant_comparison_covers_every_regime_present`, `test_variant_summary_columns`.
- [ ] Step 2: run, expect failures on missing names.
- [ ] Step 3: implement.
- [ ] Step 4: run `pytest tests/test_report_core.py tests/test_report_metrics.py tests/test_report_variants.py tests/test_report_cost_bins.py`.
- [ ] Step 5: commit `feat(report): core metric builders`.

### Task 3: Key messages over the core matrix

**Files:** modify `report/messages.py`; test `tests/test_report_core.py` (append).

**Produces:** `km_investment_range` unchanged in signature (keys may be core labels; `name()` returns a label unchanged); `km_regime_effect(core_h: dict, switch_df) -> dict` one sentence per key case; `km_supply_variants(vc, case="BU", grid_cost=PRIMARY_COST)` filters on `grid_cost` when the column exists; `key_messages(core_h, sens, deltas, hydro, variants, switch_df, primary_h)` where `primary_h` is the headlines of the three key cases at the primary regime (used by `km_tech_mix`, `km_unserved_2030`, `km_hydro`).

- [ ] Step 1: tests `test_km_regime_effect_names_regimes_and_directions`, `test_km_supply_variants_filters_on_primary_cost`, `test_key_messages_accepts_core_inputs`.
- [ ] Step 2: run, expect failures.
- [ ] Step 3: implement.
- [ ] Step 4: run `pytest tests/test_report_core.py tests/test_report_messages.py tests/test_report_review_fixes.py tests/test_report_dre_mix.py tests/test_report_wording_v2.py`.
- [ ] Step 5: commit `feat(report): key messages over the core matrix`.

### Task 4: Build and template restructure

**Files:** modify `report/build.py`, `report/templates/report.html.j2`, `report/constants.py` (CHAPTERS titles); tests `tests/test_report_build.py` (EXPECTED ids), `tests/test_report_core.py` (append build checks).

**Produces:** the chapter layout of the spec. Ids: `map-4-5-<case>`, `map-7-1-<case>`, `fig-9-1-<case>-<regime_key>`, `map-9-2-<case>`, `fig-9-3`, `fig-9-3b`, `map-9-4`, `fig-9-5` to `fig-9-9`, `fig-9-10`, `fig-9-11`, `fig-9-11b`, `fig-9-12`; tables `t11` (core matrix), `t92` (variant summary), `t93`, `t94`, `t95`, `t96`; section ids `regime-switches`, `supply-variants`, `extended`, `cost-bins`.

- [ ] Step 1: update `EXPECTED_FIGURES` and `EXPECTED_MAPS`; add `test_core_tables_and_not_run_cells` (sample build: Table 1.1 has nine rows or "not run" cells; no raw metric names; `"Cost-reflective"` appears in Table 4.1).
- [ ] Step 2: run `pytest tests/test_report_build.py tests/test_report_core.py`, expect failures on missing ids.
- [ ] Step 3: restructure `build.py` and the template.
- [ ] Step 4: run the whole fast suite.
- [ ] Step 5: commit `feat(report): core matrix layout, regime switches, supply-side sensitivity at every regime`.

### Task 5: Sample refresh, full build, README, publish

- [ ] Step 1: after the 15 runs complete, delete `tests/_cache/report_sample_500/2026-10-25_table1` and `tests/_cache/report_sample_500_core/...`, update the count assertions (38 to 53; core sample 21 to 24), run the fast suite.
- [ ] Step 2: full build in `OnSSET_SENEGAL`; verify consistency PASS, every id, size; view the new maps and heat maps.
- [ ] Step 3: README section "Final scenario set" (control file note, regime names, primary regime).
- [ ] Step 4: commit, stage the HTML, republish to the same artifact URL, update memory.
