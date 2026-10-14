"""Abstract bench ports, loosely modelled on ASAM XIL (model access and fault injection).

Tests only depend on these interfaces and on logical variable names such as
``ego.speed_mps``; each backend maps those names to its own sources through the
``[variables]`` table of its TOML file.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

import pandas as pd

from mini_hil_bench.bench.faults import Fault
from mini_hil_bench.plant.lead_object import LeadProfile


@dataclass(frozen=True)
class Scenario:
    """Initial conditions of a test scenario (SI units).

    Attributes:
        ego_speed_mps: Initial ego speed.
        initial_gap_m: Initial distance between ego front and object rear.
        lead_profile: Motion profile of the object ahead.
        lead_speed_mps: Initial object speed.
        lead_decel_mps2: Object deceleration for ``LeadProfile.DECELERATING``.
        bus_load_frames_per_step: Filler frames sent on an unrelated ID every step.
    """

    ego_speed_mps: float
    initial_gap_m: float
    lead_profile: LeadProfile = LeadProfile.STATIONARY
    lead_speed_mps: float = 0.0
    lead_decel_mps2: float = 0.0
    bus_load_frames_per_step: int = 0


class ModelAccessPort(ABC):
    """Read, write and capture logical bench variables."""

    @abstractmethod
    def read(self, name: str) -> float:
        """Return the current value of a logical variable.

        Args:
            name: Logical variable name.

        Returns:
            The current value.

        Raises:
            SignalNotFoundError: If the variable is not mapped.
        """

    @abstractmethod
    def write(self, name: str, value: float) -> None:
        """Write a logical variable.

        Args:
            name: Logical variable name.
            value: New value.

        Raises:
            SignalNotFoundError: If the variable is not mapped or not writable.
        """

    @abstractmethod
    def capture(self, names: list[str]) -> pd.DataFrame:
        """Return the history of variables since the scenario was loaded.

        Args:
            names: Logical variable names.

        Returns:
            A DataFrame with a ``time_s`` column and one column per variable.

        Raises:
            SignalNotFoundError: If a variable is not mapped.
        """


class FaultInjectionPort(ABC):
    """Inject and clear faults on the communication between plant and ECU."""

    @abstractmethod
    def inject(self, fault: Fault) -> None:
        """Activate a fault.

        Args:
            fault: Fault to activate.
        """

    @abstractmethod
    def clear(self, fault: Fault) -> None:
        """Deactivate a fault.

        Args:
            fault: Fault to deactivate.
        """

    @abstractmethod
    def clear_all(self) -> None:
        """Deactivate every active fault."""


class Bench(ABC):
    """A test bench: owns the ports and drives simulated time.

    Use it as a context manager so that it is always stopped::

        with create_bench(config) as bench:
            bench.load_scenario(Scenario(ego_speed_mps=10.0, initial_gap_m=50.0))
            bench.run_for(5.0)
    """

    @property
    @abstractmethod
    def model(self) -> ModelAccessPort:
        """Model access port."""

    @property
    @abstractmethod
    def faults(self) -> FaultInjectionPort:
        """Fault injection port."""

    @property
    @abstractmethod
    def log_path(self) -> Path:
        """Path of the CAN log (BLF) recorded while the bench runs."""

    @abstractmethod
    def start(self) -> None:
        """Connect to the bench (buses, logging)."""

    @abstractmethod
    def stop(self) -> None:
        """Disconnect from the bench and flush logs. Must be idempotent."""

    @abstractmethod
    def load_scenario(self, scenario: Scenario) -> None:
        """Reset plant and ECU to the initial conditions of a scenario.

        Args:
            scenario: Scenario to load.
        """

    @abstractmethod
    def run_for(self, seconds: float) -> None:
        """Advance simulated time.

        Args:
            seconds: Duration to simulate.
        """

    def __enter__(self) -> Bench:
        """Start the bench and return it."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop the bench, even if the body raised."""
        self.stop()
