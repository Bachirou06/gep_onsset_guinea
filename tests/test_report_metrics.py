"""Metrics on a six-row synthetic frame with hand-computed answers.

Rows: 1 grid densification (urban, start-year electrified), 2 grid extension,
3 stand-alone PV (not served in 2030: code 99), 4 mini-grid PV, 5 mini-grid
hydro, 6 stand-alone PV with no new connections in 2040 and an LCOE of 99."""
import numpy as np
import pandas as pd
import pytest

from report import metrics as M


def frame() -> pd.DataFrame:
    rows = [
        # id, ElecStart, IsUrban, Admin_1, Pop2030, Pop2040, NC30, NC40, Cap30, Cap40, Inv30, Inv40,
        # Code30, Code40, LCOE30, LCOE40, E30, E40, hh, FID, Hydro, HydroDist
        (1, 1, 2, "Boke", 1000, 1200, 100, 200, 50, 60, 1e6, 2e6, 1, 1, 0.10, 0.10, 500, 600, 6.0, -1, 0.0, 50.0),
        (2, 0, 0, "Boke", 500, 600, 500, 100, 20, 5, 5e5, 1e5, 2, 2, 0.12, 0.11, 100, 120, 6.0, -1, 0.0, 40.0),
        (3, 0, 0, "Labe", 200, 250, 200, 250, 0, 8, 0.0, 4e4, 99, 3, 0.40, 0.32, 0, 40, 5.0, -1, 0.0, 30.0),
        (4, 0, 0, "Labe", 300, 350, 300, 50, 30, 5, 3e5, 5e4, 5, 5, 0.27, 0.26, 90, 100, 6.0, -1, 0.0, 20.0),
        (5, 0, 0, "Not assigned", 100, 120, 100, 20, 10, 2, 1e5, 2e4, 7, 7, 0.20, 0.19, 30, 35, 6.0, 7, 500.0, 3.0),
        (6, 0, 0, "Boke", 50, 55, 50, 0, 5, 0, 5e4, 0.0, 3, 3, 0.33, 99.0, 10, 0, 6.0, -1, 0.0, 60.0),
    ]
    cols = ["id", "ElecStart", "IsUrban", "Admin_1", "Pop2030", "Pop2040", "NewConnections2030",
            "NewConnections2040", "NewCapacity2030", "NewCapacity2040", "InvestmentCost2030",
            "InvestmentCost2040", "FinalElecCode2030", "FinalElecCode2040", "MinimumOverallLCOE2030",
            "MinimumOverallLCOE2040", "EnergyPerSettlement2030", "EnergyPerSettlement2040",
            "NumPeoplePerHH", "HydropowerFID", "Hydropower", "HydropowerDist"]
    df = pd.DataFrame(rows, columns=cols)
    df["PopStartYear"] = df["Pop2030"] * 0.9
    df["X_deg"] = np.linspace(-13.0, -8.0, 6)
    df["Y_deg"] = np.linspace(8.0, 12.0, 6)
    df["Admin_2"] = df["Admin_1"]
    return df


def test_tech_table_2040_population_includes_unserved_rows_but_connections_do_not():
    t = M.tech_table(frame(), 2040)
    assert t.loc[3, "population"] == 305 and t.loc[3, "new_connections"] == 250
    assert t.loc[3, "settlements"] == 2
    assert t.loc[1, "capacity_mw"] == pytest.approx(0.06) and t.loc[1, "investment_musd"] == pytest.approx(2.0)
    assert 99 not in t.index


def test_tech_table_2030_reports_not_yet_electrified_separately():
    t = M.tech_table(frame(), 2030)
    assert t.loc[99, "population"] == 200 and t.loc[99, "investment_musd"] == 0
    assert t.loc[2, "new_connections"] == 500


def test_cumulative_table_totals():
    c = M.cumulative_table(frame())
    assert c.loc["Total", "new_connections_cum"] == 1670
    assert c.loc["Total", "investment_musd_cum"] == pytest.approx(4.16)
    assert c.loc["Total", "capacity_mw_cum"] == pytest.approx((115 + 80) / 1000)
    assert c.loc[3, "new_connections_cum"] == 300           # 50 in 2030 (id 6) + 250 in 2040 (id 3)


def test_weighted_lcoe_energy_population_and_excluding_densification():
    df = frame()
    assert M.weighted_lcoe(df, 2040, "energy") == pytest.approx(118.65 / 895)
    assert M.weighted_lcoe(df, 2040, "population") == pytest.approx(379.8 / 2520)
    assert M.weighted_lcoe(df, 2040, "energy", exclude_densification=True) == pytest.approx(58.65 / 295)


