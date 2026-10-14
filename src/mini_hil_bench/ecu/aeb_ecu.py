"""Virtual AEB ECU: time-to-collision state machine that talks only over CAN."""

from __future__ import annotations

import logging
import math
from enum import IntEnum

import can

from mini_hil_bench.can_db import KPH_PER_MPS, CanDatabase
from mini_hil_bench.config import EcuConfig

logger = logging.getLogger(__name__)


class AebState(IntEnum):
    """AEB function state; values match the ``AebState`` VAL_ table of the DBC."""

    OFF = 0
    STANDBY = 1
    WARNING = 2
    PARTIAL_BRAKE = 3
    FULL_BRAKE = 4
    FAULT = 5


BRAKING_STATES = (AebState.PARTIAL_BRAKE, AebState.FULL_BRAKE)


def time_to_collision_s(distance_m: float, rel_speed_mps: float) -> float:
    """Compute the time to collision.

    Args:
        distance_m: Distance to the object.
        rel_speed_mps: Object speed minus ego speed (negative = closing).

    Returns:
        ``distance / closing speed`` when closing, otherwise ``math.inf``.
    """
    closing_speed_mps = -rel_speed_mps
    if closing_speed_mps <= 0.0:
        return math.inf
    return distance_m / closing_speed_mps


class AebEcu:
    """AEB ECU connected to a CAN bus.

    Every call to ``step()`` drains the receive queue, runs diagnostics and the state
    machine, and transmits one ``AebCommand`` frame. The ECU has no access to the plant.

    State logic:
        * ``OFF`` until the first ``VehicleState`` frame is received.
        * ``FAULT`` (latched, no braking) on radar timeout or frozen alive counter.
        * Otherwise the TTC selects ``STANDBY``/``WARNING``/``PARTIAL_BRAKE``/``FULL_BRAKE``,
          only above the minimum speed and for a valid, closing object.
        * A brake state never de-escalates while the object is still closing and the ego
          is moving (brake to standstill).

    Args:
        params: ECU calibration.
        can_db: CAN database used to encode/decode frames.
        bus: Bus the ECU is connected to.
    """

    def __init__(self, params: EcuConfig, can_db: CanDatabase, bus: can.BusABC) -> None:
        """Initialise the ECU in state ``OFF``."""
        self._params = params
        self._db = can_db
        self._bus = bus
        self.state = AebState.OFF
        self._ego_speed_mps = 0.0
        self._vehicle_seen = False
        self._distance_m = 0.0
        self._rel_speed_mps = 0.0
        self._obj_valid = False
        self._last_radar_rx_s = 0.0
        self._last_alive_counter: int | None = None
        self._alive_repeats = 0

    def step(self, now_s: float) -> None:
        """Run one ECU cycle at simulated time ``now_s``.

        Args:
            now_s: Current simulated time in seconds.
        """
        while (frame := self._bus.recv(timeout=0)) is not None:
            self._on_frame(frame, now_s)
        self._update_state(now_s)
        decel_mps2 = self._decel_request_mps2()
        command = self._db.encode(
            "AebCommand",
            {
                "AebState": int(self.state),
                "DecelRequest": decel_mps2,
                "BrakeRequest": int(decel_mps2 > 0.0),
            },
            timestamp_s=now_s,
        )
        self._bus.send(command)

    def _on_frame(self, frame: can.Message, now_s: float) -> None:
        name = self._db.message_name(frame.arbitration_id)
        if name == "VehicleState":
            _, signals = self._db.decode(frame)
            self._ego_speed_mps = signals["EgoSpeed"] / KPH_PER_MPS
            self._vehicle_seen = True
        elif name == "RadarObject":
            _, signals = self._db.decode(frame)
            self._on_radar(signals, now_s)

    def _on_radar(self, signals: dict[str, float], now_s: float) -> None:
        self._last_radar_rx_s = now_s
        self._distance_m = signals["ObjDistance"]
        self._rel_speed_mps = signals["ObjRelSpeed"]
        self._obj_valid = bool(signals["ObjValid"])
        counter = int(signals["RadarAliveCounter"])
        same = counter == self._last_alive_counter
        self._alive_repeats = self._alive_repeats + 1 if same else 0
        self._last_alive_counter = counter

    def _diagnose(self, now_s: float) -> str:
        if now_s - self._last_radar_rx_s > self._params.radar_timeout_s:
            return "radar timeout"
        if self._alive_repeats >= self._params.alive_counter_max_repeats:
            return "radar alive counter frozen"
        return ""

    def _update_state(self, now_s: float) -> None:
        if self.state is AebState.FAULT:
            return
        reason = self._diagnose(now_s)
        if reason:
            logger.warning("AEB FAULT at t=%.2f s: %s", now_s, reason)
            self.state = AebState.FAULT
        elif self._vehicle_seen:
            self.state = self._next_state()

    def _object_closing(self) -> bool:
        return self._obj_valid and self._rel_speed_mps < 0.0

    def _ttc_state(self) -> AebState:
        p = self._params
        if self._ego_speed_mps < p.min_speed_mps or not self._object_closing():
            return AebState.STANDBY
        ttc_s = time_to_collision_s(self._distance_m, self._rel_speed_mps)
        if ttc_s < p.ttc_full_s:
            return AebState.FULL_BRAKE
        if ttc_s < p.ttc_partial_s:
            return AebState.PARTIAL_BRAKE
        if ttc_s < p.ttc_warning_s:
            return AebState.WARNING
        return AebState.STANDBY

    def _next_state(self) -> AebState:
        target = self._ttc_state()
        hold_brake = (
            self.state in BRAKING_STATES
            and self._object_closing()
            and self._ego_speed_mps > self._params.standstill_speed_mps
        )
        if hold_brake and target < self.state:
            return self.state
        return target

    def _decel_request_mps2(self) -> float:
        if self.state is AebState.FULL_BRAKE:
            return self._params.full_decel_mps2
        if self.state is AebState.PARTIAL_BRAKE:
            return self._params.partial_decel_mps2
        return 0.0
