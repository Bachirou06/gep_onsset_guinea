"""Scenario control file: load, validate and resolve.

The control file (Scenarios/guinea_scenarios.json) declares every lever of every
scenario of the study. Keys use the variable names of GEP_Generator.ipynb so a
reader can map the file to the notebook cell by cell. This module has no
dependency on the model; it only reads and checks the file.

Blocks:
  meta         free text about the study and the hard-coded rules
  paths        input and output locations, relative to the repository root
  calibration  levers of the calibration step (one calibration per control file)
  defaults     every scenario lever, flat key/value
  scenarios    list of {id, demand_case, label, overrides, legacy_name?}
"""
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


class ControlError(ValueError):
    """Raised for any problem found in a control file."""


SCENARIO_KEYS = frozenset({
    "start_year", "end_year", "intermediate_year",
    "electrification_rate_target", "intermediate_electrification_target",
    "urban_target_tier", "rural_target_tier",
    "num_people_per_hh_urban", "num_people_per_hh_rural",
    "prioritization", "auto_intensification",
    "annual_new_grid_connections_limit_intermediate", "annual_new_grid_connections_limit_end",
    "annual_grid_cap_gen_limit_intermediate", "annual_grid_cap_gen_limit_end",
    "grid_generation_cost", "grid_power_plants_capital_cost", "grid_losses",
    "existing_grid_cost_ratio", "pv_adjustment_factor", "discount_rate", "pop_threshold",
    "diesel_price", "diesel_techs", "tech_switches",
    "sa_diesel_capital_cost", "mg_diesel_capital_cost", "mg_pv_capital_cost",
    "mg_wind_capital_cost", "mg_hydro_capital_cost",
    "sa_pv_capital_cost_1", "sa_pv_capital_cost_2", "sa_pv_capital_cost_3",
    "sa_pv_capital_cost_4", "sa_pv_capital_cost_5",
    "hv_line_capacity", "hv_line_cost", "mv_line_cost", "mv_line_capacity",
    "mv_line_max_length", "mv_increase_rate", "max_mv_line_dist", "MV_line_amperage_limit",
    "lv_line_capacity", "lv_line_max_length", "lv_line_cost",
    "service_Transf_type", "service_Transf_cost", "max_nodes_per_serv_trans",
    "hv_lv_transformer_cost", "hv_mv_transformer_cost", "mv_lv_transformer_cost",
    "mv_mv_transformer_cost",
    "tier_1", "tier_2", "tier_3", "tier_4", "tier_5",
    "productive_demand", "productive_preference", "cost_choice",
    "mg_pv_hybrid_cost_factor",     # multiplies the PV panel cost inside the PV-battery mini-grid (notebook literal 1)
})
POSITIVE_KEYS = frozenset({"mg_pv_hybrid_cost_factor", "pv_adjustment_factor"})

CALIBRATION_KEYS = frozenset({
    "pop_start_year", "end_year_pop", "urban_ratio_start_year", "urban_ratio_end_year",
    "elec_ratio_start_year", "urban_elec_ratio", "rural_elec_ratio",
    "min_night_lights", "min_pop", "max_service_transformer_distance",
    "max_mv_line_distance", "max_hv_line_distance",
})

NOT_OVERRIDABLE = frozenset({"start_year", "intermediate_year", "end_year"})

PATH_KEYS = ("raw_input_csv", "calibrated_csv", "pv_profile", "wind_profile",
             "productive_matrix", "output_root")
PATHS_NOT_REQUIRED_TO_EXIST = frozenset({"output_root", "calibrated_csv"})

COST_DICT_KEYS = frozenset({
    "sa_diesel_capital_cost", "mg_diesel_capital_cost", "mg_pv_capital_cost",
    "mg_wind_capital_cost", "mg_hydro_capital_cost",
})

TECH_SWITCH_KEYS = frozenset({"sa_pv", "mg_hydro", "mg_pv", "mg_pv_hybrid", "mg_wind_hybrid"})

TOP_LEVEL_BLOCKS = ("meta", "paths", "calibration", "defaults", "scenarios")

ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")

