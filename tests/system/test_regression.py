import pytest

from mini_hil_bench.bench.ports import Scenario
from mini_hil_bench.ecu.aeb_ecu import AebState
from mini_hil_bench.plant.lead_object import LeadProfile

KPH = 1 / 3.6
ONSET_TOLERANCE_S = 0.15  # radar latency + cycle time + noise
MIN_STANDSTILL_GAP_M = 1.0

pytestmark = pytest.mark.regression


def _stationary(speed_kph, gap_m=60.0):
    return Scenario(ego_speed_mps=speed_kph * KPH, initial_gap_m=gap_m)


def _onset_ttc_s(df, state):
    rows = df[df["ecu.aeb_state"] == state]
    assert not rows.empty, f"ECU never entered {state.name}"
    return rows["plant.ttc_s"].iloc[0]


@pytest.mark.req("REQ-AEB-001")
def test_warning_issued_when_ttc_drops_below_warning_threshold(run_scenario, bench_config):
    df = run_scenario(_stationary(50), duration_s=6.0)
    threshold_s = bench_config.ecu.ttc_warning_s
    assert threshold_s - ONSET_TOLERANCE_S <= _onset_ttc_s(df, AebState.WARNING) <= threshold_s
    warning = df[df["ecu.aeb_state"] == AebState.WARNING]
    assert (warning["ecu.brake_request"] == 0).all()


@pytest.mark.req("REQ-AEB-002")
def test_partial_brake_at_partial_ttc_threshold(run_scenario, bench_config):
    df = run_scenario(_stationary(50), duration_s=6.0)
    ecu = bench_config.ecu
    onset_s = _onset_ttc_s(df, AebState.PARTIAL_BRAKE)
    assert ecu.ttc_partial_s - ONSET_TOLERANCE_S <= onset_s <= ecu.ttc_partial_s
    partial = df[df["ecu.aeb_state"] == AebState.PARTIAL_BRAKE]
    assert partial["ecu.decel_request_mps2"].to_numpy() == pytest.approx(ecu.partial_decel_mps2)
    assert (partial["ecu.brake_request"] == 1).all()


@pytest.mark.req("REQ-AEB-003")
def test_full_brake_at_full_ttc_threshold(run_scenario, bench_config):
    df = run_scenario(_stationary(50), duration_s=6.0)
    ecu = bench_config.ecu
    onset_s = _onset_ttc_s(df, AebState.FULL_BRAKE)
    assert ecu.ttc_full_s - ONSET_TOLERANCE_S <= onset_s <= ecu.ttc_full_s
    full = df[df["ecu.aeb_state"] == AebState.FULL_BRAKE]
    assert full["ecu.decel_request_mps2"].to_numpy() == pytest.approx(ecu.full_decel_mps2)


@pytest.mark.req("REQ-AEB-004")
@pytest.mark.parametrize("speed_kph", [30, 50])
def test_no_collision_with_stationary_target(run_scenario, speed_kph):
    df = run_scenario(_stationary(speed_kph), duration_s=8.0)
    assert df["ego.speed_mps"].iloc[-1] == 0.0
    assert df["plant.gap_m"].min() >= MIN_STANDSTILL_GAP_M


@pytest.mark.req("REQ-AEB-004")
def test_no_collision_with_braking_lead_vehicle(run_scenario):
    scenario = Scenario(
        ego_speed_mps=50 * KPH,
        initial_gap_m=25.0,
        lead_profile=LeadProfile.DECELERATING,
        lead_speed_mps=50 * KPH,
        lead_decel_mps2=6.0,
    )
    df = run_scenario(scenario, duration_s=8.0)
    assert df["plant.gap_m"].min() > 0.0


@pytest.mark.req("REQ-AEB-005")
def test_no_activation_below_minimum_speed(run_scenario):
    df = run_scenario(_stationary(8, gap_m=10.0), duration_s=6.0)
    assert set(df["ecu.aeb_state"].dropna()) <= {AebState.OFF, AebState.STANDBY}
    assert (df["ecu.brake_request"].fillna(0) == 0).all()


@pytest.mark.req("REQ-AEB-006")
def test_no_activation_for_receding_object(run_scenario):
    scenario = Scenario(
        ego_speed_mps=50 * KPH,
        initial_gap_m=15.0,
        lead_profile=LeadProfile.CONSTANT_SPEED,
        lead_speed_mps=70 * KPH,
    )
    df = run_scenario(scenario, duration_s=5.0)
    assert set(df["ecu.aeb_state"].dropna()) <= {AebState.OFF, AebState.STANDBY}
