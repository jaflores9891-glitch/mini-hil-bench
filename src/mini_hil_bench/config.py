"""Load bench configuration files (TOML) and validate them into frozen dataclasses."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, TypeVar

from mini_hil_bench.exceptions import BenchConfigError

SUPPORTED_BACKENDS = ("virtual", "dspace")

_ConfigT = TypeVar("_ConfigT")


@dataclass(frozen=True)
class SimulationConfig:
    """Fixed-step scheduler settings.

    Attributes:
        step_s: Scheduler step in seconds.
        seed: Seed for every random number generator in the plant.
        real_time: If True, the scheduler waits so that simulated time follows wall time.
    """

    step_s: float
    seed: int
    real_time: bool = False


@dataclass(frozen=True)
class CanConfig:
    """CAN database, virtual bus and logging settings (paths are absolute after loading)."""

    dbc_path: Path
    channel_prefix: str
    log_dir: Path


@dataclass(frozen=True)
class VehicleConfig:
    """Ego vehicle longitudinal dynamics parameters."""

    brake_time_constant_s: float
    max_decel_mps2: float


@dataclass(frozen=True)
class RadarConfig:
    """Radar sensor model parameters."""

    noise_std_m: float
    latency_steps: int
    max_range_m: float


@dataclass(frozen=True)
class EcuConfig:
    """AEB ECU calibration: activation thresholds, braking levels and diagnostics."""

    min_speed_mps: float
    standstill_speed_mps: float
    ttc_warning_s: float
    ttc_partial_s: float
    ttc_full_s: float
    partial_decel_mps2: float
    full_decel_mps2: float
    radar_timeout_s: float
    alive_counter_max_repeats: int


@dataclass(frozen=True)
class DspaceConfig:
    """Connection settings for the (template) dSPACE backend."""

    platform: str
    xil_port_config: Path


@dataclass(frozen=True)
class BenchConfig:
    """Complete bench configuration.

    Attributes:
        backend: Backend name, one of ``SUPPORTED_BACKENDS``.
        simulation: Scheduler settings.
        ecu: ECU calibration (also the expected values used by the tests).
        variables: Logical variable name -> backend-specific source (variable mapping).
        can: CAN settings (virtual backend only).
        vehicle: Vehicle model (virtual backend only).
        radar: Radar model (virtual backend only).
        dspace: dSPACE settings (dSPACE backend only).
    """

    backend: str
    simulation: SimulationConfig
    ecu: EcuConfig
    variables: dict[str, str]
    can: CanConfig | None = None
    vehicle: VehicleConfig | None = None
    radar: RadarConfig | None = None
    dspace: DspaceConfig | None = None


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    section = data.get(name)
    if not isinstance(section, dict):
        raise BenchConfigError(f"Missing or invalid section [{name}]")
    return section


def _build(cls: type[_ConfigT], data: dict[str, Any], name: str) -> _ConfigT:
    """Build a config dataclass from a TOML section, checking keys and value types.

    Args:
        cls: Dataclass type to build.
        data: Whole TOML document.
        name: Section name.

    Returns:
        The populated dataclass instance.

    Raises:
        BenchConfigError: If keys are missing/unknown or a value has the wrong type.
    """
    section = _section(data, name)
    declared = {f.name: f.type for f in fields(cls)}
    unknown = set(section) - set(declared)
    if unknown:
        raise BenchConfigError(f"Unknown keys in [{name}]: {sorted(unknown)}")
    for key, value in section.items():
        is_number = isinstance(value, int | float) and not isinstance(value, bool)
        expected_ok = {
            "float": is_number,
            "int": is_number and isinstance(value, int),
            "bool": isinstance(value, bool),
        }.get(str(declared[key]), isinstance(value, str))
        if not expected_ok:
            raise BenchConfigError(f"[{name}].{key} has invalid type: {value!r}")
    try:
        return cls(**section)
    except TypeError as err:
        raise BenchConfigError(f"Invalid section [{name}]: {err}") from err


def _validate_ecu(ecu: EcuConfig) -> None:
    if not ecu.ttc_warning_s > ecu.ttc_partial_s > ecu.ttc_full_s > 0:
        raise BenchConfigError("TTC thresholds must satisfy warning > partial > full > 0")
    if not 0 < ecu.partial_decel_mps2 <= ecu.full_decel_mps2:
        raise BenchConfigError("Decelerations must satisfy 0 < partial <= full")
    if ecu.radar_timeout_s <= 0 or ecu.alive_counter_max_repeats < 1:
        raise BenchConfigError("Diagnostic thresholds must be positive")


def load_config(path: str | Path) -> BenchConfig:
    """Load and validate a bench TOML file.

    Relative paths inside the file are resolved against the file's directory.

    Args:
        path: Path to the TOML file.

    Returns:
        The validated configuration.

    Raises:
        BenchConfigError: If the file is missing, malformed or inconsistent.
    """
    path = Path(path).resolve()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as err:
        raise BenchConfigError(f"Config file not found: {path}") from err
    except tomllib.TOMLDecodeError as err:
        raise BenchConfigError(f"Invalid TOML in {path}: {err}") from err

    backend = data.get("backend")
    if backend not in SUPPORTED_BACKENDS:
        raise BenchConfigError(f"backend must be one of {SUPPORTED_BACKENDS}, got {backend!r}")
    simulation = _build(SimulationConfig, data, "simulation")
    if simulation.step_s <= 0:
        raise BenchConfigError("simulation.step_s must be positive")
    ecu = _build(EcuConfig, data, "ecu")
    _validate_ecu(ecu)
    variables = {str(k): str(v) for k, v in _section(data, "variables").items()}
    base = path.parent
    if backend == "dspace":
        raw = _build(DspaceConfig, data, "dspace")
        dspace = DspaceConfig(raw.platform, (base / raw.xil_port_config).resolve())
        return BenchConfig(backend, simulation, ecu, variables, dspace=dspace)

    raw_can = _build(CanConfig, data, "can")
    can_cfg = CanConfig(
        (base / raw_can.dbc_path).resolve(),
        raw_can.channel_prefix,
        (base / raw_can.log_dir).resolve(),
    )
    return BenchConfig(
        backend,
        simulation,
        ecu,
        variables,
        can=can_cfg,
        vehicle=_build(VehicleConfig, data, "vehicle"),
        radar=_build(RadarConfig, data, "radar"),
    )
