import itertools
import math

import can
import pytest

from mini_hil_bench.can_db import KPH_PER_MPS, CanDatabase
from mini_hil_bench.ecu.aeb_ecu import AebEcu, AebState, time_to_collision_s

STEP_S = 0.01
_channel_ids = itertools.count()


class EcuHarness:
    """Feeds CAN frames to the ECU over a private virtual bus and reads its commands."""

    def __init__(self, config):
        channel = f"unit-ecu-{next(_channel_ids)}"
        self.db = CanDatabase(config.can.dbc_path)
        self.tester = can.Bus(interface="virtual", channel=channel)
        self.ecu_bus = can.Bus(interface="virtual", channel=channel)
        self.ecu = AebEcu(config.ecu, self.db, self.ecu_bus)
        self.now_s = 0.0
        self.alive = 0

    def close(self):
        self.tester.shutdown()
        self.ecu_bus.shutdown()

    def cycle(self, speed_kph, distance_m=0.0, rel_speed_mps=0.0, valid=True, alive_step=1):
        self.alive = (self.alive + alive_step) % 16
        self.tester.send(self.db.encode("VehicleState", {"EgoSpeed": speed_kph, "EgoAccel": 0}))
        radar = {
            "ObjDistance": distance_m,
            "ObjRelSpeed": rel_speed_mps,
            "ObjValid": int(valid),
            "RadarAliveCounter": self.alive,
        }
        self.tester.send(self.db.encode("RadarObject", radar))
        return self.step()

    def step(self):
        self.ecu.step(self.now_s)
        self.now_s += STEP_S
        _, command = self.db.decode(self.tester.recv(timeout=0))
        return command


@pytest.fixture
def harness(virtual_config):
    h = EcuHarness(virtual_config)
    yield h
    h.close()


def _distance_for_ttc(ttc_s, closing_mps):
    return ttc_s * closing_mps


def test_ttc_is_infinite_when_object_not_closing():
    assert time_to_collision_s(20.0, 0.0) == math.inf
    assert time_to_collision_s(20.0, 2.0) == math.inf
    assert time_to_collision_s(20.0, -10.0) == pytest.approx(2.0)


def test_ecu_starts_off_and_goes_to_standby_on_vehicle_state(harness):
    assert harness.step()["AebState"] == AebState.OFF
    assert harness.cycle(50.0, 100.0, 0.0)["AebState"] == AebState.STANDBY


@pytest.mark.parametrize(
    ("ttc_s", "expected_state", "expected_decel"),
    [
        (3.0, AebState.STANDBY, 0.0),
        (2.5, AebState.WARNING, 0.0),
        (1.5, AebState.PARTIAL_BRAKE, 4.0),
        (0.8, AebState.FULL_BRAKE, 9.0),
    ],
)
def test_ecu_state_follows_ttc_thresholds(harness, ttc_s, expected_state, expected_decel):
    closing_mps = 50.0 / KPH_PER_MPS
    command = harness.cycle(50.0, _distance_for_ttc(ttc_s, closing_mps), -closing_mps)
    assert command["AebState"] == expected_state
    assert command["DecelRequest"] == pytest.approx(expected_decel)
    assert command["BrakeRequest"] == (expected_decel > 0)


def test_ecu_inactive_below_min_speed(harness):
    command = harness.cycle(9.0, 0.5, -2.5)
    assert command["AebState"] == AebState.STANDBY


def test_ecu_ignores_invalid_or_receding_object(harness):
    assert harness.cycle(50.0, 5.0, -13.0, valid=False)["AebState"] == AebState.STANDBY
    assert harness.cycle(50.0, 5.0, +3.0)["AebState"] == AebState.STANDBY


def test_ecu_holds_brake_until_standstill(harness):
    harness.cycle(50.0, 10.0, -13.9)
    assert harness.cycle(5.0, 4.0, -1.4)["AebState"] == AebState.FULL_BRAKE
    assert harness.cycle(0.0, 3.9, 0.0)["AebState"] == AebState.STANDBY


def test_ecu_faults_on_radar_timeout_and_does_not_brake(harness):
    harness.cycle(50.0, 10.0, -13.9)
    for _ in range(11):
        harness.tester.send(harness.db.encode("VehicleState", {"EgoSpeed": 50, "EgoAccel": 0}))
        command = harness.step()
    assert command["AebState"] == AebState.FAULT
    assert command["DecelRequest"] == 0.0
    assert command["BrakeRequest"] == 0


def test_ecu_faults_on_frozen_alive_counter(harness):
    harness.cycle(50.0, 100.0, 0.0)
    states = [harness.cycle(50.0, 100.0, 0.0, alive_step=0)["AebState"] for _ in range(3)]
    assert states == [AebState.STANDBY, AebState.STANDBY, AebState.FAULT]


def test_ecu_ignores_unknown_can_ids(harness):
    harness.tester.send(can.Message(arbitration_id=0x050, data=bytes(8), is_extended_id=False))
    assert harness.cycle(50.0, 100.0, 0.0)["AebState"] == AebState.STANDBY
