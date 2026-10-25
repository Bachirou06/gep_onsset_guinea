# Final scenario set and report restructure, design note

Date 2026-10-25. Decided with the mission lead after the team's scenario decision.

## Intent

The team fixed the final scenario set of the study: the three key demand cases at three grid
generation cost regimes, with a supply-side sensitivity on top. The report must present that
matrix as its core, and keep the earlier material (cost sweep, bins, other demand cases) as
extended sensitivity, so that nothing already computed is lost but the reader meets the final
scenarios first.

## The final scenario set

| Axis | Values |
|---|---|
| Demand cases (key cases, unchanged) | U3R1 (`TD_Low_minus`), U4R2 (`TD_High_minus`), BU |
| Grid cost regimes | Cost-reflective 0.22 USD/kWh (Mission 300 compact, no subsidy); Hydro cost 0.085 USD/kWh (hydro-dominant supply, subsidised); Current tariff 0.1 USD/kWh (subsidised, the earlier reference) |
| Supply-side sensitivity | `optgrid` (2030 connection and capacity caps removed) and `optgrid_optmg` (plus mini-grid PV panels 25 percent cheaper), at every regime |

Nine core scenarios, eighteen sensitivity scenarios. The value 0.085 was confirmed by the mission
lead (written as 0.85 in the team note). The regime names were chosen by the mission lead.

**Primary regime: Cost-reflective, 0.22 USD/kWh.** My call, open to a one-constant change: the
team listed it first, and the unsubsidised cost is the honest basis for comparing decentralised
options with a dam-fed grid. Maps, the phasing chapter, the hydro map, the corridor narrative and
the KPI tiles use the primary regime; every table carries all three regimes.

`REFERENCE_COST` stays 0.1 for the extended sensitivity (the sweep and bins were built around
it, and the other demand cases exist only at 0.1).

## Control file

Fifteen scenarios appended to `Scenarios/guinea_scenarios.json` in the same batch
(`2026-10-25_table1`): the three cases at 0.085, and both variants at 0.22 and 0.085 for the three
cases. Ids follow the existing pattern (`BU_g0.085`, `BU_optgrid_g0.22`, ...). Batch total 53.

## Report structure (changes only)

| Chapter | Change |
|---|---|
| 1 Key messages | KPI tiles for the three key cases at the primary regime; Table 1.1 core matrix (9 rows, six headline metrics); key messages recomputed over the core matrix: investment range across the nine, technology mix at the primary regime, regime effect per case (grid extension, decentralised share, investment, newly electrified LCOE from cost-reflective to the two subsidised regimes), supply-side sensitivity at the primary regime, hydro, 2030 un-served, newly electrified LCOE; sweep and bins sentences kept as extended sensitivity |
| 2 Scope | Regime definitions with sources; Table 2.1 gains Regime and Role columns (core, supply-side sensitivity, extended sweep, cost bin, other demand case) |
| 4 Core results | Title "Least-cost options for the final scenario set". Figures 4.1 to 4.4 over the nine core scenarios (x axis grouped by case, regimes adjacent); Tables 4.1, 4.1b, 4.2, 4.2b, 4.3 over the nine; maps 4.5a to c for the key cases at the primary regime; Figure 4.6 LCOE histograms for the key cases at the primary regime |
| 5 Metrics | Tables 5.1 to 5.4 and Figure 5.1 over the nine |
| 6 Hydro | Table 6.1 over the nine; map at BU primary |
| 7 Phasing | Primary regime; Table 7.1 and 7.1b for BU; two-panel maps for the three key cases |
| 8 Corridor | Tables 8.1 and 8.2 over the nine; narrative at BU primary |
| 9 Sensitivity | 9A Regime switches: Table 9.1 (per case and subsidised regime: switched settlements, people, largest flows), heat maps `fig-9-1-<case>-<regime>`, switch maps `map-9-2-<case>` (cost-reflective against hydro cost). 9B Supply-side sensitivity at every regime: Table 9.2 wide (case, regime, variant rows; investment, grid-extension people, mini-grid PV people, decentralised share, newly electrified LCOE, reference and variant and percent change), Figures 9.3 and 9.3b delta bars over the nine, map 9.4 (BU primary against optgrid_optmg). 9C Extended sensitivity: the cost sweep (Figures 9.5 to 9.9, Tables 9.3 and 9.4, relative to 0.1), other demand cases (Table 9.5, Figure 9.10), cost bins (Figures 9.11, 9.11b, 9.12, Table 9.6) |
| 10, 11 | Unchanged, plus the core matrix in the annex |

A core cell that is missing from the batch (not yet run) is shown as "not run" in tables and
skipped in figures; the build never fails on an incomplete matrix. Figure and map ids are
deterministic from case and regime keys, never from a running count.

## Non-goals

Bachirou's planned HV line correction (new extraction, full rerun) is a later step; this design
does not touch the model or the extraction. The with and without Koukoutamba comparison is
likewise later.

## Acceptance

- Fast suite green on the refreshed sample (53 scenarios).
- Full build: consistency PASS, every core id present, size under 16 MB.
- Rendered maps and heat maps checked by eye (ids above).
- No em-dash, no IRENA, no raw metric names in the body.
