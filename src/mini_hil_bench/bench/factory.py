"""Create a bench from a configuration file."""

from __future__ import annotations

from pathlib import Path

from mini_hil_bench.bench.backends.virtual import VirtualBench
from mini_hil_bench.bench.ports import Bench
from mini_hil_bench.config import BenchConfig, load_config
from mini_hil_bench.exceptions import BenchConfigError


def create_bench(config: BenchConfig | str | Path, test_name: str = "bench") -> Bench:
    """Instantiate the backend selected by the configuration.

    Args:
        config: Loaded configuration or path to a TOML file.
        test_name: Name used for log files.

    Returns:
        A bench that is not yet started.

    Raises:
        BenchConfigError: If the backend is not available.
    """
    if not isinstance(config, BenchConfig):
        config = load_config(config)
    if config.backend == "virtual":
        return VirtualBench(config, test_name)
    if config.backend == "dspace":
        raise BenchConfigError(
            "The dSPACE backend is a non-validated template (no dSPACE license available). "
            "Implement mini_hil_bench.bench.backends.dspace before using bench_dspace.toml."
        )
    raise BenchConfigError(f"Unsupported backend: {config.backend!r}")
