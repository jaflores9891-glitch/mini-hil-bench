import math

import pytest

from mini_hil_bench.analysis.log_reader import read_blf
from mini_hil_bench.bench.ports import Scenario
from mini_hil_bench.can_db import CanDatabase
from mini_hil_bench.ecu.aeb_ecu import AebState

CRUISE = Scenario(ego_speed_mps=50 / 3.6, initial_gap_m=500.0)

pytestmark = pytest.mark.smoke


def test_bench_starts_and_signals_of_all_three_messages_are_received(bench):
    bench.load_scenario(CRUISE)
    bench.run_for(0.5)
    assert not math.isnan(bench.model.read("bus.ego_speed_kph"))  # VehicleState
    assert not math.isnan(bench.model.read("radar.distance_m"))  # RadarObject
    assert not math.isnan(bench.model.read("ecu.aeb_state"))  # AebCommand


def test_ecu_reaches_standby_while_cruising_without_target(bench):
    bench.load_scenario(CRUISE)
    bench.run_for(0.5)
    assert bench.model.read("ecu.aeb_state") == AebState.STANDBY
    assert bench.model.read("ecu.brake_request") == 0


def test_model_variables_can_be_written_and_read_back(bench):
    bench.load_scenario(CRUISE)
    bench.model.write("ego.speed_mps", 20.0)
    bench.run_for(0.1)
    assert bench.model.read("ego.speed_mps") == pytest.approx(20.0)
    assert bench.model.read("bus.ego_speed_kph") == pytest.approx(72.0, abs=0.01)


def test_blf_log_contains_traffic_on_all_three_ids(bench, bench_config):
    bench.load_scenario(CRUISE)
    bench.run_for(1.0)
    bench.stop()
    df = read_blf(bench.log_path, CanDatabase(bench_config.can.dbc_path))
    counts = df["message"].value_counts()
    assert counts["VehicleState"] == 100
    assert counts["AebCommand"] == 100
    assert counts["RadarObject"] == 50
    assert df["time_s"].iloc[-1] == pytest.approx(0.99)
