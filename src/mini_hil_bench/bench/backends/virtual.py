"""Virtual backend: plant, fault gateway and ECU on python-can virtual buses.

Topology (two virtual CAN channels, one process, one thread)::

    Plant <--plant channel--> FaultGateway <--ECU channel--> AebEcu

Every 10 ms step: the plant transmits, the gateway forwards to the ECU (applying faults),
the ECU runs and answers, the gateway forwards back, the plant reads the command and
integrates. All ECU-side traffic is recorded to a BLF file with simulated timestamps.
"""

from __future__ import annotations

import itertools
import logging
import math
import re
import time
from collections.abc import Callable
from pathlib import Path

import can
import pandas as pd

from mini_hil_bench.bench.faults import Fault, FaultType
from mini_hil_bench.bench.ports import Bench, FaultInjectionPort, ModelAccessPort, Scenario
from mini_hil_bench.can_db import KPH_PER_MPS, CanDatabase
from mini_hil_bench.config import BenchConfig
from mini_hil_bench.ecu.aeb_ecu import AebEcu
from mini_hil_bench.exceptions import BenchConfigError, BenchStateError, SignalNotFoundError
from mini_hil_bench.plant.lead_object import LeadObject
from mini_hil_bench.plant.radar import Radar
from mini_hil_bench.plant.vehicle import Vehicle

logger = logging.getLogger(__name__)

FILLER_FRAME_ID = 0x050  # higher priority than every DBC message
MODEL_PREFIX = "model:"
CAN_PREFIX = "can:"
_bench_ids = itertools.count()


def _drain(bus: can.BusABC) -> list[can.Message]:
    frames = []
    while (frame := bus.recv(timeout=0)) is not None:
        frames.append(frame)
    return frames


class SignalCache(can.Listener):
    """Keeps the latest decoded value of every DBC signal seen on a bus."""

    def __init__(self, can_db: CanDatabase) -> None:
        """Create an empty cache."""
        self._db = can_db
        self.values: dict[str, float] = {}

    def on_message_received(self, msg: can.Message) -> None:
        """Decode a frame and store its signals as ``Message.Signal`` keys."""
        if self._db.message_name(msg.arbitration_id) is None:
            return
        name, signals = self._db.decode(msg)
        self.values.update({f"{name}.{sig}": value for sig, value in signals.items()})


class FaultGateway(FaultInjectionPort):
    """Forwards frames between the plant and ECU channels and applies active faults.

    Args:
        can_db: CAN database.
        listeners: Listeners notified of every frame on the ECU side.
    """

    def __init__(self, can_db: CanDatabase, listeners: list[can.Listener]) -> None:
        """Create a gateway without active faults."""
        self._db = can_db
        self._listeners = listeners
        self._active: dict[Fault, float | int | None] = {}
        self._delayed: list[tuple[int, can.BusABC, can.Message]] = []

    def inject(self, fault: Fault) -> None:
        """Activate a fault (see ``FaultInjectionPort.inject``)."""
        signals = self._db.signal_names(fault.message)
        if fault.signal is not None and fault.signal not in signals:
            raise SignalNotFoundError(f"{fault.message}.{fault.signal}")
        logger.info("Injecting fault %s", fault)
        self._active[fault] = fault.count if fault.kind is FaultType.DROP else fault.value

    def clear(self, fault: Fault) -> None:
        """Deactivate a fault (see ``FaultInjectionPort.clear``)."""
        self._active.pop(fault, None)

    def clear_all(self) -> None:
        """Deactivate every fault."""
        self._active.clear()

    def forward(self, src: can.BusABC, dst: can.BusABC, step: int, now_s: float) -> None:
        """Forward pending frames from ``src`` to ``dst``, releasing due delayed frames.

        Args:
            src: Bus to read from.
            dst: Bus to write to.
            step: Current scheduler step index.
            now_s: Current simulated time.
        """
        due = [f for s, bus, f in self._delayed if bus is dst and s <= step]
        self._delayed = [d for d in self._delayed if not (d[1] is dst and d[0] <= step)]
        for frame in due:
            self._deliver(dst, frame, now_s)
        for frame in _drain(src):
            faulty = self._apply(frame)
            if faulty is None:
                continue
            delay_steps = self._delay_steps(faulty)
            if delay_steps:
                self._delayed.append((step + delay_steps, dst, faulty))
            else:
                self._deliver(dst, faulty, now_s)

    def _deliver(self, dst: can.BusABC, frame: can.Message, now_s: float) -> None:
        frame.timestamp = now_s
        dst.send(frame)
        self.notify(frame)

    def notify(self, frame: can.Message) -> None:
        """Pass an ECU-side frame to the listeners (logger, signal cache).

        Args:
            frame: Frame seen on the ECU side.
        """
        for listener in self._listeners:
            listener.on_message_received(frame)

    def _faults_for(self, frame: can.Message) -> list[Fault]:
        name = self._db.message_name(frame.arbitration_id)
        return [fault for fault in self._active if fault.message == name]

    def _delay_steps(self, frame: can.Message) -> int:
        faults = [f for f in self._faults_for(frame) if f.kind is FaultType.DELAY]
        return max((f.count for f in faults), default=0)

    def _apply(self, frame: can.Message) -> can.Message | None:
        faults = self._faults_for(frame)
        if not faults:
            return frame
        if any(f.kind is FaultType.SILENCE for f in faults):
            return None
        for fault in (f for f in faults if f.kind is FaultType.DROP):
            remaining = int(self._active[fault] or 0)
            if remaining > 0:
                self._active[fault] = remaining - 1
                return None
        name, signals = self._db.decode(frame)
        for fault in faults:
            if fault.kind is FaultType.OFFSET:
                signals[fault.signal] += fault.value
            elif fault.kind is FaultType.FREEZE:
                if self._active[fault] is None:
                    self._active[fault] = signals[fault.signal]
                signals[fault.signal] = float(self._active[fault])
        return self._db.encode(name, signals, frame.timestamp)


