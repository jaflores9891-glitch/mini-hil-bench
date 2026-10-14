from pathlib import Path

import pytest

from mini_hil_bench.config import BenchConfig, load_config

VIRTUAL_TOML = Path(__file__).resolve().parents[2] / "config" / "bench_virtual.toml"


@pytest.fixture(scope="session")
def virtual_config() -> BenchConfig:
    """Unit tests always use the virtual configuration, independent of --bench."""
    return load_config(VIRTUAL_TOML)
