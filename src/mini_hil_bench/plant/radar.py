"""Front radar model: Gaussian range noise, fixed latency, maximum range and alive counter."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from mini_hil_bench.config import RadarConfig

ALIVE_COUNTER_MODULO = 16


@dataclass(frozen=True)
class RadarMeasurement:
    """One radar output sample, in SI units.

    Attributes:
        distance_m: Measured distance to the object (0 when invalid).
        rel_speed_mps: Object speed minus ego speed (negative = closing).
        valid: True when the object is within the radar's range.
        alive_counter: Rolling counter, incremented on every output.
    """

    distance_m: float
    rel_speed_mps: float
    valid: bool
    alive_counter: int


class Radar:
    """Radar sensor model.

    The ground truth is sampled every scheduler step into a delay line; ``output()`` returns
    the sample from ``latency_steps`` steps ago with Gaussian noise on the distance.

    Args:
        params: Radar parameters.
        seed: Seed of the noise generator (makes the noise reproducible).
    """

    def __init__(self, params: RadarConfig, seed: int) -> None:
        """Initialise the radar with an empty delay line."""
        self._params = params
        self._rng = np.random.default_rng(seed)
        self._delay_line: deque[tuple[float, float]] = deque(maxlen=params.latency_steps + 1)
        self._alive_counter = 0

    def sample(self, gap_m: float, rel_speed_mps: float) -> None:
        """Store the ground truth of the current step.

        Args:
            gap_m: True distance between ego front and object rear.
            rel_speed_mps: True object speed minus ego speed.
        """
        self._delay_line.append((gap_m, rel_speed_mps))

    def output(self) -> RadarMeasurement:
        """Produce the measurement to transmit now.

        Returns:
            The delayed, noisy measurement.

        Raises:
            ValueError: If ``sample()`` was never called.
        """
        if not self._delay_line:
            raise ValueError("Radar.output() called before any sample()")
        gap_m, rel_speed_mps = self._delay_line[0]
        noisy_gap_m = gap_m + float(self._rng.normal(0.0, self._params.noise_std_m))
        valid = 0.0 < gap_m <= self._params.max_range_m
        self._alive_counter = (self._alive_counter + 1) % ALIVE_COUNTER_MODULO
        return RadarMeasurement(
            distance_m=max(noisy_gap_m, 0.0) if valid else 0.0,
            rel_speed_mps=rel_speed_mps if valid else 0.0,
            valid=valid,
            alive_counter=self._alive_counter,
        )
