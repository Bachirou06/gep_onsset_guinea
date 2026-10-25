"""Scenario runner: the scenario cells of GEP_Generator.ipynb as functions.

Every function here is a cell of the notebook (commit fff30bd) with its globals
turned into parameters. The model itself (onsset.py, hybrids_pv.py,
hybrids_wind.py, guinea_demand_customization.py) is called exactly as the
notebook calls it. Nothing numeric is changed.

Cell map:
  32      TECH_CONSTANTS, build_technologies
  53      Technology.set_default_values (inside build_technologies), scenario loop
  55      summary_table
  62      variables_table (notebook rows, then the hidden levers)
"""
import json
from pathlib import Path

import pandas as pd

from onsset import *  # noqa: F401,F403  (SET_* constants, Technology, SettlementProcessor)
from scenario_control import _sha256_file as sha256_file

# ---------------------------------------------------------------------------
# Cell 32: every literal that is not a control-file key, kept in one place so
# the manifest can record them.
# ---------------------------------------------------------------------------
TECH_CONSTANTS = {
    "grid": {"om_of_td_lines": 0.02, "connection_cost_per_hh": 125, "base_to_peak_load_ratio": 0.8,
             "capacity_factor": 1, "tech_life": 30, "grid_penalty_ratio": 1},
    "mg_pv_hybrid": {"om_of_td_lines": 0.02, "distribution_losses": 0.05, "connection_cost_per_hh": 100,
                     "capacity_factor": 0.5, "tech_life": 20},
    "mg_wind_hybrid": {"om_of_td_lines": 0.02, "distribution_losses": 0.05, "connection_cost_per_hh": 100,
                       "capacity_factor": 0.5, "tech_life": 20},
    "mg_hydro": {"om_of_td_lines": 0.02, "distribution_losses": 0.05, "connection_cost_per_hh": 100,
                 "base_to_peak_load_ratio": 0.85, "capacity_factor": 0.5, "tech_life": 30, "om_costs": 0.02},
    "mg_wind": {"om_of_td_lines": 0.02, "distribution_losses": 0.05, "connection_cost_per_hh": 100,
                "base_to_peak_load_ratio": 0.85, "om_costs": 0.02, "tech_life": 20},
    "mg_pv": {"om_of_td_lines": 0.02, "distribution_losses": 0.05, "connection_cost_per_hh": 100,
              "base_to_peak_load_ratio": 0.85, "tech_life": 20, "om_costs": 0.015},
    "sa_pv": {"base_to_peak_load_ratio": 0.9, "tech_life": 15, "om_costs": 0.02,
              "capital_cost_bins": [0.020, 0.050, 0.100, 1, 5]},
    "mg_diesel": {"om_of_td_lines": 0.03, "distribution_losses": 0.05, "connection_cost_per_hh": 100,
                  "base_to_peak_load_ratio": 0.85, "capacity_factor": 0.7, "tech_life": 15,
                  "om_costs": 0.1, "efficiency": 0.33, "diesel_truck_consumption": 33.7,
                  "diesel_truck_volume": 15000},
    "sa_diesel": {"base_to_peak_load_ratio": 0.9, "capacity_factor": 0.7, "tech_life": 10,
                  "om_costs": 0.1, "efficiency": 0.28, "diesel_truck_consumption": 14,
                  "diesel_truck_volume": 300},
    "sa_diesel_cost": {"efficiency": 0.28, "diesel_truck_consumption": 14, "diesel_truck_volume": 300},
    "mg_diesel_cost": {"efficiency": 0.33, "diesel_truck_consumption": 14, "diesel_truck_volume": 300},
}

HYDRO_VIABILITY_KM = 10  # hard-coded as max_hydro_dist in onsset.py; recorded, not a lever
HYDRO_SITE_FILTER = "sites above 1 MW excluded upstream in the extraction (Hydropower column 0 to 1000 kW)"

SUMMARY_INDEX = ["Grid_dens", "Grid_ext", "SA_PV", "MG_PV_Battery", "MG_Hydro", "Non-electrified", "Total"]


