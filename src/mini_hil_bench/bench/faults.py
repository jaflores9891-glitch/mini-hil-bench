"""Fault definitions for CAN-level fault injection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mini_hil_bench.exceptions import FaultConfigError


class FaultType(Enum):
    """Kinds of faults the bench can inject on a CAN message."""

    DROP = "drop"  # drop the next `count` frames
    FREEZE = "freeze"  # hold a signal at `value`, or at its value when the fault starts
    OFFSET = "offset"  # add `value` to a signal
    DELAY = "delay"  # deliver every frame `count` scheduler steps late
    SILENCE = "silence"  # drop every frame of the message


@dataclass(frozen=True)
class Fault:
    """One fault applied to a DBC message (and optionally one of its signals).

    Attributes:
        kind: Fault type.
        message: DBC message name.
        signal: Signal name (required for FREEZE and OFFSET).
        value: Offset (OFFSET) or frozen value (FREEZE, optional).
        count: Frames to drop (DROP) or steps of delay (DELAY).

    Raises:
        FaultConfigError: If the combination of fields is inconsistent.
    """

    kind: FaultType
    message: str
    signal: str | None = None
    value: float | None = None
    count: int = 1

    def __post_init__(self) -> None:
        """Validate the field combination."""
        if self.kind in (FaultType.FREEZE, FaultType.OFFSET) and self.signal is None:
            raise FaultConfigError(f"{self.kind.name} fault needs a signal")
        if self.kind is FaultType.OFFSET and self.value is None:
            raise FaultConfigError("OFFSET fault needs a value")
        if self.count < 1:
            raise FaultConfigError("count must be >= 1")
