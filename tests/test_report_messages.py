import math

import pandas as pd
import pytest

from report import messages as MS


def test_formatters():
    assert MS.fmt_people(13_451_356) == "13.5 million"
    assert MS.fmt_people(982_070) == "982,000"
    assert MS.fmt_people(146_000) == "146,000"
    assert MS.fmt_people(2_500) == "2,500"
    assert MS.fmt_musd(1331.83) == "1,332 million USD"
    assert MS.fmt_musd(982.07) == "982 million USD"
    assert MS.fmt_musd(2.5) == "2.5 million USD"
    assert MS.fmt_usd(2491.0) == "2,491 USD"
    assert MS.fmt_pct(0.6990) == "70%" and MS.fmt_pct(0.6990, 1) == "69.9%"
    assert MS.fmt_lcoe(0.1326) == "0.13 USD/kWh" and MS.fmt_lcoe(0.1326, 3) == "0.133 USD/kWh"
    assert MS.fmt_mw(353.08) == "353 MW" and MS.fmt_mw(0.98) == "1.0 MW"


def test_direction_words():
    assert MS.direction(0.08) == "increases" and MS.direction(-0.08) == "decreases"
    assert MS.direction(0.001) == "leaves unchanged"
    assert MS.direction(0.08, up="raises", down="lowers") == "raises"


def test_formatters_raise_on_nan():
    for f in (MS.fmt_people, MS.fmt_musd, MS.fmt_usd, MS.fmt_pct, MS.fmt_lcoe):
        with pytest.raises(ValueError):
            f(float("nan"))


def _headlines():
    base = {"population_2040": 27_697_654.0, "people_reached_cum": 18_280_000.0, "investment_musd_cum": 1752.4,
            "capacity_mw_cum": 400.0, "usd_per_new_connection": 95.9, "people_per_musd": 10_430.0,
            "lcoe_energy_w": 0.168, "lcoe_pop_w": 0.15, "lcoe_energy_w_excl_dens": 0.25, "grid_share_2040": 0.74,
            "offgrid_share_2040": 0.26, "sa_pv_people_2040": 5_720_000.0, "mg_pv_people_2040": 1_580_000.0,
            "mg_hydro_people_2040": 31_000.0, "grid_ext_people_2040": 2_100_000.0, "grid_ext_settlements_2040": 1200,
            "unserved_2030": 6_110_000.0, "investment_musd_2030": 420.6, "investment_musd_2040": 1331.8}
    h = {}
    for i, case in enumerate(["TD_Low_minus", "TD_Low", "TD_High", "TD_High_plus", "BU"]):
        d = dict(base)
        d["investment_musd_cum"] = 1300 + 400 * i
        d["lcoe_energy_w"] = 0.16 + 0.01 * i
        d["sa_pv_people_2040"] = 8_000_000 - 1_500_000 * i
        d["mg_pv_people_2040"] = 500_000 + 800_000 * i
        h[case] = d
    return h


def test_key_messages_are_complete_sentences_from_numbers():
    sens = pd.DataFrame([
        {"demand_case": c, "grid_cost": g, "investment_musd_cum": 1800 + 50 * k, "switched_people": 3e6 * k,
         "grid_ext_people": 5e6 - 1e6 * k, "lcoe_energy_w": 0.15 + 0.02 * k}
        for c in ("TD_Low", "TD_High", "BU") for k, g in enumerate([0.047, 0.078, 0.1, 0.22])])
    deltas = {"TD_Low_minus": {"investment_musd_cum": -26.0, "lcoe_energy_w": -5.0},
              "TD_High_plus": {"investment_musd_cum": 9.0, "lcoe_energy_w": 3.0}}
    hydro = {"BU": {"sites": 13, "settlements": 18, "people": 31_000.0, "capacity_mw": 0.98}}
    msgs = MS.key_messages(_headlines(), sens, deltas, hydro)
    assert len(msgs) >= 8
    for m in msgs:
        assert set(m) == {"id", "text", "source"} and m["text"].endswith(".")
        assert any(ch.isdigit() for ch in m["text"]) and "nan" not in m["text"].lower()
        assert "—" not in m["text"]
    text = " ".join(m["text"] for m in msgs)
    assert "1,300 million USD" in text and "2,900 million USD" in text        # investment range
    assert "0.22" in text and "0.1" in text                                    # grid-cost sensitivity
    assert "13 sites" in text or "13 hydro" in text


def test_key_messages_raise_on_missing_number():
    h = _headlines()
    h["BU"]["investment_musd_cum"] = float("nan")
    with pytest.raises(ValueError):
        MS.key_messages(h, pd.DataFrame(columns=["demand_case", "grid_cost", "investment_musd_cum",
                                                  "switched_people", "grid_ext_people", "lcoe_energy_w"]), {}, {})