def build_technologies(params: dict) -> dict:
    """Cells 28, 29, 32 and the set_default_values call of cell 53."""
    c = TECH_CONSTANTS
    diesel_price = params["diesel_price"]
    sa_diesel_cost = {"diesel_price": diesel_price, **c["sa_diesel_cost"]}
    mg_diesel_cost = {"diesel_price": diesel_price, **c["mg_diesel_cost"]}

    Technology.set_default_values(base_year=params["start_year"], start_year=params["start_year"],
                                  end_year=params["end_year"], discount_rate=params["discount_rate"],
                                  hv_line_type=params["hv_line_capacity"], hv_line_cost=params["hv_line_cost"],
                                  mv_line_type=params["mv_line_capacity"],
                                  mv_line_amperage_limit=params["MV_line_amperage_limit"],
                                  mv_line_cost=params["mv_line_cost"], lv_line_type=params["lv_line_capacity"],
                                  lv_line_cost=params["lv_line_cost"],
                                  lv_line_max_length=params["lv_line_max_length"],
                                  service_transf_type=params["service_Transf_type"],
                                  service_transf_cost=params["service_Transf_cost"],
                                  max_nodes_per_serv_trans=params["max_nodes_per_serv_trans"],
                                  mv_lv_sub_station_cost=params["mv_lv_transformer_cost"],
                                  mv_mv_sub_station_cost=params["mv_mv_transformer_cost"],
                                  hv_lv_sub_station_cost=params["hv_lv_transformer_cost"],
                                  hv_mv_sub_station_cost=params["hv_mv_transformer_cost"])

    grid_calc = Technology(om_of_td_lines=c["grid"]["om_of_td_lines"],
                           distribution_losses=params["grid_losses"],
                           connection_cost_per_hh=c["grid"]["connection_cost_per_hh"],
                           base_to_peak_load_ratio=c["grid"]["base_to_peak_load_ratio"],
                           capacity_factor=c["grid"]["capacity_factor"],
                           tech_life=c["grid"]["tech_life"],
                           grid_penalty_ratio=c["grid"]["grid_penalty_ratio"],
                           grid_capacity_investment=params["grid_power_plants_capital_cost"],
                           grid_price=params["grid_generation_cost"])

    mg_pv_hybrid_calc = Technology(**c["mg_pv_hybrid"], mini_grid=True, hybrid=True)
    mg_wind_hybrid_calc = Technology(**c["mg_wind_hybrid"], mini_grid=True, hybrid=True)
    mg_hydro_calc = Technology(**c["mg_hydro"], capital_cost=params["mg_hydro_capital_cost"])
    mg_wind_calc = Technology(**c["mg_wind"], capital_cost=params["mg_wind_capital_cost"])
    mg_pv_calc = Technology(**c["mg_pv"], capital_cost=params["mg_pv_capital_cost"])

    f = params["pv_adjustment_factor"]
    bins = c["sa_pv"]["capital_cost_bins"]
    sa_pv_calc = Technology(base_to_peak_load_ratio=c["sa_pv"]["base_to_peak_load_ratio"],
                            tech_life=c["sa_pv"]["tech_life"], om_costs=c["sa_pv"]["om_costs"],
                            capital_cost={bins[0]: params["sa_pv_capital_cost_1"] * f,
                                          bins[1]: params["sa_pv_capital_cost_2"] * f,
                                          bins[2]: params["sa_pv_capital_cost_3"] * f,
                                          bins[3]: params["sa_pv_capital_cost_4"] * f,
                                          bins[4]: params["sa_pv_capital_cost_5"] * f},
                            standalone=True)

    mg_diesel_calc = Technology(**c["mg_diesel"], capital_cost=params["mg_diesel_capital_cost"],
                                diesel_price=diesel_price)
    sa_diesel_calc = Technology(**c["sa_diesel"], capital_cost=params["sa_diesel_capital_cost"],
                                diesel_price=diesel_price, standalone=True)

    return {"grid": grid_calc, "mg_pv_hybrid": mg_pv_hybrid_calc, "mg_wind_hybrid": mg_wind_hybrid_calc,
            "mg_hydro": mg_hydro_calc, "mg_wind": mg_wind_calc, "mg_pv": mg_pv_calc, "sa_pv": sa_pv_calc,
            "mg_diesel": mg_diesel_calc, "sa_diesel": sa_diesel_calc,
            "sa_diesel_cost": sa_diesel_cost, "mg_diesel_cost": mg_diesel_cost}


def summary_table(df: pd.DataFrame, yearsofanalysis, cost_choice: int) -> pd.DataFrame:
    """Cell 55 verbatim, with onsseter.df as df."""
    techs = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "99"]

    sumtechs = []
    for year in yearsofanalysis:
        sumtechs.extend(["Population{}".format(year) + t for t in techs])
        sumtechs.extend(["NewConnections{}".format(year) + t for t in techs])
        sumtechs.extend(["Capacity{}".format(year) + t for t in techs])
        sumtechs.extend(["Investment{}".format(year) + t for t in techs])

    if cost_choice == 1:
        for year in yearsofanalysis:
            sumtechs.extend(["InvestmentCostLV{}".format(year) + t for t in techs])
            sumtechs.extend(["InvestmentCostMV{}".format(year) + t for t in techs])
            sumtechs.extend(["InvestmentCostHV{}".format(year) + t for t in techs])
            sumtechs.extend(["InvestmentCostTransformer{}".format(year) + t for t in techs])
            sumtechs.extend(["InvestmentCostConnection{}".format(year) + t for t in techs])
            sumtechs.extend(["CapitalCapacityInvestment{}".format(year) + t for t in techs])
            sumtechs.extend(["RecurringCosts{}".format(year) + t for t in techs])

    summary = pd.Series(index=sumtechs, name='country', dtype=float)

    if cost_choice == 1:
        for year in yearsofanalysis:
            for t in techs:
                sel = (df[SET_MIN_OVERALL + '{}'.format(year)] == t + '{}'.format(year)) & \
                      (df[SET_ELEC_FINAL_CODE + '{}'.format(year)] < 99)
                summary.loc["Population{}".format(year) + t] = df.loc[sel, SET_POP + '{}'.format(year)].sum()
                summary.loc["NewConnections{}".format(year) + t] = df.loc[sel, SET_NEW_CONNECTIONS + '{}'.format(year)].sum()
                summary.loc["Capacity{}".format(year) + t] = df.loc[sel, SET_NEW_CAPACITY + '{}'.format(year)].sum() / 1000
                summary.loc["Investment{}".format(year) + t] = df.loc[sel, SET_INVESTMENT_COST + '{}'.format(year)].sum()
                for label in ("InvestmentCostLV", "InvestmentCostMV", "InvestmentCostHV",
                              "InvestmentCostTransformer", "InvestmentCostConnection",
                              "CapitalCapacityInvestment", "RecurringCosts"):
                    summary.loc[label + "{}".format(year) + t] = df.loc[sel, label + '{}'.format(year)].sum()
    else:
        for year in yearsofanalysis:
            for t in techs:
                code = df[SET_ELEC_FINAL_CODE + '{}'.format(year)]
                summary.loc["Population{}".format(year) + t] = df.loc[code == int(t), SET_POP + '{}'.format(year)].sum()
                summary.loc["NewConnections{}".format(year) + t] = df.loc[code == int(t), SET_NEW_CONNECTIONS + '{}'.format(year)].sum()
                summary.loc["Capacity{}".format(year) + t] = df.loc[(code == int(t)) & (code < 99), SET_NEW_CAPACITY + '{}'.format(year)].sum() / 1000
                summary.loc["Investment{}".format(year) + t] = df.loc[(code == int(t)) & (code < 99), SET_INVESTMENT_COST + '{}'.format(year)].sum()

    summary = summary.fillna(0)

    index = techs + ['Total']
    columns = []
    if cost_choice == 1:
        for year in yearsofanalysis:
            columns += ["Population{}".format(year), "NewConnections{}".format(year),
                        "Capacity{} (MW)".format(year), "Investment{} (million USD)".format(year),
                        "InvestmentLV{} (million USD)".format(year), "InvestmentMV{} (million USD)".format(year),
                        "InvestmentHV{} (million USD)".format(year), "InvestmentTrans{} (million USD)".format(year),
                        "InvestmentCon{} (million USD)".format(year), "InvestmentCap{} (million USD)".format(year),
                        "RecurringCosts{} (million USD)".format(year)]
    else:
        for year in yearsofanalysis:
            columns += ["Population{}".format(year), "NewConnections{}".format(year),
                        "Capacity{} (MW)".format(year), "Investment{} (million USD)".format(year)]

    summary_table = pd.DataFrame(index=index, columns=columns)

    if cost_choice == 1:
        n = 7
        slices = [(0, "int"), (7, "int"), (14, "int"), (21, "musd"), (56, "musd"), (63, "musd"), (70, "musd"),
                  (77, "musd"), (84, "musd"), (91, "musd"), (98, "musd"),
                  (28, "int"), (35, "int"), (42, "int"), (49, "musd"), (105, "musd"), (112, "musd"),
                  (119, "musd"), (126, "musd"), (133, "musd"), (140, "musd"), (147, "musd")]
        for col, (start, kind) in zip(columns, slices):
            block = summary.iloc[start:start + n]
            if kind == "int":
                summary_table[col] = block.astype(int).tolist() + [int(block.sum())]
            else:
                summary_table[col] = [round(x / 1e4) / 1e2 for x in block.astype(float).tolist()] + [round(block.sum() / 1e4) / 1e2]
    else:
        summary_table[columns[0]] = summary.iloc[0:11].astype(int).tolist() + [int(summary.iloc[0:11].sum())]
        summary_table[columns[1]] = summary.iloc[11:22].astype(int).tolist() + [int(summary.iloc[11:22].sum())]
        summary_table[columns[2]] = [round(x, 2) for x in summary.iloc[22:33].astype(float).tolist()] + [round(summary.iloc[22:33].sum(), 2)]
        summary_table[columns[3]] = [round(x / 1e4) / 1e2 for x in summary.iloc[33:44].astype(float).tolist()] + [round(summary.iloc[33:44].sum() / 1e4) / 1e2]
        summary_table[columns[4]] = summary.iloc[44:55].astype(int).tolist() + [int(summary.iloc[44:55].sum())]
        summary_table[columns[5]] = summary.iloc[55:66].astype(int).tolist() + [int(summary.iloc[55:66].sum())]
        summary_table[columns[6]] = [round(x, 2) for x in summary.iloc[66:77].astype(float).tolist()] + [round(summary.iloc[66:77].sum(), 2)]
        summary_table[columns[7]] = [round(x / 1e4) / 1e2 for x in summary.iloc[77:88].astype(float).tolist()] + [round(summary.iloc[77:88].sum() / 1e4) / 1e2]

    # remove disabled technologies and the empty code-10 slot (original string codes)
    summary_table = summary_table.drop(['4', '6', '8', '9', '10'])
    map_dict = {'1': 'Grid_dens', '2': 'Grid_ext', '3': 'SA_PV', '5': 'MG_PV_Battery', '7': 'MG_Hydro',
                '99': 'Non-electrified', 'Total': 'Total'}
    summary_table.index = summary_table.index.to_series().map(map_dict)
    return summary_table


