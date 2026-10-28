"""Recompute the two HV distance columns of an OnSSET input file from new line layers.

    python tools/hv_distances.py <input.csv> <output.csv> --admin <adm0> \
        --existing <layer> [--existing <layer> ...] --planned <layer> [...] \
        [--old <layer> ...] [--crs EPSG:32628] [--note "..."]

A layer spec is a path, optionally followed by "|field=value" to keep only matching features
(for example "HT_existing_line.shp|status=Existing") or "|field!=value" to drop them.

Method, identical to the GIS extraction notebook (funcs.ipynb, processing_lines): clip the lines
to the admin boundary, project, explode, place a point every 100 m along each line, and take the
nearest such point to each settlement centroid (X_deg, Y_deg), in kilometres. The notebook also
sets the distance to zero where the settlement polygon intersects a line. The polygons are not in
the repository, so that rule is carried over from the input file: a row whose old value is zero
keeps zero when the line that crossed it is still present, which is read as "the new distance
equals the old centroid distance to the old layers" (within two metres). Pass the old layers with
--old to enable this; without them the zero rule is not applied.

Writes the output CSV (every other column untouched) and a sidecar JSON
<output>.hv_distances.json with layer paths, hashes, feature counts, lengths and column statistics.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

COLUMNS = {"existing": "CurrentHVLineDist", "planned": "PlannedHVLineDist"}
STEP_M = 100
ZERO_TOL_KM = 0.002


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_layer(spec: str) -> gpd.GeoDataFrame:
    """'path', 'path|field=value' (keep matching features) or 'path|field!=value' (drop them)."""
    path, _, flt = spec.partition("|")
    g = gpd.read_file(path)
    if flt:
        if "!=" in flt:
            field, _, value = flt.partition("!=")
            g = g[g[field].astype(str) != value].copy()
        else:
            field, _, value = flt.partition("=")
            g = g[g[field].astype(str) == value].copy()
    return g


def line_points(layers, admin: gpd.GeoDataFrame, crs: str, step_m: int = STEP_M) -> np.ndarray:
    """Points every step_m metres along the lines clipped to admin, in crs. Shape (n, 2)."""
    pts = []
    adm = admin.to_crs("EPSG:4326")
    for layer in layers:
        g = gpd.clip(layer.to_crs("EPSG:4326"), adm).to_crs(crs)
        for geom in g.geometry.explode(index_parts=False):
            if geom is None or geom.is_empty:
                continue
            for d in range(0, int(geom.length), step_m):
                p = geom.interpolate(d)
                pts.append((p.x, p.y))
    if not pts:
        raise ValueError("no line features inside the admin boundary")
    return np.asarray(pts)


def nearest_km(xy: np.ndarray, line_xy: np.ndarray) -> np.ndarray:
    d, _ = cKDTree(line_xy).query(xy)
    return d / 1000.0


def distances_km(df: pd.DataFrame, layers, admin: gpd.GeoDataFrame, crs: str) -> np.ndarray:
    pts = gpd.GeoSeries(gpd.points_from_xy(df["X_deg"], df["Y_deg"]), crs="EPSG:4326").to_crs(crs)
    return nearest_km(np.c_[pts.x.to_numpy(), pts.y.to_numpy()], line_points(layers, admin, crs))


def apply_zero_rule(new_d: np.ndarray, old_col: np.ndarray, old_centroid_d: np.ndarray,
                    tol_km: float = ZERO_TOL_KM) -> np.ndarray:
    """Keep the extraction's zero (settlement polygon crossed a line) where the crossing line is
    still the nearest one, that is where the new distance equals the old centroid distance."""
    out = np.asarray(new_d, dtype=float).copy()
    keep = (np.asarray(old_col) == 0) & (np.abs(out - np.asarray(old_centroid_d)) <= tol_km)
    out[keep] = 0.0
    return out


def _layer_info(specs, admin, crs):
    info = []
    for spec in specs:
        path = spec.partition("|")[0]
        g = read_layer(spec)
        clipped = gpd.clip(g.to_crs("EPSG:4326"), admin.to_crs("EPSG:4326")).to_crs(crs)
        info.append({"spec": spec, "path": str(path), "sha256": _sha256(path), "features": int(len(g)),
                     "length_km": round(float(g.to_crs(crs).length.sum() / 1000), 1),
                     "length_inside_admin_km": round(float(clipped.length.sum() / 1000), 1),
                     "crs": str(g.crs)})
    return info


def _stats(values: np.ndarray) -> dict:
    v = np.asarray(values, dtype=float)
    return {"mean_km": round(float(v.mean()), 3), "median_km": round(float(np.median(v)), 3),
            "max_km": round(float(v.max()), 3), "zero_rows": int((v == 0).sum()),
            "within_5_km": int((v < 5).sum()), "within_10_km": int((v < 10).sum())}


def recompute(csv_in, csv_out, existing, planned, admin, old_layers=None, crs="EPSG:32628", note="",
              log=print) -> dict:
    csv_in, csv_out = Path(csv_in), Path(csv_out)
    adm = gpd.read_file(admin)
    df = pd.read_csv(csv_in, low_memory=False)
    layers = {"existing": [read_layer(s) for s in existing], "planned": [read_layer(s) for s in planned]}
    old_centroid = None
    if old_layers:
        old_centroid = distances_km(df, [read_layer(s) for s in old_layers], adm, crs)
    before = {c: df[c].to_numpy(dtype=float).copy() for c in COLUMNS.values() if c in df}
    for role, col in COLUMNS.items():
        d = distances_km(df, layers[role], adm, crs)
        if old_centroid is not None and col in before:
            d = apply_zero_rule(d, before[col], old_centroid)
        df[col] = d
        log(f"{col}: mean {d.mean():.2f} km, zero rows {(d == 0).sum()}, within 5 km {(d < 5).sum()}")
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_out, index=False)
    side = {
        "tool": "tools/hv_distances.py", "written": datetime.now().isoformat(timespec="seconds"),
        "input_csv": str(csv_in), "input_sha256": _sha256(csv_in), "output_csv": str(csv_out),
        "output_sha256": _sha256(csv_out), "crs": crs, "step_m": STEP_M, "note": note,
        "admin": {"path": str(admin), "sha256": _sha256(admin)},
        "existing": _layer_info(existing, adm, crs), "planned": _layer_info(planned, adm, crs),
        "old_layers_for_zero_rule": _layer_info(old_layers, adm, crs) if old_layers else [],
        "rows": int(len(df)),
        "stats": {col: _stats(df[col].to_numpy()) for col in COLUMNS.values()},
        "stats_before": {col: _stats(v) for col, v in before.items()},
    }
    csv_out.with_suffix(".hv_distances.json").write_text(json.dumps(side, indent=1), encoding="utf-8")
    return side


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv_in"); ap.add_argument("csv_out")
    ap.add_argument("--admin", required=True)
    ap.add_argument("--existing", action="append", required=True, help="existing HV layer spec (repeatable)")
    ap.add_argument("--planned", action="append", required=True, help="planned HV layer spec (repeatable)")
    ap.add_argument("--old", action="append", default=None, help="layers of the previous extraction, for the zero rule")
    ap.add_argument("--crs", default="EPSG:32628")
    ap.add_argument("--note", default="")
    a = ap.parse_args(argv)
    side = recompute(a.csv_in, a.csv_out, a.existing, a.planned, a.admin, a.old, a.crs, a.note)
    print(json.dumps(side["stats"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
