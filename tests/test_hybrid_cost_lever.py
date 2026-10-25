"""The mini-grid PV hybrid panel cost factor lever (default 1 keeps the notebook's literal)."""
import inspect

import pytest

from tests.test_scenario_control import minimal_control


@pytest.fixture
def sc(gep_path):
    import scenario_control
    return scenario_control


def test_lever_is_a_scenario_key_with_default_one_in_the_study_file(sc):
    assert "mg_pv_hybrid_cost_factor" in sc.SCENARIO_KEYS
    c = sc.load_control("Scenarios/guinea_scenarios.json", check_paths=False)
    assert c.defaults["mg_pv_hybrid_cost_factor"] == 1


def test_lever_must_be_a_positive_number(sc, tmp_path):
    with pytest.raises(sc.ControlError, match="mg_pv_hybrid_cost_factor"):
        sc.load_control(minimal_control(tmp_path, defaults_extra={"mg_pv_hybrid_cost_factor": 0}), check_paths=False)
    with pytest.raises(sc.ControlError, match="mg_pv_hybrid_cost_factor"):
        sc.load_control(minimal_control(tmp_path, defaults_extra={"mg_pv_hybrid_cost_factor": "0.75"}), check_paths=False)


def test_runner_passes_the_lever_to_the_hybrid_call(gep_path):
    import scenario_runner
    src = inspect.getsource(scenario_runner.run_scenario)
    call = src[src.index("calculate_pv_hybrids_lcoe("):]
    call = call[:call.index("pv_path)") + len("pv_path)")]
    assert 'params["mg_pv_hybrid_cost_factor"]' in call
    assert "\n            1,\n" not in call                       # the notebook's literal is gone


def test_variables_table_records_the_lever(gep_path):
    import scenario_control, scenario_runner
    c = scenario_control.load_control("Scenarios/guinea_scenarios.json", check_paths=False)
    s = c.scenario("BU_g0.1")
    p = c.resolved(s.id)
    df = scenario_runner.variables_table(c, s, p, scenario_runner.build_technologies(p), extra={})
    assert "mg_pv_hybrid_cost_factor" in set(df.Variable)