def variables_table(control, scenario, params: dict, technologies: dict, extra: dict) -> pd.DataFrame:
    """Cell 62 verbatim (same rows, same order), then the levers the notebook never exported."""
    cal = control.calibration
    p = params
    list1 = [('Start_year', p["start_year"], '', '', ''),
             ('End_year', p["end_year"], '', '', ''),
             ('End year electrification rate target', p["electrification_rate_target"], '', '', ''),
             ('Intermediate target year', p["intermediate_year"], '', '', ''),
             ('Intermediate electrification rate target', p["intermediate_electrification_target"], '', '', ''),
             ('PV cost adjustment factor', p["pv_adjustment_factor"], '', '', ''),
             ('Urban target tier', p["urban_target_tier"], '', '', ''),
             ('Rural target tier', p["rural_target_tier"], '', '', ''),
             ('Prioritization', p["prioritization"], '', '', '5 = least cost, 4 = forced grid within buffer only, 6 = forced grid within buffer & least cost out of the buffer zone'),
             ('Auto intensification distance', p["auto_intensification"], '', '', 'Buffer distance (km) for automatic intensification if choosing prioritization 1'),
             ('discount_rate', p["discount_rate"], '', '', ''),
             ('pop_threshold', p["pop_threshold"], '', '', ''),
             ('pop_start_year', cal["pop_start_year"], '', '', 'the population in the base year (e.g. 2018)'),
             ('pop_end_year', cal["end_year_pop"], '', '', 'the projected population in the end year (e.g. 2030)'),
             ('urban_ratio_start_year', cal["urban_ratio_start_year"], '', '', 'the urban population population ratio in the base year (e.g. 2018)'),
             ('urban_ratio_end_year', cal["urban_ratio_end_year"], '', '', 'the urban population population ratio in the end year (e.g. 2030)'),
             ('num_people_per_hh_urban', p["num_people_per_hh_urban"], '', '', 'the number of people per household expected in the end year (e.g. 2030)'),
             ('num_people_per_hh_rural', p["num_people_per_hh_rural"], '', '', 'the number of people per household expected in the end year (e.g. 2030)'),
             ('elec_ratio_start_year', cal["elec_ratio_start_year"], '', '', 'the electrification rate in the base year (e.g. 2018)'),
             ('urban_elec_ratio', cal["urban_elec_ratio"], '', '', 'urban electrification rate in the base year (e.g. 2018)'),
             ('rural_elec_ratio', cal["rural_elec_ratio"], '', '', 'rural electrification rate in the base year (e.g. 2018)'),
             ('grid_generation_cost', p["grid_generation_cost"], '', '', 'This is the grid cost electricity USD/kWh as expected in the end year of the analysis'),
             ('grid_power_plants_capital_cost', p["grid_power_plants_capital_cost"], '', '', 'The cost in USD/kW to for capacity upgrades of the grid-connected power plants'),
             ('grid_losses', p["grid_losses"], '', '', 'The fraction of electricity lost in transmission and distribution (percentage)'),
             ('base_to_peak', technologies["grid"].base_to_peak_load_ratio, '', '', 'The ratio of base grid demand to peak demand (percentage)'),
             ('existing_grid_cost_ratio', p["existing_grid_cost_ratio"], '', '', 'The additional cost per round of electrification (percentage)'),
             ('diesel_price', p["diesel_price"], '', '', 'This is the diesel price in USD/liter as expected in the end year of the analysis'),
             ('sa_diesel_capital_cost', p["sa_diesel_capital_cost"], '', '', 'Stand-alone Diesel capital cost (USD/kW) as expected in the years of the analysis'),
             ('mg_diesel_capital_cost', p["mg_diesel_capital_cost"], '', '', 'Mini-grid Diesel capital cost (USD/kW) as expected in the years of the analysis'),
             ('mg_pv_capital_cost', p["mg_pv_capital_cost"], '', '', 'Mini-grid PV capital cost (USD/kW) as expected in the years of the analysis'),
             ('mg_wind_capital_cost', p["mg_wind_capital_cost"], '', '', 'Mini-grid Wind capital cost (USD/kW) as expected in the years of the analysis'),
             ('mg_hydro_capital_cost', p["mg_hydro_capital_cost"], '', '', 'Mini-grid Hydro capital cost (USD/kW) as expected in the years of the analysis'),
             ('sa_pv_capital_cost_1', p["sa_pv_capital_cost_1"], '', '', 'Stand-alone PV capital cost (USD/kW) for household systems under 20 W'),
             ('sa_pv_capital_cost_2', p["sa_pv_capital_cost_2"], '', '', 'Stand-alone PV capital cost (USD/kW) for household systems between 21-50 W'),
             ('sa_pv_capital_cost_3', p["sa_pv_capital_cost_3"], '', '', 'Stand-alone PV capital cost (USD/kW) for household systems between 51-100 W'),
             ('sa_pv_capital_cost_4', p["sa_pv_capital_cost_4"], '', '', 'Stand-alone PV capital cost (USD/kW) for household systems between 101-200 W'),
             ('sa_pv_capital_cost_5', p["sa_pv_capital_cost_5"], '', '', 'Stand-alone PV capital cost (USD/kW) for household systems over 200 W'),
             ('mv_line_cost', p["mv_line_cost"], '', '', 'Cost of MV lines in USD/km'),
             ('lv_line_cost', p["lv_line_cost"], '', '', 'Cost of LV lines in USD/km'),
             ('mv_line_capacity', p["mv_line_capacity"], '', '', 'Capacity of MV lines in kW/line'),
             ('lv_line_capacity', p["lv_line_capacity"], '', '', 'Capacity of LV lines in kW/line'),
             ('lv_line_max_length', p["lv_line_max_length"], '', '', 'Maximum length of LV lines (km)'),
             ('hv_line_cost', p["hv_line_cost"], '', '', 'Cost of HV lines in USD/km'),
             ('mv_line_max_length', p["mv_line_max_length"], '', '', 'Maximum length of MV lines (km)'),
             ('hv_lv_transformer_cost', p["hv_lv_transformer_cost"], '', '', 'Cost of HV/MV transformer (USD/unit)'),
             ('mv_increase_rate', p["mv_increase_rate"], '', '', 'percentage'),
             ('max_grid_extension_dist', p["max_mv_line_dist"], '', '', 'Maximum distance that the grid may be extended by means of MV lines'),
             ('annual_new_grid_connections_limit_intermediate', p["annual_new_grid_connections_limit_intermediate"], '', '', 'This is the maximum amount of new households that can be connected to the grid in one year (thousands)'),
             ('annual_new_grid_connections_limit_end', p["annual_new_grid_connections_limit_end"], '', '', 'This is the maximum amount of new households that can be connected to the grid in one year (thousands)'),
             ('grid_capacity_limit_end', p["annual_grid_cap_gen_limit_end"], '', '', 'This is the maximum generation capacity that can be added to the grid in one year (MW)'),
             ('grid_capacity_limit_intermediate', p["annual_grid_cap_gen_limit_intermediate"], '', '', 'This is the maximum generation capacity that can be added to the grid in one year (MW)'),
             ('GIS data: Administrative boundaries', '', '', '', 'Delineates the boundaries of the analysis.'),
             ('GIS data: DEM', '', '', '', 'Filled DEM (elevation) maps are use in a number of processes in the analysis (Energy potentials, restriction zones, grid extension suitability map etc.).'),
             ('GIS data: Hydropower', '', '', '', 'Points showing potential mini/small hydropower potential.  Provides power availability in each identified point.'),
             ('GIS data: Land Cover', '', '', '', 'Land cover maps are use in a number of processes in the analysis (Energy potentials, restriction zones, grid extension suitability map etc.).'),
             ('GIS data: Night-time Lights', '', '', '', 'Dataset used to,identify and spatially calibrate the currently electrified/non-electrified population.'),
             ('GIS data: Population', '', '', '', 'Spatial identification and quantification of the current (base year) population. This dataset sets the basis of the ONSSET analysis as it is directly connected with the electricity demand and the assignment of energy access goals'),
             ('GIS data: Roads', '', '', '', 'Current road infrastructure is used in order to specify grid extension suitability.'),
             ('GIS data: Solar GHI', '', '', '', 'Provide information about the Global Horizontal Irradiation (kWh/m2/year) over an area. This is later used to identify the availability/suitability of Photovoltaic systems.'),
             ('GIS data: Substations', '', '', '', 'Current Substation infrastructure is used in order to specify grid extension suitability.'),
             ('GIS data: Existing grid', '', '', '', 'Current grid network'),
             ('GIS data: Planned grid', '', '', '', 'Planned/committed grid network extensions'),
             ('GIS data: Travel-time', '', '', '', 'Visualizes spatially the travel time required to reach from any individual cell to the closest town with population more than 50,000 people.'),
             ('GIS data: Wind velocity', '', '', '', 'Provide information about the wind velocity (m/sec) over an area. This is later used to identify the availability/suitability of wind power (using Capacity factors).'),
             ]
    hidden = [
        ('tech_switches', str(p["tech_switches"]), 'control file', '', 'Technologies allowed in the least-cost comparison (1 on, 0 off)'),
        ('diesel_techs', p["diesel_techs"], 'control file', '', 'Diesel technologies included (1) or not (0)'),
        ('productive_demand', p["productive_demand"], 'control file', '', '1 if productive and social demand is included'),
        ('productive_preference', p["productive_preference"], 'control file', '', 'Energy-intensity column of the productive-uses matrix (Low, Medium, High)'),
        ('tier_1', p["tier_1"], 'control file', '', 'MTF tier 1, kWh per household per year'),
        ('tier_2', p["tier_2"], 'control file', '', 'MTF tier 2, kWh per household per year'),
        ('tier_3', p["tier_3"], 'control file', '', 'MTF tier 3, kWh per household per year'),
        ('tier_4', p["tier_4"], 'control file', '', 'MTF tier 4, kWh per household per year'),
        ('tier_5', p["tier_5"], 'control file', '', 'MTF tier 5, kWh per household per year'),
        ('cost_choice', p["cost_choice"], 'control file', '', '2 = total investment only (1 is not available in this code version)'),
        ('min_night_lights', cal["min_night_lights"], 'calibration', '', 'Calibration threshold'),
        ('min_pop', cal["min_pop"], 'calibration', '', 'Calibration threshold'),
        ('max_service_transformer_distance', cal["max_service_transformer_distance"], 'calibration', '', 'Calibration threshold (km)'),
        ('max_mv_line_distance', cal["max_mv_line_distance"], 'calibration', '', 'Calibration threshold (km)'),
        ('max_hv_line_distance', cal["max_hv_line_distance"], 'calibration', '', 'Calibration threshold (km)'),
        ('hydro_viability_km', HYDRO_VIABILITY_KM, 'onsset.py', '', 'Hard-coded max_hydro_dist; not a lever'),
        ('hydro_site_filter', HYDRO_SITE_FILTER, 'extraction', '', 'Not a lever'),
        ('control_file', control.path.name, 'control file', '', ''),
        ('control_file_sha256', control.sha256, 'control file', '', ''),
        ('calibrated_csv_sha256', extra.get("calibrated_csv_sha256", ''), 'input', '', ''),
        ('scenario_id', scenario.id, 'control file', '', scenario.label),
        ('demand_case', scenario.demand_case, 'control file', '', ''),
        ('legacy_name', scenario.legacy_name or '', 'control file', '', 'Shared run with the same levers, if any'),
    ]
    labels = ['Variable', 'Value', 'Source', 'Comments', 'Description']
    return pd.DataFrame.from_records(list1 + hidden, columns=labels)


