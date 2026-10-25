"""Batch discovery, manifests, compact per-settlement tables with a cache, and the
consistency check of per-settlement aggregates against comparison_summary.csv."""
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from report.constants import (CACHE_SCHEMA_VERSION, CASE_ORDER, CATEGORY_COLUMNS, INT8_COLUMNS,
                              KEY_TO_CODE, NOT_ASSIGNED, REFERENCE_COST, RESULT_COLUMNS, SUMMARY_INDEX,
                              YEARS)


@dataclass
class ScenarioData:
    scenario_id: str
    demand_case: str
    grid_cost: float
    urban_tier: int
    rural_tier: int
    label: str
    manifest: dict
    settlements: pd.DataFrame
    summaries: pd.DataFrame
    scenario_dir: Path


@dataclass
class Batch:
    batch_dir: Path
    name: str
    scenarios: dict                      # scenario_id -> ScenarioData, control-file order
    comparison: pd.DataFrame
    control: dict
    batch_log: str = ""
    checks_md: str = ""
    _by_case: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        for s in self.scenarios.values():
            self._by_case.setdefault(s.demand_case, {})[s.grid_cost] = s

    def reference(self) -> list:
        """The demand cases at the reference grid cost, in DEMAND_CASES display order."""
        out = []
        for case in CASE_ORDER:
            s = self._by_case.get(case, {}).get(REFERENCE_COST)
            if s is not None:
                out.append(s)
        return out

    def by_case(self, demand_case: str) -> dict:
        """grid_cost -> ScenarioData for one demand case."""
        return dict(self._by_case.get(demand_case, {}))

    def provenance(self) -> dict:
        ms = [s.manifest for s in self.scenarios.values()]
        shas = sorted({m.get("calibrated_csv_sha256", "") for m in ms})
        return {
            "batch": self.name,
            "batch_dir": str(self.batch_dir),
            "n_scenarios": len(ms),
            "calibrated_csv": sorted({Path(m.get("calibrated_csv", "")).name for m in ms}),
            "calibrated_csv_sha256": shas[0] if len(shas) == 1 else shas,
            "calibrated_csv_sha_count": len(shas),
            "control_file": sorted({Path(m.get("control_file", "")).name for m in ms}),
            "control_file_sha256": sorted({m.get("control_file_sha256", "") for m in ms})[0],
            "git_commits": sorted({str(m.get("git_commit"))[:7] for m in ms}),
            "git_dirty_any": any(bool(m.get("git_dirty")) for m in ms),
            "python": sorted({m.get("python", "") for m in ms}),
            "pandas": sorted({m.get("pandas", "") for m in ms}),
            "rows_out": sorted({int(m.get("rows_out", 0)) for m in ms}),
            "started": min(m.get("started", "") for m in ms),
            "finished": max(m.get("finished", "") for m in ms),
            "model_seconds": round(sum(float(m.get("seconds", 0)) for m in ms), 1),
        }


# ---------------------------------------------------------------------------
# Discovery and manifests
# ---------------------------------------------------------------------------
def load_manifest(scenario_dir: Path) -> dict:
    return json.loads((Path(scenario_dir) / "manifest.json").read_text(encoding="utf-8"))


def discover_scenarios(batch_dir: Path) -> list:
    """Scenario folders of a batch whose manifest says complete, sorted by name."""
    out = []
    for d in sorted(Path(batch_dir).iterdir()):
        if d.is_dir() and (d / "manifest.json").exists():
            try:
                if load_manifest(d).get("status") == "complete":
                    out.append(d)
            except json.JSONDecodeError:
                continue
    return out


def load_control(manifest: dict, repo_root: Path) -> dict:
    """The control file recorded in a manifest, else the repository's study file."""
    candidates = [Path(manifest.get("control_file", "")), Path(repo_root) / "Scenarios" / "guinea_scenarios.json"]
    for p in candidates:
        if p and p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError("control file not found: " + ", ".join(str(c) for c in candidates))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Compact per-settlement table with a parquet cache
# ---------------------------------------------------------------------------
def _cache_key(results_csv: Path, manifest: dict, columns) -> dict:
    st = results_csv.stat()
    return {"source_path": str(results_csv), "source_bytes": st.st_size, "source_mtime_ns": st.st_mtime_ns,
            "calibrated_csv_sha256": manifest.get("calibrated_csv_sha256"), "columns": list(columns),
            "schema": CACHE_SCHEMA_VERSION}


def _shrink(df: pd.DataFrame) -> pd.DataFrame:
    for c in INT8_COLUMNS:
        if c in df.columns:
            df[c] = df[c].fillna(99).round().astype("int8")
    for c in CATEGORY_COLUMNS:
        if c in df.columns:
            df[c] = df[c].astype(str).replace({"Unknown": NOT_ASSIGNED, "nan": NOT_ASSIGNED}).astype("category")
    if "id" in df.columns:
        df["id"] = df["id"].astype("int32")
    if "HydropowerFID" in df.columns:
        df["HydropowerFID"] = df["HydropowerFID"].fillna(-1).astype("int32")
    return df


def _read_results(results_csv: Path, columns) -> pd.DataFrame:
    df = pd.read_csv(results_csv, usecols=list(columns), encoding="utf-8")
    return _shrink(df[list(columns)].copy())


