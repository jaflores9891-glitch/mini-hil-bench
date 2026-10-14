import can
import pytest

from mini_hil_bench.can_db import CanDatabase
from mini_hil_bench.exceptions import BenchConfigError, SignalNotFoundError


@pytest.fixture
def db(virtual_config):
    return CanDatabase(virtual_config.can.dbc_path)


@pytest.mark.parametrize(
    ("message", "signals"),
    [
        ("VehicleState", {"EgoSpeed": 87.65, "EgoAccel": -8.765}),
        (
            "RadarObject",
            {"ObjDistance": 42.42, "ObjRelSpeed": -13.37, "ObjValid": 1, "RadarAliveCounter": 15},
        ),
        ("AebCommand", {"AebState": 4, "DecelRequest": 9.0, "BrakeRequest": 1}),
    ],
)
def test_encode_decode_round_trip_preserves_physical_values(db, message, signals):
    frame = db.encode(message, signals, timestamp_s=1.23)
    assert frame.arbitration_id == db.frame_id(message)
    assert frame.timestamp == pytest.approx(1.23)
    name, decoded = db.decode(frame)
    assert name == message
    assert decoded == pytest.approx(signals, abs=1e-3)


def test_cycle_times_come_from_dbc_attributes(db):
    assert db.cycle_time_s("VehicleState") == pytest.approx(0.010)
    assert db.cycle_time_s("RadarObject") == pytest.approx(0.020)
    assert db.cycle_time_s("AebCommand") == pytest.approx(0.010)


def test_encode_with_missing_signal_raises(db):
    with pytest.raises(SignalNotFoundError):
        db.encode("VehicleState", {"EgoSpeed": 10.0})


def test_unknown_message_and_unknown_id_raise(db):
    with pytest.raises(SignalNotFoundError):
        db.frame_id("NoSuchMessage")
    with pytest.raises(SignalNotFoundError):
        db.decode(can.Message(arbitration_id=0x7FF, data=bytes(8), is_extended_id=False))
    assert db.message_name(0x7FF) is None


def test_missing_dbc_file_raises_config_error(tmp_path):
    with pytest.raises(BenchConfigError):
        CanDatabase(tmp_path / "missing.dbc")