def test_weighted_lcoe_2030_filters_code_99_rows():
    df = frame()
    # served 2030 rows: ids 1,2,4,5,6 (id 3 is code 99 and must be excluded)
    expected = (0.10 * 500 + 0.12 * 100 + 0.27 * 90 + 0.20 * 30 + 0.33 * 10) / (500 + 100 + 90 + 30 + 10)
    assert M.weighted_lcoe(df, 2030, "energy") == pytest.approx(expected)


def test_consultancy_metrics_rows_and_values():
    m = M.consultancy_metrics(frame())
    assert m.loc["Total", "usd_per_new_connection"] == pytest.approx(4.16e6 / 1670)
    assert m.loc["Total", "people_per_musd"] == pytest.approx(1670 / 4.16)
    assert m.loc["Total", "lcoe_energy_w"] == pytest.approx(118.65 / 895)
    assert m.loc["Total excl. densification", "lcoe_energy_w"] == pytest.approx(58.65 / 295)
    assert m.loc[1, "usd_per_new_connection"] == pytest.approx(3e6 / 300)
    assert m.loc["Total", "usd_per_household"] == pytest.approx(4.16e6 / (1050 / 6 - 100 / 6 + 100 / 6 + 620 / 6 - 250 / 6 + 250 / 5))
    assert m.loc["Total", "share_pop_2040"] == pytest.approx(1.0)


def test_category_shares_all_and_newly_electrified():
    df = frame()
    s = M.category_shares(df, 2040)
    assert s["Grid"] == pytest.approx(1800 / 2575) and s["Mini-grid"] == pytest.approx(470 / 2575)
    n = M.category_shares(df, 2040, newly_electrified_only=True)
    assert n["Grid"] == pytest.approx(600 / 1375)


def test_region_urban_rural_and_hydro_tables():
    df = frame()
    r = M.region_table(df, 2040)
    assert r.loc["Boke", "population"] == 1855 and r.loc["Not assigned", "population"] == 120
    assert r.loc["Boke", "grid_share"] == pytest.approx(1800 / 1855)
    assert r.loc["Boke", "investment_musd_cum"] == pytest.approx((1e6 + 5e5 + 5e4 + 2e6 + 1e5) / 1e6)
    u = M.urban_rural_table(df)
    assert u.loc["Urban", "usd_per_new_connection"] == pytest.approx(3e6 / 300)
    assert u.loc["Rural", "new_connections_cum"] == 1370
    h = M.hydro_table(df, 2040)
    assert h == {"sites": 1, "settlements": 1, "people": 120, "capacity_mw": pytest.approx(0.002),
                 "investment_musd": pytest.approx(0.02), "mean_dist_km": 3.0}


def test_start_year_and_phasing_tables():
    df = frame()
    s = M.start_year_table(df)
    assert s.loc["Boke", "electrified_pop_start"] == pytest.approx(900) and s.loc["Boke", "settlements"] == 3
    assert s.loc["Total", "access_rate_start"] == pytest.approx(900 / (2150 * 0.9))
    p = M.phasing_table(df)
    assert p.loc[(2030, "Boke", 2), "new_connections"] == 500
    assert p.loc[(2040, "Labe", 3), "investment_musd"] == pytest.approx(0.04)


def test_switches_and_demand_delta():
    ref = frame()
    alt = frame()
    alt.loc[alt.id == 2, "FinalElecCode2040"] = 5
    alt.loc[alt.id == 3, "FinalElecCode2040"] = 5
    flows, totals = M.switches(ref, alt, 2040)
    assert totals == {"settlements": 2, "people": 850}
    assert flows.set_index(["from_code", "to_code"]).loc[(2, 5), "people"] == 600
    d = M.demand_delta(alt, ref)
    assert set(d.columns) == {"metric", "base", "variant", "delta_abs", "delta_pct"}
    assert d.set_index("metric").loc["investment_musd_cum", "delta_abs"] == 0


def test_lcoe_histogram_is_population_weighted():
    h = M.lcoe_histogram(frame(), 2040, bins=np.array([0.0, 0.15, 0.3, 0.6]))
    assert h["people"].sum() == 2520           # served rows with LCOE < 99
    assert h.loc[0, "people"] == 1800          # 0.10 and 0.11 fall in the first bin


def test_corridor_table_uses_distance_threshold():
    df = frame()
    geo = pd.DataFrame({"id": df.id, "kkt_main_dist_km": [50, 8, 4, 30, 90, 12]})
    t = M.corridor_table(df, geo, radius_km=10)
    assert t["settlements"] == 2 and t["people_2040"] == 850
    assert t["investment_musd_cum"] == pytest.approx((5e5 + 1e5 + 4e4) / 1e6)
