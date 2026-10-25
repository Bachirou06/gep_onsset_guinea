"""GIS layers and per-settlement geographic attributes (corridor distance, protected
areas, affected localities). geopandas is imported lazily; HAS_GEO says whether it
is available. Distances are computed in EPSG:32629 (UTM 29N), which covers Guinea
with a scale error below 0.6 percent at the western border."""
import glob
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import geopandas as gpd
    HAS_GEO = True
except ImportError:          # pragma: no cover
    gpd = None
    HAS_GEO = False

UTM = "EPSG:32629"
WGS84 = "EPSG:4326"
KKT_MAIN_NAME = "Manantali"      # the Linsan to Manantali feature of HV_KKT.shp

LAYER_FILES = {
    "adm0": "Boundaries/gadm41_GIN_0.shp",
    "adm1": "Boundaries/gadm41_GIN_1.shp",
    "hv_existing": "HV_Existing_lines/HT_existing_line.shp",
    "kkt": "HV_KKT/HV_KKT.shp",
    "protected": "Protected_Area_Guinea/Guinea_protected_Area_polygon.gpkg",
    "moyen_bafing": "Protected_Area_Guinea/Park_Moyen Bafing_guinea.gpkg",
    "affected_localities": "Protected_Area_Guinea/Localit*_affected_BR.gpkg",
    "protected_span_hv": "Protected_Area_Guinea/Protected_Area_Span_HT_line.gpkg",
    "mini_hydro": "Hydro_potential/Guinea_mini_hydro.gpkg",
    "substations": "Substations/Substations.shp",
}
OPTIONAL_LAYERS = {"mini_hydro", "substations", "hv_existing", "protected_span_hv"}

GEO_COLUMNS = ["id", "kkt_main_dist_km", "kkt_any_dist_km", "in_protected_area", "protected_area_name",
               "in_moyen_bafing", "affected_locality", "in_protected_span_hv", "region_gadm"]


def _resolve(inputs_dir: Path, pattern: str) -> Path | None:
    hits = sorted(glob.glob(str(Path(inputs_dir) / pattern)))
    return Path(hits[0]) if hits else None


def load_layers(inputs_dir) -> dict:
    """Every layer the report draws or joins, all in WGS84. Optional layers may be absent."""
    if not HAS_GEO:
        raise ImportError("geopandas is required for report.geo")
    inputs_dir = Path(inputs_dir)
    layers = {}
    for key, pattern in LAYER_FILES.items():
        p = _resolve(inputs_dir, pattern)
        if p is None:
            if key in OPTIONAL_LAYERS:
                continue
            raise FileNotFoundError(f"GIS layer '{key}' not found under {inputs_dir} ({pattern})")
        g = gpd.read_file(p)
        if g.crs is None:
            g = g.set_crs(WGS84)
        elif g.crs.to_epsg() != 4326:
            g = g.to_crs(WGS84)
        layers[key] = g
    kkt = layers["kkt"]
    main = kkt[kkt["Name"].astype(str).str.contains(KKT_MAIN_NAME, case=False, na=False)]
    layers["kkt_main"] = main if len(main) else kkt.iloc[[0]]
    return layers


def _layer_signature(inputs_dir: Path) -> dict:
    sig = {}
    for key, pattern in LAYER_FILES.items():
        p = _resolve(inputs_dir, pattern)
        if p is not None:
            st = p.stat()
            sig[key] = [p.name, st.st_size, st.st_mtime_ns]
    return sig


def _ids_hash(ids) -> str:
    return hashlib.sha256(np.asarray(ids, dtype=np.int64).tobytes()).hexdigest()


def settlement_geo_attributes(points: pd.DataFrame, layers: dict, cache_dir, radii_km=(5, 10, 25),
                              inputs_dir=None, log=None) -> pd.DataFrame:
    """Per settlement: distance (km) to the Linsan to Manantali line and to any
    Koukoutamba line feature, protected-area membership and name, Moyen-Bafing park,
    affected locality name, membership of a protected area crossed by the HV line, and
    the GADM region. Cached as parquet with a sidecar of the inputs' signature."""
    cache_dir = Path(cache_dir)
    parquet = cache_dir / "geo_attributes.parquet"
    sidecar = cache_dir / "geo_attributes.cache.json"
    key = {"n": int(len(points)), "ids": _ids_hash(points["id"].to_numpy()), "radii": list(radii_km),
           "layers": _layer_signature(Path(inputs_dir)) if inputs_dir else {k: len(v) for k, v in layers.items()},
           "schema": 1}
    if parquet.exists() and sidecar.exists():
        try:
            if json.loads(sidecar.read_text(encoding="utf-8")) == key:
                return pd.read_parquet(parquet)
        except (json.JSONDecodeError, OSError, ValueError):
            pass

    pts = gpd.GeoDataFrame(points[["id"]].copy(),
                           geometry=gpd.points_from_xy(points["X_deg"], points["Y_deg"]), crs=WGS84).to_crs(UTM)
    kkt_main = layers["kkt_main"].to_crs(UTM).geometry.union_all()
    kkt_any = layers["kkt"].to_crs(UTM).geometry.union_all()
    out = pd.DataFrame({"id": points["id"].to_numpy()})
    out["kkt_main_dist_km"] = pts.geometry.distance(kkt_main).to_numpy() / 1000.0
    out["kkt_any_dist_km"] = pts.geometry.distance(kkt_any).to_numpy() / 1000.0

    def within_name(layer_key, name_col):
        if layer_key not in layers:
            return pd.Series([None] * len(pts), index=pts.index, dtype=object)
        poly = layers[layer_key].to_crs(UTM)[[name_col, "geometry"]].rename(columns={name_col: "_name"})
        j = gpd.sjoin(pts[["geometry"]], poly, how="left", predicate="within")
        j = j[~j.index.duplicated(keep="first")]
        return j["_name"].reindex(pts.index)

    prot = within_name("protected", "name")
    out["in_protected_area"] = prot.notna().to_numpy()
    out["protected_area_name"] = prot.fillna("").astype(str).to_numpy()
    out["in_moyen_bafing"] = within_name("moyen_bafing", "name").notna().to_numpy()
    out["affected_locality"] = within_name("affected_localities", "shapeName").fillna("").astype(str).to_numpy()
    out["in_protected_span_hv"] = within_name("protected_span_hv", "name").notna().to_numpy()
    out["region_gadm"] = within_name("adm1", "NAME_1").fillna("").astype(str).to_numpy()
    out = out[GEO_COLUMNS]

    cache_dir.mkdir(parents=True, exist_ok=True)
    out.to_parquet(parquet, index=False)
    sidecar.write_text(json.dumps(key, indent=1), encoding="utf-8")
    if log:
        log(f"geo attributes computed for {len(out)} settlements")
    return out
