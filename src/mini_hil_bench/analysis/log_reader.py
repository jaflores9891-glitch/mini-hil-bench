"""Read BLF CAN logs into pandas DataFrames decoded with the DBC."""

from __future__ import annotations

import logging
from pathlib import Path

import can
import pandas as pd

from mini_hil_bench.can_db import CanDatabase

logger = logging.getLogger(__name__)


def read_blf(log_path: str | Path, can_db: CanDatabase) -> pd.DataFrame:
    """Decode every DBC frame of a BLF log.

    Frames whose ID is not in the DBC (e.g. bus-load filler) are counted and skipped.

    Args:
        log_path: Path to the ``.blf`` file.
        can_db: Database used to decode the frames.

    Returns:
        One row per decoded frame with columns ``time_s`` (seconds since the first frame),
        ``message`` and one column per DBC signal (NaN for signals of other messages).
    """
    rows: list[dict[str, float | str]] = []
    skipped = 0
    start_s: float | None = None
    with can.BLFReader(str(log_path)) as reader:
        for frame in reader:
            start_s = frame.timestamp if start_s is None else start_s
            if can_db.message_name(frame.arbitration_id) is None:
                skipped += 1
                continue
            name, signals = can_db.decode(frame)
            rows.append({"time_s": frame.timestamp - start_s, "message": name, **signals})
    logger.debug("Read %d frames from %s (%d unknown skipped)", len(rows), log_path, skipped)
    columns = [sig for msg in can_db.message_names() for sig in can_db.signal_names(msg)]
    return pd.DataFrame(rows, columns=["time_s", "message", *columns])