class PlantNode:
    """Plant (vehicle, lead object, radar) connected to the plant CAN channel.

    Args:
        config: Bench configuration (virtual backend).
        can_db: CAN database.
        bus: Plant-side bus.
        scenario: Initial conditions.
    """

    def __init__(
        self, config: BenchConfig, can_db: CanDatabase, bus: can.BusABC, scenario: Scenario
    ) -> None:
        """Build the plant models from the scenario."""
        step_s = config.simulation.step_s
        self._db = can_db
        self._bus = bus
        self._scenario = scenario
        self.vehicle = Vehicle(config.vehicle, scenario.ego_speed_mps, step_s)
        self.lead = LeadObject(
            scenario.lead_profile,
            scenario.initial_gap_m,
            scenario.lead_speed_mps,
            scenario.lead_decel_mps2,
            step_s,
        )
        self.radar = Radar(config.radar, config.simulation.seed)
        self.decel_request_mps2 = 0.0
        self._vehicle_period = round(can_db.cycle_time_s("VehicleState") / step_s)
        self._radar_period = round(can_db.cycle_time_s("RadarObject") / step_s)

    @property
    def gap_m(self) -> float:
        """True distance between ego front and object rear."""
        return self.lead.position_m - self.vehicle.position_m

    @property
    def rel_speed_mps(self) -> float:
        """True object speed minus ego speed."""
        return self.lead.speed_mps - self.vehicle.speed_mps

    @property
    def ttc_s(self) -> float:
        """Ground-truth time to collision (inf when not closing)."""
        closing_mps = -self.rel_speed_mps
        return self.gap_m / closing_mps if closing_mps > 0.0 else math.inf

    def transmit(self, step: int, now_s: float) -> None:
        """Sample the radar and send the frames due at this step.

        Args:
            step: Scheduler step index.
            now_s: Simulated time.
        """
        self.radar.sample(self.gap_m, self.rel_speed_mps)
        filler = can.Message(arbitration_id=FILLER_FRAME_ID, data=bytes(8), is_extended_id=False)
        for _ in range(self._scenario.bus_load_frames_per_step):
            filler.timestamp = now_s
            self._bus.send(filler)
        if step % self._vehicle_period == 0:
            signals = {
                "EgoSpeed": self.vehicle.speed_mps * KPH_PER_MPS,
                "EgoAccel": self.vehicle.accel_mps2,
            }
            self._bus.send(self._db.encode("VehicleState", signals, now_s))
        if step % self._radar_period == 0:
            m = self.radar.output()
            signals = {
                "ObjDistance": m.distance_m,
                "ObjRelSpeed": m.rel_speed_mps,
                "ObjValid": int(m.valid),
                "RadarAliveCounter": m.alive_counter,
            }
            self._bus.send(self._db.encode("RadarObject", signals, now_s))

    def receive(self) -> None:
        """Read the latest ``AebCommand`` from the bus."""
        for frame in _drain(self._bus):
            if self._db.message_name(frame.arbitration_id) == "AebCommand":
                self.decel_request_mps2 = self._db.decode(frame)[1]["DecelRequest"]

    def advance(self) -> None:
        """Integrate the plant by one step."""
        self.vehicle.step(self.decel_request_mps2)
        self.lead.step()


