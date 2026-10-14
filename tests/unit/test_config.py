from pathlib import Path

import pytest

from mini_hil_bench.bench.backends.dspace import DspaceBench
from mini_hil_bench.bench.factory import create_bench
from mini_hil_bench.config import load_config
from mini_hil_bench.exceptions import BenchConfigError

REPO_ROOT = Path(__file__).resolve().parents[2]
VIRTUAL_TOML = REPO_ROOT / "config" / "bench_virtual.toml"


def test_virtual_config_loads_with_resolved_paths():
    config = load_config(VIRTUAL_TOML)
    assert config.backend == "virtual"
    assert config.simulation.step_s == pytest.approx(0.01)
    assert config.can is not None
    assert config.can.dbc_path == REPO_ROOT / "dbc" / "aeb.dbc"
    assert config.ecu.ttc_warning_s > config.ecu.ttc_partial_s > config.ecu.ttc_full_s
    assert config.variables["ecu.aeb_state"] == "can:AebCommand.AebState"


def _write_variant(tmp_path: Path, old: str, new: str) -> Path:
    text = VIRTUAL_TOML.read_text(encoding="utf-8")
    assert old in text
    target = tmp_path / "bench.toml"
    target.write_text(text.replace(old, new), encoding="utf-8")
    return target


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('backend = "virtual"', 'backend = "unknown"'),
        ("ttc_full_s = 0.9", "ttc_full_s = 3.0"),
        ("seed = 42", 'seed = "forty-two"'),
        ("seed = 42", "seed = 42\nunexpected_key = 1"),
        ("[radar]", "[radar_typo]"),
        ("step_s = 0.01", "step_s = 0.01 = 2"),
    ],
    ids=["bad-backend", "ttc-order", "wrong-type", "unknown-key", "missing-section", "bad-toml"],
)
def test_invalid_config_raises_bench_config_error(tmp_path, old, new):
    with pytest.raises(BenchConfigError):
        load_config(_write_variant(tmp_path, old, new))


def test_missing_config_file_raises_bench_config_error(tmp_path):
    with pytest.raises(BenchConfigError, match="not found"):
        load_config(tmp_path / "missing.toml")


def test_dspace_template_config_loads_and_factory_refuses_it():
    config = load_config(REPO_ROOT / "config" / "bench_dspace.toml")
    assert config.backend == "dspace"
    assert config.dspace is not None
    assert config.can is None
    assert set(config.variables) == set(load_config(VIRTUAL_TOML).variables)
    with pytest.raises(BenchConfigError, match="non-validated template"):
        create_bench(config)


def test_dspace_template_methods_raise_not_implemented():
    bench = DspaceBench(load_config(REPO_ROOT / "config" / "bench_dspace.toml"))
    with pytest.raises(NotImplementedError, match="non-validated"):
        bench.start()
    with pytest.raises(NotImplementedError):
        bench.model.read("ego.speed_mps")
