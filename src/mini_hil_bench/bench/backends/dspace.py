"""dSPACE backend - documented TEMPLATE, NOT VALIDATED (no dSPACE license available).

How this backend would work
---------------------------
On a dSPACE bench the plant model (and, for a virtual ECU, the AEB function too) runs on
the dSPACE platform: VEOS for PC-based simulation or a SCALEXIO system for real-time HIL
with a physical ECU. The test PC talks to the platform through the ASAM XIL API, which
dSPACE provides as part of its Platform API Package / XIL API implementation.

Mapping of this project's ports to ASAM XIL concepts:

* ``ModelAccessPort`` -> an XIL **MAPort** (model access port). ``read``/``write`` act on
  model variables; ``capture`` corresponds to an XIL **Capture** started on the MAPort.
* ``FaultInjectionPort`` -> CAN-level manipulation in the bus simulation model, or an XIL
  **EESPort** (electrical error simulation) for wiring faults on a SCALEXIO system.
* Logical variable names (``ego.speed_mps``) are mapped to model paths in
  ``config/bench_dspace.toml`` (for example ``"Model Root/Vehicle/v_ego"``). The paths in
  that file are placeholders and must be replaced with the paths of the real model.

Nothing from dSPACE is imported at module level, so the package installs and passes CI
without a license. Every method raises ``NotImplementedError``; the ``TODO`` comments say
which step belongs where. Refer to the official dSPACE XIL API documentation for the
concrete classes, method names and configuration files - none are guessed here.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from mini_hil_bench.bench.faults import Fault
from mini_hil_bench.bench.ports import Bench, FaultInjectionPort, ModelAccessPort, Scenario
from mini_hil_bench.config import BenchConfig

NOT_VALIDATED = (
    "dSPACE backend is a non-validated template (no dSPACE license available). "
    "See the module docstring of mini_hil_bench.bench.backends.dspace."
)


class DspaceModelAccess(ModelAccessPort):
    """Model access through an ASAM XIL MAPort (template).

    Args:
        config: Bench configuration with ``backend = "dspace"``.
    """

    def __init__(self, config: BenchConfig) -> None:
        """Store the configuration; no connection is made."""
        self._config = config

    def read(self, name: str) -> float:
        """Read a model variable (template, see ``ModelAccessPort.read``)."""
        # TODO: Resolve `name` through self._config.variables to its model path and read it
        #       from the connected MAPort (dSPACE XIL API documentation: reading variables).
        raise NotImplementedError(NOT_VALIDATED)

    def write(self, name: str, value: float) -> None:
        """Write a model variable (template, see ``ModelAccessPort.write``)."""
        # TODO: Resolve `name` to its model path and write `value` through the MAPort
        #       (dSPACE XIL API documentation: writing variables).
        raise NotImplementedError(NOT_VALIDATED)

    def capture(self, names: list[str]) -> pd.DataFrame:
        """Return captured variable history (template, see ``ModelAccessPort.capture``)."""
        # TODO: Configure an XIL Capture for the mapped model paths before the run, then
        #       fetch the capture result and convert it to a DataFrame with a time_s column
        #       (dSPACE XIL API documentation: data capturing).
        raise NotImplementedError(NOT_VALIDATED)


class DspaceFaultInjection(FaultInjectionPort):
    """Fault injection on a dSPACE bench (template).

    Args:
        config: Bench configuration with ``backend = "dspace"``.
    """

    def __init__(self, config: BenchConfig) -> None:
        """Store the configuration; no connection is made."""
        self._config = config

    def inject(self, fault: Fault) -> None:
        """Activate a fault (template, see ``FaultInjectionPort.inject``)."""
        # TODO: Translate `fault` into writes on the bus simulation's manipulation
        #       variables (drop/freeze/offset/delay/silence), or into an EESPort error set
        #       for electrical faults (dSPACE documentation of the bus and EES features).
        raise NotImplementedError(NOT_VALIDATED)

    def clear(self, fault: Fault) -> None:
        """Deactivate a fault (template, see ``FaultInjectionPort.clear``)."""
        # TODO: Reset the manipulation variables / EESPort error set of `fault`.
        raise NotImplementedError(NOT_VALIDATED)

    def clear_all(self) -> None:
        """Deactivate every fault (template, see ``FaultInjectionPort.clear_all``)."""
        # TODO: Reset every manipulation variable and EESPort error set.
        raise NotImplementedError(NOT_VALIDATED)


class DspaceBench(Bench):
    """Bench running on VEOS or SCALEXIO through the ASAM XIL API (template).

    Args:
        config: Bench configuration with ``backend = "dspace"``.
    """

    def __init__(self, config: BenchConfig) -> None:
        """Store the configuration; no connection is made."""
        self._config = config
        self._model = DspaceModelAccess(config)
        self._faults = DspaceFaultInjection(config)

    @property
    def model(self) -> ModelAccessPort:
        """Model access port (template)."""
        return self._model

    @property
    def faults(self) -> FaultInjectionPort:
        """Fault injection port (template)."""
        return self._faults

    @property
    def log_path(self) -> Path:
        """CAN log path (template)."""
        # TODO: Return the path of the CAN log recorded by the bus monitoring tool.
        raise NotImplementedError(NOT_VALIDATED)

    def start(self) -> None:
        """Connect to the platform (template, see ``Bench.start``)."""
        # TODO: 1. Create the XIL testbench for the installed dSPACE XIL API version.
        #       2. Create the MAPort and configure it with self._config.dspace.xil_port_config
        #          (platform: self._config.dspace.platform).
        #       3. Load/start the simulation application on VEOS or SCALEXIO.
        #       See the dSPACE XIL API documentation, "MAPort configuration".
        raise NotImplementedError(NOT_VALIDATED)

    def stop(self) -> None:
        """Disconnect from the platform (template, see ``Bench.stop``)."""
        # TODO: Stop running captures, stop the simulation if required, dispose the MAPort.
        raise NotImplementedError(NOT_VALIDATED)

    def load_scenario(self, scenario: Scenario) -> None:
        """Apply initial conditions (template, see ``Bench.load_scenario``)."""
        # TODO: Write the scenario's initial conditions to the mapped model variables
        #       (ego speed, lead profile/speed/gap) and reset the model.
        raise NotImplementedError(NOT_VALIDATED)

    def run_for(self, seconds: float) -> None:
        """Let the real-time simulation run (template, see ``Bench.run_for``)."""
        # TODO: On a real-time platform time cannot be stepped; wait `seconds` of
        #       simulation time (e.g. by polling the model's simulation time variable).
        raise NotImplementedError(NOT_VALIDATED)
