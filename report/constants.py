"""Codes, labels, colours, orders and column lists shared by the report package."""

# GEP-OnSSET FinalElecCode -> (key, label, colour, category). Okabe-Ito, colour-blind safe.
TECH = {
    1: ("Grid_dens", "Grid densification", "#0072B2", "Grid"),
    2: ("Grid_ext", "Grid extension", "#56B4E9", "Grid"),
    3: ("SA_PV", "Stand-alone PV", "#E69F00", "Stand-alone"),
    5: ("MG_PV_Battery", "Mini-grid PV with battery", "#009E73", "Mini-grid"),
    7: ("MG_Hydro", "Mini-grid hydro", "#CC79A7", "Mini-grid"),
    99: ("Non-electrified", "Not yet electrified", "#BBBBBB", "Unserved"),
}
TECH_ORDER = [1, 2, 5, 7, 3, 99]                 # stacking order: grid, mini-grids, stand-alone, none
SERVED_CODES = [1, 2, 3, 5, 7]
GRID_CODES = [1, 2]
OFFGRID_CODES = [3, 5, 7]
TECH_KEY = {code: v[0] for code, v in TECH.items()}
TECH_LABEL = {code: v[1] for code, v in TECH.items()}
TECH_COLOUR = {code: v[2] for code, v in TECH.items()}
TECH_CATEGORY = {code: v[3] for code, v in TECH.items()}
KEY_TO_CODE = {v[0]: code for code, v in TECH.items()}
CATEGORY_COLOURS = {"Grid": "#0072B2", "Mini-grid": "#009E73", "Stand-alone": "#E69F00", "Unserved": "#BBBBBB"}

# Demand cases: (demand_case, study name, description, line colour), display order.
DEMAND_CASES = [
    ("TD_Low_minus", "U3R1", "Top-down low (urban tier 3, rural tier 1)", "#9ECAE1"),
    ("TD_Low", "U3R2", "Top-down low, higher rural tier (urban tier 3, rural tier 2)", "#4292C6"),
    ("TD_High_minus", "U4R2", "Top-down high (urban tier 4, rural tier 2)", "#2171B5"),
    ("TD_High", "U4R3", "Top-down high, higher rural tier (urban tier 4, rural tier 3)", "#08519C"),
    ("TD_High_plus", "U5R3", "Top-down high, higher urban tier (urban tier 5, rural tier 3)", "#08306B"),
    ("BU", "BU", "Bottom-up demand from GDP-PPP and poverty (custom tier)", "#D55E00"),
]
CASE_ORDER = [c[0] for c in DEMAND_CASES]
KEY_CASES = ["TD_Low_minus", "TD_High_minus", "BU"]      # the three scenarios agreed with the team (U3R1, U4R2, BU)
DRE_CODES = [3, 5, 7]                                     # decentralised renewable energy technologies
CASE_STUDY_NAME = {c[0]: c[1] for c in DEMAND_CASES}
CASE_DESCRIPTION = {c[0]: c[2] for c in DEMAND_CASES}
CASE_COLOUR = {c[0]: c[3] for c in DEMAND_CASES}

COST_LEVELS = [0.047, 0.078, 0.085, 0.1, 0.22]
REFERENCE_COST = 0.1                                      # baseline of the extended sensitivity (sweep, bins, other demand cases)
COST_ROLE = {0.047: "legacy", 0.078: "low variant", 0.085: "hydro cost regime", 0.1: "current tariff regime (reference of the sweep)",
             0.22: "cost-reflective regime"}

