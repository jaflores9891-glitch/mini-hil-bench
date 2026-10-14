import pytest

from mini_hil_bench.config import RadarConfig, VehicleConfig
from mini_hil_bench.plant.lead_object import LeadObject, LeadProfile
from mini_hil_bench.plant.radar import Radar
from mini_hil_bench.plant.vehicle import Vehicle

STEP_S = 0.01
VEHICLE = VehicleConfig(brake_time_constant_s=0.15, max_decel_mps2=10.0)
RADAR = RadarConfig(noise_std_m=0.05, latency_steps=2, max_range_m=120.0)


def _run(vehicle: Vehicle, decel_mps2: float, steps: int) -> None:
    for _ in range(steps):
        vehicle.step(decel_mps2)


def test_vehicle_without_brake_keeps_constant_speed_and_integrates_position():
    vehicle = Vehicle(VEHICLE, initial_speed_mps=10.0, step_s=STEP_S)
    _run(vehicle, 0.0, 100)
    assert vehicle.speed_mps == pytest.approx(10.0)
    assert vehicle.position_m == pytest.approx(10.0)


def test_vehicle_deceleration_follows_first_order_lag():
    vehicle = Vehicle(VEHICLE, initial_speed_mps=30.0, step_s=STEP_S)
    _run(vehicle, 5.0, 15)  # one time constant
    assert vehicle.accel_mps2 == pytest.approx(-5.0 * 0.63, abs=0.15)
    _run(vehicle, 5.0, 100)
    assert vehicle.accel_mps2 == pytest.approx(-5.0, abs=0.01)


def test_vehicle_deceleration_saturates_at_max_decel():
    vehicle = Vehicle(VEHICLE, initial_speed_mps=40.0, step_s=STEP_S)
    _run(vehicle, 50.0, 200)
    assert vehicle.accel_mps2 == pytest.approx(-VEHICLE.max_decel_mps2, abs=0.01)


def test_vehicle_speed_never_negative():
    vehicle = Vehicle(VEHICLE, initial_speed_mps=1.0, step_s=STEP_S)
    _run(vehicle, 10.0, 300)
    assert vehicle.speed_mps == 0.0
    assert vehicle.accel_mps2 == 0.0


@pytest.mark.parametrize(
    ("profile", "expected_speed_mps"),
    [
        (LeadProfile.STATIONARY, 0.0),
        (LeadProfile.CONSTANT_SPEED, 10.0),
        (LeadProfile.DECELERATING, 6.0),
    ],
)
def test_lead_object_profiles(profile, expected_speed_mps):
    lead = LeadObject(profile, 50.0, speed_mps=10.0, decel_mps2=2.0, step_s=STEP_S)
    for _ in range(200):
        lead.step()
    assert lead.speed_mps == pytest.approx(expected_speed_mps)


def test_radar_noise_is_deterministic_for_a_given_seed():
    def outputs(seed):
        radar = Radar(RADAR, seed=seed)
        radar.sample(30.0, -5.0)
        return [radar.output().distance_m for _ in range(20)]

    assert outputs(7) == outputs(7)
    assert outputs(7) != outputs(8)


def test_radar_applies_latency_in_steps():
    radar = Radar(RadarConfig(noise_std_m=0.0, latency_steps=2, max_range_m=120.0), seed=0)
    for gap_m in (30.0, 29.0, 28.0, 27.0):
        radar.sample(gap_m, -1.0)
    assert radar.output().distance_m == pytest.approx(29.0)


def test_radar_reports_invalid_out_of_range_and_wraps_alive_counter():
    radar = Radar(RADAR, seed=0)
    radar.sample(RADAR.max_range_m + 1.0, -1.0)
    counters = [radar.output() for _ in range(16)]
    assert not counters[0].valid
    assert counters[0].distance_m == 0.0
    assert [m.alive_counter for m in counters] == [*range(1, 16), 0]