MODEL_GETTERS: dict[str, Callable[[PlantNode], float]] = {
    "ego.speed_mps": lambda plant: plant.vehicle.speed_mps,
    "ego.accel_mps2": lambda plant: plant.vehicle.accel_mps2,
    "lead.speed_mps": lambda plant: plant.lead.speed_mps,
    "plant.gap_m": lambda plant: plant.gap_m,
    "plant.ttc_s": lambda plant: plant.ttc_s,
}


class VirtualModelAccess(ModelAccessPort):
    """Model access port of the virtual bench.

    Args:
        bench: The owning bench.
    """

    def __init__(self, bench: VirtualBench) -> None:
        """Bind the port to its bench."""
        self._bench = bench

    def read(self, name: str) -> float:
        """Return the current value of a logical variable (see ``ModelAccessPort``)."""
        return self._bench.read_variable(name)

    def write(self, name: str, value: float) -> None:
        """Write a writable model variable (see ``ModelAccessPort``)."""
        self._bench.write_variable(name, value)

    def capture(self, names: list[str]) -> pd.DataFrame:
        """Return the recorded history of variables (see ``ModelAccessPort``)."""
        for name in names:
            self._bench.source_of(name)
        return pd.DataFrame(self._bench.history, columns=["time_s", *self._bench.variables])[
            ["time_s", *names]
        ]


