# HV correction and the Koukoutamba paired case, design note (28 October 2026)

## What arrived

Two GeoPackages from the colleague, `Existing_HV.gpkg` (layer `clipped`, 28 features, EPSG:32628,
2,950 km, 17 distinct line names, every feature duplicated once) and `Planned_HV.gpkg` (layer
`symmetrical_difference`, 13 features, 1,508 km, 8 names, duplicates). Both carry the attribute
table of the study's line source `HT_existing_line.shp` (66 features, status `Existing` or
`Planned`, voltage 15 to 225 kV).

Findings (scripts in the session scratchpad, numbers from the 83,010-row input file):

- The source's `status` tags the 225 kV backbone as `Planned` (dataset vintage) and the Conakry-area
  110 and 60 kV lines, Kaleta-Maneah, Kindia-Linsan, Linsan-Mamou and Garafari-Linsan as `Existing`.
- `Existing_HV.gpkg` is the 225 kV backbone inside Guinea as built since (Boke-Kaleta-Souapiti-Linsan,
  Labe-Linsan, Kaleta-Linsan, Fomi-Kankan-Siguiri, Kankan-Kerouane-Beyla-Nzerekore-Yekepa, the
  Linsan to Manantali section as far as 11.3 N); its geometries coincide with the source's same-name
  features. It leaves out every `Existing`-status feature of the source.
- `Planned_HV.gpkg` is the remainder of those features: the cross-border ends (Boundiali-Kankan in
  Cote d'Ivoire, Sanankoroba-Siguiri in Mali, Kamakwie-Linsan in Sierra Leone), the Linsan to
  Manantali section north of 11.3 N (256 km, 121 km inside Guinea), the Fomi-Linsan gap (60 km),
  Labe-Mali (71 km), Mali-Sambangalou (32 km inside) and Boke-Saltinho (80 km inside). 948 of its
  1,508 km lie outside Guinea.
- The 2026-10-18 extraction used the full source for both columns (`PlannedHVLineDist` equals
  `CurrentHVLineDist`), so the previous batches treated every planned line as existing and as planned.
- The extraction method is reproducible: centroid to the nearest densified point in EPSG:32628
  matches the input column to 0.6 m on every non-zero row; the 273 zero rows are the notebook's
  polygon-intersection rule (the 83,010-polygon layer is not in the repository; the 48,019-feature
  `clusters.shp` is another layer).
- The model uses `CurrentHVLineDist` only as the path length of already electrified settlements
  (`current_mv_line_dist`); calibration runs on MV lines. `PlannedHVLineDist` drives the second
  extension round (any settlement may connect at the cost of its distance to a planned line) and the
  intensification distance (minimum with the planned MV distance).
- The Conakry-area omission moves the nearest existing line by more than 1 km for 9,257 settlements;
  3,752 of them (3.24 million people, Conakry 2.76 million, Kindia 0.47 million) lie within 10 km of a
  dropped line.
- The corridor layer of chapter 8 (`HV_KKT.shp`, Linsan to Manantali, 371 km) follows a different
  route from the Linsan to Manantali feature of the colleague's layers (overlap within 200 m: 1 to 4 km).

## Rulings

1. Existing network = `Existing_HV.gpkg` plus the `Existing`-status features of `HT_existing_line.shp`.
   Why: they are existing lines in the same source, they were in the previous extraction, and leaving
   them out changes the path distance of the settlements serving 3.2 million people. Cost if wrong:
   one rerun with the literal file (`--existing` once, 4 hours).
2. Planned network = `Planned_HV.gpkg` only, as delivered (the GEP convention: existing lines are
   reached through electrified settlements). Cost if wrong: one rerun with the union as planned
   layer; the previous batch already approximates that reading.
3. The zero rule is carried over from the previous column where the crossing line is still the
   nearest one (new distance equals the old centroid distance within 2 m); 245 of 273 zeros survive.
4. The corridor of chapter 8 stays on `HV_KKT.shp` (the study's corridor definition). The paired
   case removes the colleague's Linsan to Manantali feature from the planned network; the route
   difference is stated in the caveat and the corridor note. To settle with the colleague.
5. The paired case runs the nine core scenarios only (`Scenarios/guinea_scenarios_noKKT.json`,
   batch `2026-10-28_hvfix_noKKT`); the report takes it through `--paired`.
6. Superseded: batch `2026-10-25_table1` and the earlier D runs. The control file's notes say so.

## Deliverables

- `tools/hv_distances.py` with tests; input `OnSSET_InputFile_20261028_hv.csv` and its sidecar;
  `OnSSET_InputFile_20261028_hv_noKKT.csv` for the paired case (both under `GuineaRuns/`, not committed).
- Control file pointed at the corrected input; paired control file.
- Report: existing network and planned sections on the maps (`report/geo.py`, `report/maps.py`),
  Table 2.3 rows and caveat from the sidecar, chapter 8 section "With and without the Koukoutamba
  line" (Table 8.3, Figures 8.2 and 8.3, key message `km-koukoutamba`).
- README section "The HV correction (28 October 2026)".

## Addendum, 31 October 2026: the colleague's own re-extraction replaces rulings 1 to 3

The colleague delivered `OnSSET_InputFile_20261028_140602.csv`, the 2026-10-18 extraction with the two
HV columns recomputed by the extraction notebook from his layers. Checks (scratchpad scripts, numbers
from the file):

- Every column other than the two HV columns is identical to the 2026-10-18 file (same ids, coordinates,
  MV distances).
- `CurrentHVLineDist` is the distance to `Existing_HV.gpkg` alone; `PlannedHVLineDist` the distance to
  the union of `Existing_HV.gpkg` and `Planned_HV.gpkg`. Both reproduce to within 1 m on every non-zero
  row with the tool in EPSG:32628. The 193 and 203 zeros are a fresh polygon-intersection pass.
- The union reading of the planned column is the right one for the model: the second extension round
  offers every settlement a connection at its distance to that column, so the column must describe the
  whole future network. Ruling 2 (unbuilt sections only) is withdrawn.
- His existing layer omits the Existing-status features of the source (Conakry-area lines, Kaleta-Maneah,
  Kindia-Linsan, Linsan-Mamou, Garafari-Linsan). The mission lead chose to run his file as delivered;
  ruling 1 becomes a caveat and a question to the colleague. A candidate with those lines added to both
  columns (`OnSSET_InputFile_20261031_hv_union.csv`) was built and not run.
- The stated basis for the built/unbuilt split (overlap with the MV layer) does not reproduce: no built
  section runs within 500 m of an MV line for more than 9 percent of its length, and the unbuilt sections
  score zero as well. The split is recorded as the colleague's assessment, basis to be documented.
- Ruling 3 (carried-over zeros) is moot: the file carries the notebook's own zeros.

Rulings 4 to 6 stand. Runs of record: `2026-10-31_hv` (53 scenarios) and `2026-10-31_hv_noKKT` (nine
core scenarios, planned network = union minus the Linsan to Manantali feature of `Planned_HV.gpkg`,
existing column unchanged). The report draws the omitted Conakry-area lines in a lighter stroke
(`hv_existing_unmodelled` in `report/geo.py`) so the caveat is visible on every map.
