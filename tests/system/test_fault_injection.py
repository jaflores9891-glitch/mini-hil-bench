import pytest

from mini_hil_bench.bench.faults import Fault, FaultType
from mini_hil_bench.bench.ports import Scenario
from mini_hil_bench.ecu.aeb_ecu import AebState

KPH = 1 / 3.6
CRUISE = Scenario(ego_speed_mps=50 * KPH, initial_gap_m=100.0)
APPROACH = Scenario(ego_speed_mps=50 * KPH, initial_gap_m=60.0)
CYCLE_MARGIN_S = 0.05

pytestmark = pytest.mark.fault_injection


def _fault_onset_s(df):
    faulted = df[df["ecu.aeb_state"] == AebState.FAULT]
    assert not faulted.empty, "ECU never entered FAULT"
    return faulted["time_s"].iloc[0]


def _inject_after(bench, scenario, fault, before_s, after_s):
    bench.load_scenario(scenario)
    bench.run_for(before_s)
    bench.faults.inject(fault)
    bench.run_for(after_s)
    return bench.model.capture(["ecu.aeb_state", "ecu.brake_request"])


@pytest.mark.req("REQ-AEB-007")
def test_radar_timeout_sets_fault_without_braking(bench, bench_config):
    inject_s = 1.0
    df = _inject_after(bench, APPROACH, Fault(FaultType.SILENCE, "RadarObject"), inject_s, 1.0)
    assert _fault_onset_s(df) - inject_s <= bench_config.ecu.radar_timeout_s + CYCLE_MARGIN_S
    after = df[df["time_s"] >= _fault_onset_s(df)]
    assert (after["ecu.aeb_state"] == AebState.FAULT).all()
    assert (after["ecu.brake_request"] == 0).all()


@pytest.mark.req("REQ-AEB-007")
def test_single_dropped_radar_frame_does_not_set_fault(bench):
    df = _inject_after(bench, CRUISE, Fault(FaultType.DROP, "RadarObject", count=1), 1.0, 1.0)
    assert not (df["ecu.aeb_state"] == AebState.FAULT).any()


@pytest.mark.req("REQ-AEB-008")
def test_frozen_alive_counter_sets_fault_without_braking(bench, bench_config):
    inject_s = 1.0
    fault = Fault(FaultType.FREEZE, "RadarObject", signal="RadarAliveCounter")
    df = _inject_after(bench, APPROACH, fault, inject_s, 1.0)
    radar_cycle_s = 0.02
    max_detection_s = (bench_config.ecu.alive_counter_max_repeats + 1) * radar_cycle_s
    assert _fault_onset_s(df) - inject_s <= max_detection_s + CYCLE_MARGIN_S
    assert (df[df["time_s"] >= _fault_onset_s(df)]["ecu.brake_request"] == 0).all()


@pytest.mark.req("REQ-AEB-006")
def test_object_flagged_invalid_is_ignored(run_scenario):
    fault = Fault(FaultType.FREEZE, "RadarObject", signal="ObjValid", value=0)
    df = run_scenario(APPROACH, duration_s=5.0, faults=[fault])
    assert (df["radar.valid"].dropna() == 0).all()
    assert set(df["ecu.aeb_state"].dropna()) <= {AebState.OFF, AebState.STANDBY}


@pytest.mark.req("REQ-AEB-004")
def test_distance_offset_still_avoids_collision(run_scenario):
    fault = Fault(FaultType.OFFSET, "RadarObject", signal="ObjDistance", value=1.0)
    df = run_scenario(APPROACH, duration_s=8.0, faults=[fault])
    assert df["ego.speed_mps"].iloc[-1] == 0.0
    assert df["plant.gap_m"].min() > 0.0


@pytest.mark.req("REQ-AEB-004", "REQ-AEB-007")
def test_delayed_radar_frames_avoid_collision_without_fault(run_scenario):
    fault = Fault(FaultType.DELAY, "RadarObject", count=5)
    df = run_scenario(APPROACH, duration_s=8.0, faults=[fault])
    assert not (df["ecu.aeb_state"] == AebState.FAULT).any()
    assert df["plant.gap_m"].min() > 0.0