class VirtualBench(Bench):
    """Fully simulated bench running faster than real time (unless ``real_time`` is set).

    Args:
        config: Bench configuration with ``backend = "virtual"``.
        test_name: Name of the BLF log file (sanitised).
    """

    def __init__(self, config: BenchConfig, test_name: str = "bench") -> None:
        """Prepare the bench; nothing is opened until ``start()``."""
        if config.can is None or config.vehicle is None or config.radar is None:
            raise BenchConfigError("Virtual backend needs [can], [vehicle] and [radar] sections")
        self._config = config
        self._db = CanDatabase(config.can.dbc_path)
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", test_name).strip("_")
        self._log_path = config.can.log_dir / f"{safe_name}.blf"
        self._channel = f"{config.can.channel_prefix}-{next(_bench_ids)}"
        self.variables = list(config.variables)
        self.history: list[list[float]] = []
        self._model = VirtualModelAccess(self)
        self._signals = SignalCache(self._db)
        self._buses: dict[str, can.BusABC] = {}
        self._writer: can.BLFWriter | None = None
        self._gateway: FaultGateway | None = None
        self._plant: PlantNode | None = None
        self._ecu: AebEcu | None = None
        self._step = 0
        for name in self.variables:
            self._check_source(self.source_of(name))

    @property
    def model(self) -> ModelAccessPort:
        """Model access port."""
        return self._model

    @property
    def faults(self) -> FaultInjectionPort:
        """Fault injection port (the gateway)."""
        if self._gateway is None:
            raise BenchStateError("Bench not started")
        return self._gateway

    @property
    def log_path(self) -> Path:
        """Path of the BLF log of this bench."""
        return self._log_path

    @property
    def now_s(self) -> float:
        """Current simulated time."""
        return self._step * self._config.simulation.step_s

    def start(self) -> None:
        """Open the virtual buses and the BLF log."""
        for side in ("plant", "gw_plant", "gw_ecu", "ecu"):
            channel = f"{self._channel}-{'plant' if 'plant' in side else 'ecu'}"
            self._buses[side] = can.Bus(
                interface="virtual", channel=channel, preserve_timestamps=True
            )
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._writer = can.BLFWriter(self._log_path)
        self._gateway = FaultGateway(self._db, [self._writer, self._signals])
        logger.info("Virtual bench started, logging to %s", self._log_path)

    def stop(self) -> None:
        """Close the log and the buses. Safe to call more than once."""
        if self._writer is not None:
            self._writer.stop()
            self._writer = None
        for bus in self._buses.values():
            bus.shutdown()
        self._buses.clear()

    def load_scenario(self, scenario: Scenario) -> None:
        """Reset plant, ECU and time to the scenario's initial conditions."""
        if not self._buses:
            raise BenchStateError("Call start() before load_scenario()")
        self._plant = PlantNode(self._config, self._db, self._buses["plant"], scenario)
        self._ecu = AebEcu(self._config.ecu, self._db, self._buses["ecu"])
        self._step = 0
        self.history.clear()
        logger.info("Loaded scenario %s", scenario)

    def run_for(self, seconds: float) -> None:
        """Advance simulated time by ``seconds`` with the fixed-step scheduler."""
        if self._plant is None or self._ecu is None or self._gateway is None:
            raise BenchStateError("Call start() and load_scenario() before run_for()")
        wall_start_s = time.perf_counter() - self.now_s
        for _ in range(round(seconds / self._config.simulation.step_s)):
            self._run_step(self._plant, self._ecu, self._gateway)
            if self._config.simulation.real_time:
                time.sleep(max(0.0, wall_start_s + self.now_s - time.perf_counter()))

    def _run_step(self, plant: PlantNode, ecu: AebEcu, gateway: FaultGateway) -> None:
        now_s = self.now_s
        buses = self._buses
        plant.transmit(self._step, now_s)
        gateway.forward(buses["gw_plant"], buses["gw_ecu"], self._step, now_s)
        ecu.step(now_s)
        gateway.forward(buses["gw_ecu"], buses["gw_plant"], self._step, now_s)
        plant.receive()
        self.history.append([now_s, *(self.read_variable(n) for n in self.variables)])
        plant.advance()
        self._step += 1

    def source_of(self, name: str) -> str:
        """Return the mapped source of a logical variable.

        Args:
            name: Logical variable name.

        Returns:
            The source string from the ``[variables]`` table.

        Raises:
            SignalNotFoundError: If the variable is not mapped.
        """
        try:
            return self._config.variables[name]
        except KeyError as err:
            raise SignalNotFoundError(f"Unmapped bench variable: {name}") from err

    def _check_source(self, source: str) -> None:
        if source.startswith(MODEL_PREFIX):
            if source.removeprefix(MODEL_PREFIX) not in MODEL_GETTERS:
                raise BenchConfigError(f"Unknown model variable in mapping: {source}")
        elif source.startswith(CAN_PREFIX):
            message, _, signal = source.removeprefix(CAN_PREFIX).partition(".")
            if signal not in self._db.signal_names(message):
                raise BenchConfigError(f"Unknown CAN signal in mapping: {source}")
        else:
            raise BenchConfigError(f"Variable source must start with model: or can: ({source})")

    def read_variable(self, name: str) -> float:
        """Read a logical variable from the plant or from the ECU-side signal cache.

        Args:
            name: Logical variable name.

        Returns:
            The current value (NaN for a CAN signal not received yet).
        """
        source = self.source_of(name)
        if source.startswith(CAN_PREFIX):
            return self._signals.values.get(source.removeprefix(CAN_PREFIX), math.nan)
        if self._plant is None:
            raise BenchStateError("No scenario loaded")
        return float(MODEL_GETTERS[source.removeprefix(MODEL_PREFIX)](self._plant))

    def write_variable(self, name: str, value: float) -> None:
        """Write a writable plant variable (``ego.speed_mps`` or ``lead.speed_mps``).

        Args:
            name: Logical variable name.
            value: New value in SI units.

        Raises:
            SignalNotFoundError: If the variable is read-only.
        """
        source = self.source_of(name).removeprefix(MODEL_PREFIX)
        if self._plant is None:
            raise BenchStateError("No scenario loaded")
        if source == "ego.speed_mps":
            self._plant.vehicle.speed_mps = max(0.0, value)
        elif source == "lead.speed_mps":
            self._plant.lead.speed_mps = max(0.0, value)
        else:
            raise SignalNotFoundError(f"Bench variable is read-only: {name}")
