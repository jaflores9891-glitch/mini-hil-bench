import pytest

from mini_hil_bench.bench.ports import Scenario
from mini_hil_bench.ecu.aeb_ecu import AebState

KPH = 1 / 3.6
STOP_MARGIN_S = 3.0

pytestmark = pytest.mark.edge_case


@pytest.mark.req("REQ-AEB-005")
@pytest.mark.parametrize(
    ("speed_kph", "expect_active"),
    [(9.5, False), (9.9, False), (10.1, True), (10.5, True)],
    ids=["9.5kph-inactive", "9.9kph-inactive", "10.1kph-active", "10.5kph-active"],
)
def test_activation_around_minimum_speed(run_scenario, bench_config, speed_kph, expect_active):
    speed_mps = speed_kph * KPH
    initial_ttc_s = bench_config.ecu.ttc_warning_s + 0.5
    df = run_scenario(Scenario(speed_mps, initial_ttc_s * speed_mps), duration_s=4.0)
    activated = (df["ecu.aeb_state"] == AebState.WARNING).any()
    assert activated == expect_active


@pytest.mark.req("REQ-AEB-004")
@pytest.mark.parametrize("speed_kph", [20, 35, 50])
@pytest.mark.parametrize(
    "initial_ttc_s",
    [5.0, 2.6, 1.6],
    ids=["ttc5.0", "ttc-at-warning", "ttc-at-partial"],
)
def test_no_collision_over_speed_and_initial_distance(run_scenario, speed_kph, initial_ttc_s):
    speed_mps = speed_kph * KPH
    scenario = Scenario(ego_speed_mps=speed_mps, initial_gap_m=initial_ttc_s * speed_mps)
    df = run_scenario(scenario, duration_s=initial_ttc_s + STOP_MARGIN_S)
    assert df["ego.speed_mps"].iloc[-1] == 0.0
    assert df["plant.gap_m"].min() >= 1.0
