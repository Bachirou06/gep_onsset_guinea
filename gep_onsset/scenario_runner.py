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
import pandas as pd

from onsset import *  # noqa: F401,F403  (SET_* constants, Technology, SettlementProcessor)

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