# ---------------------------------------------------------------------------
# Cells 34, 36, 37, 39, 40: calibration of the start year
# ---------------------------------------------------------------------------
def calibrate(control, out_path=None):
    """Calibrate the raw extraction and write the calibrated CSV plus its parameters JSON.

    Reproduces notebook cells 34 (population calibration and projection), 36
    (placeholder columns), 37 (conditioning, grid penalties, wind capacity
    factors), 39 (electrification calibration) and 40 (export). Returns the CSV path.
    """
    cal = control.calibration
    d = control.defaults
    out_path = Path(out_path) if out_path is not None else Path(control.paths["calibrated_csv"])
    raw_path = Path(control.paths["raw_input_csv"])

    onsseter = SettlementProcessor(str(raw_path))

    # cell 34
    pop_modelled, urban_modelled = onsseter.calibrate_current_pop_and_urban(
        cal["pop_start_year"], cal["urban_ratio_start_year"])
    onsseter.project_pop_and_urban(pop_modelled, cal["end_year_pop"], urban_modelled,
                                   cal["urban_ratio_end_year"], d["start_year"], d["end_year"],
                                   d["intermediate_year"])
    # cell 36
    onsseter.df['PerCapitaDemand'] = 0.0
    onsseter.df['ElectrificationOrder'] = 0.0
    onsseter.df['Conflict'] = 0.0
    # cell 37
    onsseter.condition_df()
    onsseter.df['GridPenalty'] = onsseter.grid_penalties(onsseter.df)
    onsseter.df['WindCF'] = onsseter.calc_wind_cfs()
    # cell 39
    elec_modelled, urban_internal_elec_ratio, rural_internal_elec_ratio = onsseter.elec_current_and_future(
        cal["elec_ratio_start_year"], cal["urban_elec_ratio"], cal["rural_elec_ratio"], d["start_year"],
        min_night_lights=cal["min_night_lights"], min_pop=cal["min_pop"],
        max_transformer_dist=cal["max_service_transformer_distance"],
        max_mv_dist=cal["max_mv_line_distance"], max_hv_dist=cal["max_hv_line_distance"])
    # cell 40
    out_path.parent.mkdir(parents=True, exist_ok=True)
    thr = d["pop_threshold"]
    calibrated = onsseter.df.loc[onsseter.df[SET_POP] > thr]
    calibrated.to_csv(out_path, index=False)

    # NB : elec_current_and_future renvoie (national, RURAL, URBAIN), mais l'appel
    # ci-dessus les recoit dans l'ordre (urbain, rural). Donc :
    #   urban_internal_elec_ratio contient le taux RURAL
    #   rural_internal_elec_ratio contient le taux URBAIN
    modelled_urban = float(rural_internal_elec_ratio)
    modelled_rural = float(urban_internal_elec_ratio)

    calib_info = {
        'start_year': d["start_year"], 'intermediate_year': d["intermediate_year"], 'end_year': d["end_year"],
        'pop_start_year': cal["pop_start_year"], 'end_year_pop': cal["end_year_pop"],
        'urban_ratio_start_year': cal["urban_ratio_start_year"], 'urban_ratio_end_year': cal["urban_ratio_end_year"],
        'elec_ratio_start_year': cal["elec_ratio_start_year"],
        'urban_elec_ratio': cal["urban_elec_ratio"], 'rural_elec_ratio': cal["rural_elec_ratio"],
        'min_night_lights': cal["min_night_lights"], 'min_pop': cal["min_pop"],
        'max_service_transformer_distance': cal["max_service_transformer_distance"],
        'max_mv_line_distance': cal["max_mv_line_distance"], 'max_hv_line_distance': cal["max_hv_line_distance"],
        'pop_threshold_applied': thr,
        'modelled_elec_rate': float(elec_modelled),
        'modelled_urban_elec_rate': modelled_urban,
        'modelled_rural_elec_rate': modelled_rural,
        'raw_input': str(raw_path),
        'raw_input_sha256': sha256_file(raw_path),
        'rows': int(len(calibrated)),
        'control_file_sha256': control.sha256,
    }
    (out_path.parent / f"{out_path.stem}_parameters.json").write_text(
        json.dumps(calib_info, indent=2), encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Cells 44 to 64: one scenario
# ---------------------------------------------------------------------------
REQUIRED_INPUT_COLUMNS = (
    "id", "Pop", "PopStartYear", "Pop2030", "Pop2040", "Pop2025", "IsUrban", "GHI", "WindVel",
    "Hydropower", "HydropowerDist", "HydropowerFID", "TravelHours", "ElecPopCalib", "ElecStart",
    "GridPenalty", "WindCF", "CurrentMVLineDist", "CurrentHVLineDist", "PlannedMVLineDist",
    "PlannedHVLineDist", "SubstationDist", "TransformerDist", "RoadDist", "NightLights",
    "ResidentialDemandTierCustom", "hc_count_com_hc", "hc_count_primary_hc", "hc_count_referral_hc",
    "FinalElecCode2025",
)


def _git_state(repo_root):
    import subprocess
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True,
                                text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=repo_root, capture_output=True,
                                    text=True, check=True).stdout.strip())
        return commit, dirty
    except Exception:
        return None, None


