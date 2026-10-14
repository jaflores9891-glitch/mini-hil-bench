"""CAN database access: load the DBC and encode/decode frames with cantools."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import can
import cantools
from cantools.database.can import Database, Message

from mini_hil_bench.exceptions import BenchConfigError, SignalNotFoundError

KPH_PER_MPS = 3.6
MS_PER_S = 1000.0


class CanDatabase:
    """Thin wrapper around a cantools database with project-specific errors.

    Args:
        dbc_path: Path to the DBC file.

    Raises:
        BenchConfigError: If the DBC file cannot be loaded.
    """

    def __init__(self, dbc_path: str | Path) -> None:
        """Load the DBC file."""
        try:
            db = cantools.database.load_file(str(dbc_path))
        except (OSError, cantools.database.UnsupportedDatabaseFormatError) as err:
            raise BenchConfigError(f"Cannot load DBC {dbc_path}: {err}") from err
        if not isinstance(db, Database):
            raise BenchConfigError(f"{dbc_path} is not a CAN database")
        self._db = db

    def _message(self, name: str) -> Message:
        try:
            return self._db.get_message_by_name(name)
        except KeyError as err:
            raise SignalNotFoundError(f"Unknown CAN message: {name}") from err

    def frame_id(self, message_name: str) -> int:
        """Return the arbitration ID of a message.

        Args:
            message_name: DBC message name.

        Returns:
            The CAN arbitration ID.
        """
        return self._message(message_name).frame_id

    def cycle_time_s(self, message_name: str) -> float:
        """Return the cycle time of a message from its ``GenMsgCycleTime`` attribute.

        Args:
            message_name: DBC message name.

        Returns:
            The cycle time in seconds.

        Raises:
            BenchConfigError: If the message has no cycle time.
        """
        cycle_ms = self._message(message_name).cycle_time
        if not cycle_ms:
            raise BenchConfigError(f"Message {message_name} has no GenMsgCycleTime")
        return cycle_ms / MS_PER_S

    def signal_names(self, message_name: str) -> list[str]:
        """Return the signal names of a message.

        Args:
            message_name: DBC message name.

        Returns:
            Signal names in DBC order.
        """
        return [signal.name for signal in self._message(message_name).signals]

    def message_name(self, frame_id: int) -> str | None:
        """Return the message name for an ID, or None if the ID is not in the DBC.

        Args:
            frame_id: CAN arbitration ID.

        Returns:
            The message name, or None for unknown IDs.
        """
        try:
            return self._db.get_message_by_frame_id(frame_id).name
        except KeyError:
            return None

    def encode(
        self, message_name: str, signals: Mapping[str, float], timestamp_s: float = 0.0
    ) -> can.Message:
        """Encode physical signal values into a CAN frame.

        Args:
            message_name: DBC message name.
            signals: Physical value per signal; every signal of the message is required.
            timestamp_s: Timestamp to store in the frame.

        Returns:
            The encoded frame.

        Raises:
            SignalNotFoundError: If the message or a signal is unknown or missing.
        """
        message = self._message(message_name)
        missing = set(self.signal_names(message_name)) - set(signals)
        unknown = set(signals) - set(self.signal_names(message_name))
        if missing or unknown:
            raise SignalNotFoundError(
                f"{message_name}: missing signals {sorted(missing)}, unknown {sorted(unknown)}"
            )
        data = message.encode(dict(signals), scaling=True, strict=False)
        return can.Message(
            arbitration_id=message.frame_id,
            data=data,
            is_extended_id=False,
            timestamp=timestamp_s,
        )

    def decode(self, frame: can.Message) -> tuple[str, dict[str, float]]:
        """Decode a CAN frame into physical signal values.

        Args:
            frame: Received frame.

        Returns:
            The message name and a mapping of signal name to physical value.

        Raises:
            SignalNotFoundError: If the frame ID is not in the DBC.
        """
        name = self.message_name(frame.arbitration_id)
        if name is None:
            raise SignalNotFoundError(f"Unknown CAN ID: 0x{frame.arbitration_id:X}")
        decoded = self._message(name).decode(bytes(frame.data), decode_choices=False)
        return name, {key: float(value) for key, value in decoded.items()}
