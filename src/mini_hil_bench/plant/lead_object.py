"""Object ahead of the ego vehicle with simple motion profiles."""

from __future__ import annotations

from enum import Enum


class LeadProfile(Enum):
    """Motion profile of the lead object."""

    STATIONARY = "stationary"
    CONSTANT_SPEED = "constant_speed"
    DECELERATING = "decelerating"


class LeadObject:
    """Point-mass object moving along the ego lane.

    Args:
        profile: Motion profile.
        initial_position_m: Initial position of the object's rear, in the ego frame (m).
        speed_mps: Initial speed (ignored for ``STATIONARY``).
        decel_mps2: Deceleration magnitude for ``DECELERATING``.
        step_s: Integration step in seconds.
    """

    def __init__(
        self,
        profile: LeadProfile,
        initial_position_m: float,
        speed_mps: float,
        decel_mps2: float,
        step_s: float,
    ) -> None:
        """Initialise the object."""
        self.profile = profile
        self.position_m = initial_position_m
        self.speed_mps = 0.0 if profile is LeadProfile.STATIONARY else max(0.0, speed_mps)
        self._decel_mps2 = decel_mps2 if profile is LeadProfile.DECELERATING else 0.0
        self._step_s = step_s

    def step(self) -> None:
        """Advance the object by one integration step."""
        self.speed_mps = max(0.0, self.speed_mps - self._decel_mps2 * self._step_s)
        self.position_m += self.speed_mps * self._step_s