def _json_safe(value):
    if isinstance(value, dict):
        return {("inf" if k == float("inf") else str(k)): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _read_manifest(scenario_dir: Path):
    p = scenario_dir / "manifest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def skip_reason(existing, params: dict, calibrated_sha: str):
    """'complete' when a scenario folder's manifest proves the same run already exists.

    Same means: status complete, the same resolved parameters and the same
    calibrated input hash. Anything else (no manifest, running, other
    parameters, other input) returns None and the scenario is re-run.
    """
    if not existing or existing.get("status") != "complete":
        return None
    if existing.get("parameters") != _json_safe(params):
        return None
    if existing.get("calibrated_csv_sha256") != calibrated_sha:
        return None
    return "complete"


def check_calibration_provenance(control, calibrated_csv) -> str:
    """Compare the calibrated file's sibling parameters JSON with the control file's
    calibration block. Returns 'verified', or 'unverified' when no sibling exists
    (for example the colleague's shared calibrated file). Raises ControlError on a
    mismatch, because the manifest would otherwise claim a calibration that did
    not produce the input.
    """
    from scenario_control import CALIBRATION_KEYS, ControlError
    calibrated_csv = Path(calibrated_csv)
    sibling = calibrated_csv.parent / f"{calibrated_csv.stem}_parameters.json"
    if not sibling.exists():
        return "unverified"
    try:
        info = json.loads(sibling.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "unverified"
    mismatches = [k for k in sorted(CALIBRATION_KEYS)
                  if k in info and info[k] != control.calibration[k]]
    if mismatches:
        detail = ", ".join(f"{k}: file {info[k]} vs control {control.calibration[k]}" for k in mismatches)
        raise ControlError(f"calibrated file {calibrated_csv.name} was produced with another calibration "
                           f"({detail}); run with --calibrate to regenerate it")
    return "verified"


def complete_scenarios(control, batch_dir) -> list:
    """Scenario ids of the control file whose folder in batch_dir holds a complete
    manifest, in control-file order."""
    batch_dir = Path(batch_dir)
    out = []
    for sid in control.ids():
        m = _read_manifest(batch_dir / sid)
        if m and m.get("status") == "complete" and (batch_dir / sid / f"{sid}_Summaries.csv").exists():
            out.append(sid)
    return out


def summary_from_manifest(batch_dir, scenario_id: str) -> pd.DataFrame:
    """Read a finished scenario's Summaries CSV back as the notebook's summary table."""
    batch_dir = Path(batch_dir)
    return pd.read_csv(batch_dir / scenario_id / f"{scenario_id}_Summaries.csv", index_col=0)


def run_scenario(control, scenario_id: str, batch_dir, force: bool = False, log=print) -> dict:
    """Run one scenario of the control file into batch_dir/<scenario_id>/.

    Returns the manifest. A scenario whose manifest says complete is skipped
    unless force. Fails before the loop if the calibrated file lacks a column
    the notebook cells read.
    """
    import datetime as _dt
    import sys as _sys
    import time as _time
    import numpy as _np

    from guinea_demand_customization import apply_customized_demand
    from scenario_control import ControlError

    scenario = control.scenario(scenario_id)
    params = control.resolved(scenario_id)
    batch_dir = Path(batch_dir)
    out_dir = batch_dir / scenario_id

    calibrated_csv = Path(control.paths["calibrated_csv"])
    if not calibrated_csv.exists():
        raise ControlError(f"calibrated file not found: {calibrated_csv} (run calibrate first)")
    calibrated_sha = sha256_file(calibrated_csv)

    existing = _read_manifest(out_dir)
    if not force:
        if skip_reason(existing, params, calibrated_sha) == "complete":
            log(f"[{scenario_id}] complete already with the same parameters and input, skipped "
                "(use force to re-run)")
            existing["skipped"] = True
            return existing
        if existing and existing.get("status") == "complete":
            log(f"[{scenario_id}] existing outputs are stale (parameters or input changed), re-running")

    provenance = check_calibration_provenance(control, calibrated_csv)
    if provenance == "unverified":
        log(f"[{scenario_id}] calibration provenance unverified: no parameters file beside "
            f"{calibrated_csv.name}")

    t0 = _time.time()
    started = _dt.datetime.now().isoformat(timespec="seconds")
    log(f"[{scenario_id}] {scenario.label}")

    onsseter = SettlementProcessor(str(calibrated_csv))
    missing = [c for c in REQUIRED_INPUT_COLUMNS if c not in onsseter.df.columns]
    if missing:
        raise ControlError(f"calibrated file {calibrated_csv.name} lacks required columns: "
                           f"{', '.join(missing)}")
    rows_in = int(len(onsseter.df))

    technologies = build_technologies(params)
    start_year = params["start_year"]
    end_year = params["end_year"]
    intermediate_year = params["intermediate_year"]
    yearsofanalysis = [intermediate_year, end_year]
    eleclimits = {intermediate_year: params["intermediate_electrification_target"],
                  end_year: params["electrification_rate_target"]}
    time_steps = {intermediate_year: intermediate_year - start_year, end_year: end_year - intermediate_year}
    num_people_per_hh_rural = params["num_people_per_hh_rural"]
    num_people_per_hh_urban = params["num_people_per_hh_urban"]
    urban_target_tier = params["urban_target_tier"]
    rural_target_tier = params["rural_target_tier"]
    productive_demand = params["productive_demand"]
    diesel_techs = params["diesel_techs"]
    tech_switches = params["tech_switches"]
    grid_generation_cost = params["grid_generation_cost"]
    mv_line_max_length = params["mv_line_max_length"]
    auto_intensification = params["auto_intensification"]
    pv_path = str(control.paths["pv_profile"])
    wind_path = str(control.paths["wind_profile"])
    grid_calc = technologies["grid"]
    mg_pv_hybrid_calc = technologies["mg_pv_hybrid"]
    mg_wind_hybrid_calc = technologies["mg_wind_hybrid"]
    mg_hydro_calc = technologies["mg_hydro"]
    mg_wind_calc = technologies["mg_wind"]
    mg_pv_calc = technologies["mg_pv"]
    sa_pv_calc = technologies["sa_pv"]
    mg_diesel_calc = technologies["mg_diesel"]
    sa_diesel_calc = technologies["sa_diesel"]
    sa_diesel_cost = technologies["sa_diesel_cost"]
    mg_diesel_cost = technologies["mg_diesel_cost"]

    # cell 44
    pop_threshold = params["pop_threshold"]
    onsseter.df = onsseter.df.loc[onsseter.df[SET_POP] > pop_threshold]
    # cell 47
    onsseter.prepare_wtf_tier_columns(num_people_per_hh_rural, num_people_per_hh_urban,
                                      params["tier_1"], params["tier_2"], params["tier_3"],
                                      params["tier_4"], params["tier_5"])
    # cell 48
    onsseter = apply_customized_demand(onsseter, matrix_path=str(control.paths["productive_matrix"]),
                                       preference=params["productive_preference"])
    # cell 52
    cost_choice = params["cost_choice"]

    # cell 53
    onsseter.current_mv_line_dist()

    try:
        onsseter.df.reset_index(inplace=True)
    except ValueError:
        pass

    for year in yearsofanalysis:

        eleclimit = eleclimits[year]
        time_step = time_steps[year]

        if year == end_year:
            grid_connect_limit = time_step * params["annual_new_grid_connections_limit_end"] * 1000
            grid_cap_gen_limit = time_step * params["annual_grid_cap_gen_limit_end"] * 1000
        else:
            grid_connect_limit = time_step * params["annual_new_grid_connections_limit_intermediate"] * 1000
            grid_cap_gen_limit = time_step * params["annual_grid_cap_gen_limit_intermediate"] * 1000

        onsseter.set_scenario_variables(year, num_people_per_hh_rural, num_people_per_hh_urban, time_step,
                                        start_year, urban_target_tier,
                                        rural_target_tier, productive_demand)

        onsseter.diesel_cost_columns(sa_diesel_cost, mg_diesel_cost, year)

        mg_pv_hybrid_investment, mg_pv_hybrid_capacity = onsseter.calculate_pv_hybrids_lcoe(year,
                                                                                            year - time_step,
                                                                                            end_year,
                                                                                            time_step,
                                                                                            mg_pv_hybrid_calc,
                                                                                            1,
                                                                                            pv_path)

        mg_wind_hybrid_investment, mg_wind_hybrid_capacity = onsseter.calculate_wind_hybrids_lcoe(year,
                                                                                                  year - time_step,
                                                                                                  end_year,
                                                                                                  time_step,
                                                                                                  mg_wind_hybrid_calc,
                                                                                                  wind_path)

        sa_diesel_investment, sa_pv_investment, mg_diesel_investment, \
            mg_wind_investment, mg_hydro_investment, mg_pv_investment = onsseter.calculate_off_grid_lcoes(
                mg_hydro_calc, mg_wind_calc, mg_pv_calc, sa_pv_calc, mg_diesel_calc, sa_diesel_calc,
                year, end_year, time_step, diesel_techs, tech_switches=tech_switches)

        grid_investment, grid_cap_gen_limit, grid_connect_limit = onsseter.pre_electrification(grid_generation_cost,
                                                                                               year,
                                                                                               time_step,
                                                                                               end_year,
                                                                                               grid_calc,
                                                                                               grid_cap_gen_limit,
                                                                                               grid_connect_limit)

        onsseter.df[SET_LCOE_GRID + "{}".format(year)], onsseter.df[SET_MIN_GRID_DIST + "{}".format(year)], \
            onsseter.df[SET_ELEC_ORDER + "{}".format(year)], onsseter.df[SET_MV_CONNECT_DIST], grid_investment = \
            onsseter.elec_extension(grid_calc,
                                    mv_line_max_length,
                                    year,
                                    start_year,
                                    end_year,
                                    time_step,
                                    grid_cap_gen_limit,
                                    grid_connect_limit,
                                    auto_intensification=auto_intensification,
                                    prioritization=5,
                                    new_investment=grid_investment,
                                    threshold=9999999999)

        onsseter.results_columns(year, time_step, 5, auto_intensification)

        onsseter.calculate_investments(sa_diesel_investment, sa_pv_investment, mg_diesel_investment,
                                       mg_pv_investment, mg_wind_investment, mg_hydro_investment,
                                       mg_pv_hybrid_investment, mg_wind_hybrid_investment, grid_investment, year)

        onsseter.apply_limitations(eleclimit, year, time_step, 5, auto_intensification)

        onsseter.calculate_new_capacity(mg_pv_hybrid_capacity, mg_wind_hybrid_capacity, mg_hydro_calc, mg_wind_calc,
                                        mg_pv_calc, sa_pv_calc, mg_diesel_calc, sa_diesel_calc, grid_calc, year)

        onsseter.tech_code_update(year, start_year)

    # cell 55
    table = summary_table(onsseter.df, yearsofanalysis, cost_choice)

    # cells 62 to 64
    variables = variables_table(control, scenario, params, technologies,
                                extra={"calibrated_csv_sha256": calibrated_sha, "scenario_id": scenario_id})
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"results": out_dir / f"{scenario_id}_Results.csv",
             "summaries": out_dir / f"{scenario_id}_Summaries.csv",
             "variables": out_dir / f"{scenario_id}_Variables.csv"}
    onsseter.df.to_csv(paths["results"], index=False)
    table.to_csv(paths["summaries"], index=True)
    variables.to_csv(paths["variables"], index=False)

    commit, dirty = _git_state(control.repo_root)
    manifest = {
        "scenario_id": scenario_id,
        "label": scenario.label,
        "demand_case": scenario.demand_case,
        "legacy_name": scenario.legacy_name,
        "status": "complete",
        "started": started,
        "finished": _dt.datetime.now().isoformat(timespec="seconds"),
        "seconds": round(_time.time() - t0, 1),
        "parameters": _json_safe(params),
        "calibration": _json_safe(control.calibration),
        "control_file": str(control.path),
        "control_file_sha256": control.sha256,
        "calibrated_csv": str(calibrated_csv),
        "calibrated_csv_sha256": calibrated_sha,
        "calibration_provenance": provenance,
        "rows_in": rows_in,
        "rows_out": int(len(onsseter.df)),
        "git_commit": commit,
        "git_dirty": dirty,
        "python": _sys.version.split()[0],
        "pandas": pd.__version__,
        "numpy": _np.__version__,
        "outputs": {k: {"path": str(p), "bytes": p.stat().st_size} for k, p in paths.items()},
        "technology_constants": TECH_CONSTANTS,
        "hydro_viability_km": HYDRO_VIABILITY_KM,
        "hydro_site_filter": HYDRO_SITE_FILTER,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log(f"[{scenario_id}] complete in {manifest['seconds']} s, {manifest['rows_out']} settlements")
    return manifest


# ---------------------------------------------------------------------------
# Batch: several scenarios, one comparison table
# ---------------------------------------------------------------------------
COMPARISON_COLUMNS = ["scenario_id", "label", "demand_case", "grid_generation_cost",
                      "urban_target_tier", "rural_target_tier", "technology", "year",
                      "population", "new_connections", "capacity_mw", "investment_musd"]


def resolve_batch_dir(control, batch_name=None) -> Path:
    """paths.output_root / batch_name, the name defaulting to today's date."""
    import datetime as _dt
    name = batch_name or _dt.date.today().isoformat()
    return Path(control.paths["output_root"]) / name


def select_ids(control, ids=None) -> list:
    """The scenario ids to run, in control-file order; unknown ids are an error."""
    from scenario_control import ControlError
    valid = control.ids()
    if ids is None:
        return list(valid)
    unknown = [i for i in ids if i not in valid]
    if unknown:
        raise ControlError(f"unknown scenario id(s) {', '.join(unknown)}; valid ids: {', '.join(valid)}")
    return [i for i in valid if i in set(ids)]


def comparison_table(control, batch_dir, ids) -> pd.DataFrame:
    """Long table, one row per scenario x technology x year, from the Summaries files."""
    rows = []
    for sid in ids:
        s = control.scenario(sid)
        p = control.resolved(sid)
        table = summary_from_manifest(batch_dir, sid)
        for tech, r in table.iterrows():
            for col in table.columns:
                if col.startswith("Population"):
                    year = int(col[len("Population"):])
                    rows.append({
                        "scenario_id": sid, "label": s.label, "demand_case": s.demand_case,
                        "grid_generation_cost": p["grid_generation_cost"],
                        "urban_target_tier": p["urban_target_tier"],
                        "rural_target_tier": p["rural_target_tier"],
                        "technology": tech, "year": year,
                        "population": r[f"Population{year}"],
                        "new_connections": r[f"NewConnections{year}"],
                        "capacity_mw": r[f"Capacity{year} (MW)"],
                        "investment_musd": r[f"Investment{year} (million USD)"],
                    })
    return pd.DataFrame(rows, columns=COMPARISON_COLUMNS)


def run_batch(control, ids=None, batch_name=None, force: bool = False, calibrate_first: bool = False,
              log=print) -> Path:
    """Run the selected scenarios (all by default) into one batch folder.

    Calibrates first when asked or when the calibrated file is missing. Writes
    comparison_summary.csv over the selected scenarios and appends to
    batch_log.txt. Returns the batch folder.
    """
    import datetime as _dt
    selected = select_ids(control, ids)          # fails before anything is created
    batch_dir = resolve_batch_dir(control, batch_name)
    calibrated_csv = Path(control.paths["calibrated_csv"])
    if calibrate_first or not calibrated_csv.exists():
        log(f"calibrating from {Path(control.paths['raw_input_csv']).name}")
        calibrate(control)
    batch_dir.mkdir(parents=True, exist_ok=True)
    log_path = batch_dir / "batch_log.txt"

    def stamp(sid, status, seconds):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"{_dt.datetime.now().isoformat(timespec='seconds')}\t{sid}\t{status}\t{seconds}\n")

    for sid in selected:
        try:
            m = run_scenario(control, sid, batch_dir, force=force, log=log)
        except Exception as e:  # record, then re-raise: a half-run batch must be visible
            stamp(sid, f"failed: {e}", "")
            raise
        stamp(sid, "skipped" if m.get("skipped") else m["status"], m.get("seconds", ""))

    done = complete_scenarios(control, batch_dir)
    comparison_table(control, batch_dir, done).to_csv(batch_dir / "comparison_summary.csv", index=False)
    log(f"batch {batch_dir.name}: {len(selected)} scenario(s) run or skipped, comparison_summary.csv "
        f"covers the {len(done)} complete scenario(s) of this batch")
    return batch_dir
