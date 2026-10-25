"""Technology mix on two bases: share of new connections 2025 to 2040 (where the
decentralised impact shows) and share of the 2040 population including the people
already on the grid."""
import pandas as pd
import pytest

from report import messages as MS
from report import metrics as M
from tests.test_report_metrics import frame


def test_headline_reports_dre_shares_on_both_bases():
    h = M.headline(frame())
    # new connections cumulative (served): grid 1: 300, grid 2: 600, SA 3: 300, MG 5: 350, hydro 7: 120 -> total 1670
    assert h["new_connections_by_tech"] == pytest.approx({1: 300, 2: 600, 3: 300, 5: 350, 7: 120})
    assert h["dre_new_connections"] == pytest.approx(770)
    assert h["dre_share_new_connections"] == pytest.approx(770 / 1670)
    # population 2040 by code (every row): 1: 1200, 2: 600, 3: 305, 5: 350, 7: 120 -> 2575
    assert h["dre_share_pop_2040"] == pytest.approx(775 / 2575)
    assert h["grid_ext_share_new_connections"] == pytest.approx(600 / 1670)


def test_mix_table_has_both_bases_per_case():
    t = M.mix_table({"BU": frame(), "TD_Low": frame()})
    assert list(t.index.names) == ["demand_case", "basis"]
    row = t.loc[("BU", "new_connections")]
    assert row["Stand-alone PV"] == pytest.approx(300 / 1670) and row["total"] == 1670
    row2 = t.loc[("BU", "population_2040")]
    assert row2["Grid densification"] == pytest.approx(1200 / 2575) and row2["total"] == 2575


def test_key_message_tech_mix_names_the_key_cases_and_both_bases():
    base = M.headline(frame())
    hs = {c: dict(base) for c in ("TD_Low_minus", "TD_High", "BU", "TD_Low", "TD_High_plus")}
    m = MS.km_tech_mix(hs, key_cases=("TD_Low_minus", "TD_High", "BU"))
    for nm in ("U3R1", "U4R3", "BU"):
        assert nm in m["text"]
    assert "U3R2" not in m["text"] and "U5R3" not in m["text"]
    assert "new connections" in m["text"] and "2040 population" in m["text"]
    assert "46%" in m["text"]            # 770 / 1670 decentralised share of new connections
    assert "30%" in m["text"]            # 775 / 2575 decentralised share of the 2040 population