# Grid-cost regimes of the final scenario set (team decision 2026-10-25): (cost, key, name, source).
REGIMES = [
    (0.22, "cost_reflective", "Cost-reflective",
     "0.22 USD/kWh, the cost-reflective grid generation cost of the Mission 300 compact, without subsidy"),
    (0.085, "hydro_cost", "Hydro cost",
     "0.085 USD/kWh, the generation cost of a hydro-dominant supply, a subsidised regime"),
    (0.1, "current_tariff", "Current tariff",
     "0.1 USD/kWh, the current subsidised tariff-based level, the reference of the earlier runs"),
]
REGIME_ORDER = [r[0] for r in REGIMES]
PRIMARY_COST = 0.22                                       # the regime behind the maps, the phasing chapter and the KPI tiles
REGIME_KEY = {r[0]: r[1] for r in REGIMES}
REGIME_NAME = {r[0]: r[2] for r in REGIMES}
REGIME_SOURCE = {r[0]: r[3] for r in REGIMES}
SENSITIVITY_CASES = ["TD_Low_minus", "TD_High_minus", "BU"]       # the key cases carry the cost sweep and the variants
CORE_CELLS = [(case, cost) for case in KEY_CASES for cost in REGIME_ORDER]      # the nine core scenarios, display order


def core_label(case: str, cost: float) -> str:
    """Display label of a core scenario: study name and regime name, for example 'BU, Cost-reflective'."""
    return f"{CASE_STUDY_NAME.get(case, case)}, {REGIME_NAME.get(cost, f'{cost} USD/kWh')}"


DEMAND_VARIANTS = [("TD_Low", "TD_Low_minus"), ("TD_High", "TD_High_minus"), ("TD_High_plus", "TD_High")]   # (variant, base)
YEARS = (2030, 2040)
START_YEAR = 2025

# Columns read from <id>_Results.csv (usecols); everything the report needs and nothing else.
RESULT_COLUMNS = [
    "id", "X_deg", "Y_deg", "Admin_1", "Admin_2", "IsUrban", "ElecStart", "NumPeoplePerHH",
    "PopStartYear", "Pop2030", "Pop2040",
    "NewConnections2030", "NewConnections2040", "NewCapacity2030", "NewCapacity2040",
    "InvestmentCost2030", "InvestmentCost2040", "FinalElecCode2030", "FinalElecCode2040",
    "MinimumOverallLCOE2030", "MinimumOverallLCOE2040",
    "Grid2040", "SA_PV2040", "MG_PV_Hybrid2040", "MG_Hydro2040",
    "EnergyPerSettlement2030", "EnergyPerSettlement2040",
    "Hydropower", "HydropowerDist", "HydropowerFID",
    "CurrentHVLineDist", "PlannedHVLineDist", "TravelHours",
]
INT8_COLUMNS = ["IsUrban", "ElecStart", "FinalElecCode2030", "FinalElecCode2040"]
CATEGORY_COLUMNS = ["Admin_1", "Admin_2"]
NOT_ASSIGNED = "Not assigned"          # replaces Admin_1 == "Unknown"
CACHE_SCHEMA_VERSION = 1

SUMMARY_INDEX = ["Grid_dens", "Grid_ext", "SA_PV", "MG_PV_Battery", "MG_Hydro", "Non-electrified", "Total"]

CHAPTERS = [
    ("key-messages", "1. Key messages"),
    ("scope", "2. Scope, scenarios, data and caveats"),
    ("access-today", "3. Energy access today and the un-served"),
    ("reference", "4. Least-cost options for the final scenario set"),
    ("metrics", "5. The three study metrics"),
    ("hydro", "6. Hydro mini-grids"),
    ("roadmap", "7. Phased roadmap 2030 and 2040"),
    ("corridor", "8. Koukoutamba corridor and protected areas"),
    ("sensitivity", "9. Sensitivity: regimes, supply-side variants and the extended sweep"),
    ("limits", "10. What the model does and does not say"),
    ("annex", "11. Annex"),
]

DISCLAIMER = ("Boundaries and names shown on this map do not imply any opinion on the part of the "
              "authors concerning the legal status of any territory or the delimitation of its frontiers.")
ACCENT = "#0072B2"
LAT_CENTER = 10.5                       # Guinea, for the scale bar's km per degree
