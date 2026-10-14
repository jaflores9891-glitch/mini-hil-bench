import pytest

from mini_hil_bench.bench.ports import Scenario
from mini_hil_bench.ecu.aeb_ecu import AebState

FILLER_FRAMES_PER_STEP = 25  # ~2500 frames/s, roughly 60 % of a 500 kbit/s CAN bus

pytestmark = pytest.mark.stress


@pytest.mark.req("REQ-AEB-002", "REQ-AEB-003", "REQ-AEB-004")
def test_ecu_keeps_braking_performance_under_bus_load(run_scenario):
    scenario = Scenario(
        ego_speed_mps=50 / 3.6,
        initial_gap_m=60.0,
        bus_load_frames_per_step=FILLER_FRAMES_PER_STEP,
    )
    df = run_scenario(scenario, duration_s=8.0)
    states = set(df["ecu.aeb_state"].dropna())
    assert {AebState.PARTIAL_BRAKE, AebState.FULL_BRAKE} <= states
    assert AebState.FAULT not in states
    assert df["ego.speed_mps"].iloc[-1] == 0.0
    assert df["plant.gap_m"].min() >= 1.0
