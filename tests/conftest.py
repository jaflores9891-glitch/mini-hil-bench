from pathlib import Path

import pytest

from mini_hil_bench.config import BenchConfig, load_config

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCH = REPO_ROOT / "config" / "bench_virtual.toml"


def pytest_addoption(parser):
    parser.addoption(
        "--bench",
        default=str(DEFAULT_BENCH),
        help="Path to the bench TOML file (default: config/bench_virtual.toml)",
    )


@pytest.fixture(scope="session")
def bench_config(request) -> BenchConfig:
    return load_config(request.config.getoption("--bench"))
