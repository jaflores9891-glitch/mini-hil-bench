"""Longitudinal dynamics of the ego vehicle (explicit Euler integration)."""

from __future__ import annotations

from mini_hil_bench.config import VehicleConfig


class Vehicle:
    """Ego vehicle driven only by the brake: no throttle, no driver input.

    The achieved acceleration follows the requested deceleration through a first-order lag
    and is saturated to the vehicle's braking capability. Speed never becomes negative.

    Args:
        params: Vehicle parameters.
        initial_speed_mps: Initial speed in m/s.
        step_s: Integration step in seconds.
    """

    def __init__(self, params: VehicleConfig, initial_speed_mps: float, step_s: float) -> None:
        """Initialise the vehicle at position 0 with the given speed."""
        self._params = params
        self._step_s = step_s
        self.position_m = 0.0
        self.speed_mps = max(0.0, initial_speed_mps)
        self.accel_mps2 = 0.0

    def step(self, decel_request_mps2: float) -> None:
        """Advance the vehicle by one integration step.

        Args:
            decel_request_mps2: Requested deceleration magnitude (positive = braking).
        """
        target_decel_mps2 = min(max(decel_request_mps2, 0.0), self._params.max_decel_mps2)
        alpha = min(self._step_s / self._params.brake_time_constant_s, 1.0)
        self.accel_mps2 += (-target_decel_mps2 - self.accel_mps2) * alpha
        self.speed_mps = max(0.0, self.speed_mps + self.accel_mps2 * self._step_s)
        if self.speed_mps == 0.0:
            self.accel_mps2 = 0.0
        self.position_m += self.speed_mps * self._step_s