# Keys that the notebook's model calls never read; recorded in the Variables file only.
# prioritization is hard-coded to 5 in the three model calls (cell 53), so any other
# value is refused rather than silently ignored.
RECORDED_ONLY_KEYS = frozenset({"existing_grid_cost_ratio", "mv_increase_rate", "max_mv_line_dist"})

INT_KEYS = frozenset({
    "start_year", "end_year", "intermediate_year", "urban_target_tier", "rural_target_tier",
    "prioritization", "cost_choice", "productive_demand", "diesel_techs",
})
TIER_KEYS = frozenset({"urban_target_tier", "rural_target_tier"})
FLAG_KEYS = frozenset({"productive_demand", "diesel_techs"})
STRING_KEYS = frozenset({"productive_preference"})
PREFERENCES = ("Low", "Medium", "High")
NUMBER_KEYS = SCENARIO_KEYS - INT_KEYS - STRING_KEYS - COST_DICT_KEYS - {"tech_switches"}


def _check_value(key: str, value):
    """Type and range rules for one scenario lever; raise ControlError on a violation."""
    if key in STRING_KEYS:
        if not isinstance(value, str):
            raise ControlError(f"'{key}' must be a string, got {value!r}")
        if key == "productive_preference" and value not in PREFERENCES:
            raise ControlError(f"'{key}' must be one of Low, Medium or High, got {value!r}")
        return
    if key in INT_KEYS:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ControlError(f"'{key}' must be an integer, got {value!r}")
        if key in TIER_KEYS and not 1 <= value <= 6:
            raise ControlError(f"'{key}' must be between 1 and 6, got {value!r}")
        if key in FLAG_KEYS and value not in (0, 1):
            raise ControlError(f"'{key}' must be 0 or 1, got {value!r}")
        if key == "cost_choice" and value not in (1, 2):
            raise ControlError(f"'{key}' must be 1 or 2, got {value!r}")
        if key == "prioritization" and value != 5:
            raise ControlError(f"'{key}' must be 5: the notebook hard-codes 5 (nationwide least cost) "
                               "in its model calls, so another value would be silently ignored")
        return
    if key in NUMBER_KEYS:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ControlError(f"'{key}' must be a number, got {value!r}")
        if key in POSITIVE_KEYS and value <= 0:
            raise ControlError(f"'{key}' must be positive, got {value!r}")


@dataclass
class Scenario:
    id: str
    demand_case: str
    label: str
    overrides: dict
    legacy_name: str | None = None
    variant: str = "reference"      # supply-side variant of the demand case (reference, optgrid, ...)


@dataclass
class Control:
    path: Path
    repo_root: Path
    meta: dict
    paths: dict
    calibration: dict
    defaults: dict
    scenarios: list
    sha256: str
    _by_id: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self._by_id = {s.id: s for s in self.scenarios}

    def ids(self) -> list:
        return [s.id for s in self.scenarios]

    def scenario(self, scenario_id: str) -> Scenario:
        try:
            return self._by_id[scenario_id]
        except KeyError:
            raise ControlError(f"unknown scenario id '{scenario_id}'; "
                               f"valid ids: {', '.join(self.ids())}") from None

    def resolved(self, scenario_id: str) -> dict:
        params = dict(self.defaults)
        params.update(self.scenario(scenario_id).overrides)
        return params


def _convert_cost_dict(key: str, value) -> dict:
    if not isinstance(value, dict) or "inf" not in value or len(value) != 1:
        raise ControlError(f"'{key}' must be an object with key 'inf', for example {{\"inf\": 2950}}")
    return {float("inf"): float(value["inf"])}


def _check_keys(block: dict, allowed: frozenset, block_name: str, required: bool):
    for k in block:
        if k not in allowed:
            raise ControlError(f"unknown key '{k}' in '{block_name}'")
    if required:
        for k in sorted(allowed):
            if k not in block:
                raise ControlError(f"missing key '{k}' in '{block_name}'")


