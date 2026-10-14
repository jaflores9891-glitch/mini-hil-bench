from collections.abc import Callable, Iterable
from pathlib import Path

import pandas as pd
import pytest

from mini_hil_bench.bench.factory import create_bench
from mini_hil_bench.bench.faults import Fault
from mini_hil_bench.bench.ports import Bench, Scenario
from mini_hil_bench.config import BenchConfig, load_config

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCH = REPO_ROOT / "config" / "bench_virtual.toml"
CAPTURED = [
    "ego.speed_mps",
    "plant.gap_m",
    "plant.ttc_s",
    "radar.valid",
    "ecu.aeb_state",
    "ecu.decel_request_mps2",
    "ecu.brake_request",
]

RunScenario = Callable[..., pd.DataFrame]


def pytest_addoption(parser):
    parser.addoption(
        "--bench",
        default=str(DEFAULT_BENCH),
        help="Path to the bench TOML file (default: config/bench_virtual.toml)",
    )


@pytest.fixture(scope="session")
def bench_config(request) -> BenchConfig:
    return load_config(request.config.getoption("--bench"))


@pytest.fixture
def bench(request, bench_config) -> Bench:
    """A started bench per test; its BLF log is named after the test."""
    with create_bench(bench_config, request.node.name) as started_bench:
        yield started_bench


@pytest.fixture
def run_scenario(bench) -> RunScenario:
    """Load a scenario, inject faults from t=0, run it and return the captured signals."""

    def _run(scenario: Scenario, duration_s: float, faults: Iterable[Fault] = ()) -> pd.DataFrame:
        bench.load_scenario(scenario)
        for fault in faults:
            bench.faults.inject(fault)
        bench.run_for(duration_s)
        return bench.model.capture(CAPTURED)

    return _run


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    requirements = [req for marker in item.iter_markers("req") for req in marker.args]
    report.requirements = ", ".join(requirements)
    if call.when == "call" and requirements:
        item.user_properties.append(("requirements", report.requirements))


def pytest_html_results_table_header(cells):
    cells.insert(2, "<th>Requirements</th>")


def pytest_html_results_table_row(report, cells):
    cells.insert(2, f"<td>{getattr(report, 'requirements', '')}</td>")