def load_settlements(scenario_dir, cache_dir, columns=RESULT_COLUMNS, id_subset=None,
                     use_cache: bool = True, log=None) -> pd.DataFrame:
    """The compact per-settlement table of one scenario, from the parquet cache when its
    sidecar matches the source file (path, size, mtime, calibrated input hash, columns)."""
    scenario_dir = Path(scenario_dir)
    sid = scenario_dir.name
    results_csv = scenario_dir / f"{sid}_Results.csv"
    manifest = load_manifest(scenario_dir)
    key = _cache_key(results_csv, manifest, columns)
    cache_dir = Path(cache_dir)
    parquet = cache_dir / f"{sid}.parquet"
    sidecar = cache_dir / f"{sid}.cache.json"
    df = None
    if use_cache and parquet.exists() and sidecar.exists():
        try:
            if json.loads(sidecar.read_text(encoding="utf-8")) == key:
                df = pd.read_parquet(parquet)
        except (json.JSONDecodeError, OSError, ValueError):
            df = None
    if df is None:
        df = _read_results(results_csv, columns)
        if use_cache:
            cache_dir.mkdir(parents=True, exist_ok=True)
            df.to_parquet(parquet, index=False)
            sidecar.write_text(json.dumps(key, indent=1), encoding="utf-8")
            if log:
                log(f"[{sid}] cached {len(df)} settlements")
    if id_subset is not None:
        df = df[df["id"].isin(np.asarray(id_subset))].reset_index(drop=True)
    return df


def load_summaries(scenario_dir: Path) -> pd.DataFrame:
    sid = Path(scenario_dir).name
    s = pd.read_csv(Path(scenario_dir) / f"{sid}_Summaries.csv", index_col=0)
    return s.reindex(SUMMARY_INDEX)


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------
def load_batch(batch_dir, repo_root, cache_dir=None, id_subset=None, use_cache=True, log=print) -> Batch:
    batch_dir = Path(batch_dir)
    cache_dir = Path(cache_dir) if cache_dir is not None else batch_dir / "report" / "cache"
    folders = discover_scenarios(batch_dir)
    if not folders:
        raise FileNotFoundError(f"no complete scenario folder under {batch_dir}")
    manifests = {d.name: load_manifest(d) for d in folders}
    control = load_control(next(iter(manifests.values())), repo_root)
    order = [s["id"] for s in control.get("scenarios", [])]
    ordered = [sid for sid in order if sid in manifests] + sorted(sid for sid in manifests if sid not in order)
    scenarios = {}
    for sid in ordered:
        d = batch_dir / sid
        m = manifests[sid]
        p = m.get("parameters", {})
        scenarios[sid] = ScenarioData(
            scenario_id=sid, demand_case=m.get("demand_case", ""), grid_cost=float(p.get("grid_generation_cost")),
            urban_tier=int(p.get("urban_target_tier")), rural_tier=int(p.get("rural_target_tier")),
            label=m.get("label", sid), manifest=m,
            settlements=load_settlements(d, cache_dir, id_subset=id_subset, use_cache=use_cache, log=log),
            summaries=load_summaries(d), scenario_dir=d)
    comparison = pd.read_csv(batch_dir / "comparison_summary.csv")
    batch_log = (batch_dir / "batch_log.txt").read_text(encoding="utf-8") if (batch_dir / "batch_log.txt").exists() else ""
    checks = (batch_dir / "CHECKS.md").read_text(encoding="utf-8") if (batch_dir / "CHECKS.md").exists() else ""
    return Batch(batch_dir=batch_dir, name=batch_dir.name, scenarios=scenarios, comparison=comparison,
                 control=control, batch_log=batch_log, checks_md=checks)


# ---------------------------------------------------------------------------
# Consistency: per-settlement aggregates against comparison_summary.csv
# ---------------------------------------------------------------------------
def check_consistency(batch: Batch, atol_people: float = 1.0, atol_musd: float = 0.01,
                      atol_mw: float = 0.01) -> pd.DataFrame:
    """One row per scenario x technology x year x metric, with the per-settlement value,
    the comparison_summary value and an ok flag. Code 99 in 2030 is compared on
    population only (the summary's new_connections for code 99 count the unserved).
    Capacity and investment follow the summary's rounding (2 decimals)."""
    rows = []
    comp = batch.comparison.set_index(["scenario_id", "technology", "year"])
    for sid, s in batch.scenarios.items():
        df = s.settlements
        for year in YEARS:
            code = df[f"FinalElecCode{year}"]
            served = code < 99
            for key, c in KEY_TO_CODE.items():
                sel = code == c
                if key == "Non-electrified" and year == 2040:
                    continue
                vals = {
                    "population": float(df.loc[sel, f"Pop{year}"].sum()),
                    "new_connections": float(df.loc[sel, f"NewConnections{year}"].sum()),
                    "capacity_mw": round(float(df.loc[sel & served, f"NewCapacity{year}"].sum() / 1000), 2),
                    "investment_musd": round(float(df.loc[sel & served, f"InvestmentCost{year}"].sum() / 1e4) / 1e2, 2),
                }
                if c == 99:
                    vals = {"population": vals["population"]}
                for metric, v in vals.items():
                    try:
                        ref = float(comp.loc[(sid, key, year), metric])
                    except KeyError:
                        ref = float("nan")
                    tol = {"population": atol_people, "new_connections": atol_people,
                           "capacity_mw": atol_mw, "investment_musd": atol_musd}[metric]
                    rows.append({"scenario_id": sid, "technology": key, "year": year, "metric": metric,
                                 "settlements": v, "summary": ref, "ok": bool(abs(v - ref) <= tol)})
    return pd.DataFrame(rows)