def _check_tech_switches(value):
    if not isinstance(value, dict) or set(value) != TECH_SWITCH_KEYS \
            or any(v not in (0, 1) for v in value.values()):
        raise ControlError("tech_switches must be an object with exactly the keys "
                           f"{sorted(TECH_SWITCH_KEYS)} and values 0 or 1")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_control(path, repo_root=None, check_paths: bool = True) -> Control:
    """Read, validate and resolve a control file.

    repo_root defaults to the parent of the folder holding the control file
    (Scenarios/guinea_scenarios.json -> the repository root). With check_paths,
    every path except output_root and calibrated_csv must exist.
    """
    path = Path(path).resolve()
    repo_root = Path(repo_root).resolve() if repo_root is not None else path.parent.parent
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ControlError(f"{path.name} is not valid JSON: {e}") from None

    for block in TOP_LEVEL_BLOCKS:
        if block not in doc:
            raise ControlError(f"missing top-level block '{block}'")
    for k in doc:
        if k not in TOP_LEVEL_BLOCKS:
            raise ControlError(f"unknown top-level block '{k}'")

    defaults = dict(doc["defaults"])
    _check_keys(defaults, SCENARIO_KEYS, "defaults", required=True)
    calibration = dict(doc["calibration"])
    _check_keys(calibration, CALIBRATION_KEYS, "calibration", required=True)
    _check_tech_switches(defaults["tech_switches"])
    for k, v in defaults.items():
        _check_value(k, v)
    for k, v in calibration.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ControlError(f"'{k}' in 'calibration' must be a number, got {v!r}")
    for k in COST_DICT_KEYS:
        defaults[k] = _convert_cost_dict(k, defaults[k])

    paths = {}
    for k in PATH_KEYS:
        if k not in doc["paths"]:
            raise ControlError(f"missing path '{k}' in 'paths'")
        p = Path(doc["paths"][k])
        paths[k] = p if p.is_absolute() else (repo_root / p)
    for k in doc["paths"]:
        if k not in PATH_KEYS:
            raise ControlError(f"unknown path '{k}' in 'paths'")
    if check_paths:
        for k, p in paths.items():
            if k not in PATHS_NOT_REQUIRED_TO_EXIST and not p.exists():
                raise ControlError(f"path '{k}' does not exist: {p}")

    scenarios = []
    seen = set()
    for raw in doc["scenarios"]:
        for req in ("id", "demand_case", "label", "overrides"):
            if req not in raw:
                raise ControlError(f"scenario entry without '{req}': {raw}")
        sid = raw["id"]
        if not ID_PATTERN.match(sid):
            raise ControlError(f"scenario id '{sid}' is not filename-safe "
                               "(letters, digits, '_', '.' and '-' only)")
        if sid in seen:
            raise ControlError(f"duplicate scenario id '{sid}'")
        seen.add(sid)
        overrides = dict(raw["overrides"])
        for k in overrides:
            if k in CALIBRATION_KEYS:
                raise ControlError(f"scenario '{sid}' overrides calibration-stage key '{k}'; "
                                   "a different calibration is a different control file")
            if k in NOT_OVERRIDABLE:
                raise ControlError(f"scenario '{sid}': '{k}' cannot be overridden per scenario")
            if k not in SCENARIO_KEYS:
                raise ControlError(f"scenario '{sid}' overrides unknown key '{k}'")
            if k in COST_DICT_KEYS:
                overrides[k] = _convert_cost_dict(k, overrides[k])
            elif k == "tech_switches":
                _check_tech_switches(overrides[k])
            else:
                _check_value(k, overrides[k])
        variant = raw.get("variant", "reference")
        if not isinstance(variant, str) or not ID_PATTERN.match(variant):
            raise ControlError(f"scenario '{sid}': variant must be a filename-safe string, got {variant!r}")
        scenarios.append(Scenario(id=sid, demand_case=raw["demand_case"], label=raw["label"],
                                  overrides=overrides, legacy_name=raw.get("legacy_name"), variant=variant))

    return Control(path=path, repo_root=repo_root, meta=dict(doc["meta"]), paths=paths,
                   calibration=calibration, defaults=defaults, scenarios=scenarios,
                   sha256=_sha256_file(path))
