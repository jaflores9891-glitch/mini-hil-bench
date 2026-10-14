# Architecture and design decisions

## Overview

```
tests ──> Bench (ports) ──> backend
                             ├── virtual: Plant ⇄ FaultGateway ⇄ AebEcu   (python-can virtual buses)
                             └── dspace:  template for VEOS / SCALEXIO via ASAM XIL (not validated)
```

* **Plant** (`plant/`): ego vehicle (Euler integration, first-order brake lag, saturation),
  lead object (stationary / constant speed / decelerating) and radar (noise, latency,
  range, alive counter). It sends `VehicleState` and `RadarObject` and reads `AebCommand`.
* **ECU** (`ecu/aeb_ecu.py`): TTC state machine with radar timeout and alive-counter
  diagnostics. It only sees CAN frames.
* **Fault gateway** (`bench/backends/virtual.py`): sits between the plant and ECU channels and
  can drop, freeze, offset, delay or silence messages. It also feeds the BLF logger.
* **Analysis** (`analysis/`): BLF → DataFrame decoded with the DBC, and one PNG per scenario.

## Why a fixed-step, single-threaded scheduler

Each 10 ms step runs plant → gateway → ECU → gateway → plant in a fixed order. There are no
threads, no `asyncio` and no sleeps (unless `real_time = true`). The same seed and the same
scenario always give exactly the same CAN log, so a failing test can always be reproduced.
It also runs much faster than real time, which keeps CI short.

## Why python-can virtual buses

The `virtual` interface works in-process on every OS, including GitHub-hosted runners where
`vcan`/SocketCAN is not available. The ECU still talks only through real `can.Message`
frames encoded with the DBC, the same as it would on a physical bus. Two channels (plant
side and ECU side) make the gateway a real man-in-the-middle, like a HIL bus-manipulation
module.

## Why XIL-like ports

Tests depend only on `ModelAccessPort`, `FaultInjectionPort` and `Bench`, and use
**logical variable names** (`ego.speed_mps`, `ecu.aeb_state`). Each backend's TOML file maps
those names to its sources: a plant variable or a decoded CAN signal on the virtual bench, or a
model path on a dSPACE bench. This is the variable mapping of a real HIL bench. The same
test suite can run against another backend by changing `--bench`, without touching the tests.

## Adding a real hardware backend

1. Create `bench/backends/<name>.py` with classes that implement the three ports.
2. Map every logical variable in a new `config/bench_<name>.toml`.
3. Implement `inject`/`clear` with the bench's own bus-manipulation or failure-insertion
   features.
4. Register the backend in `config.SUPPORTED_BACKENDS` and in `bench/factory.py`.
5. Run `pytest --bench config/bench_<name>.toml`. On real-time hardware, `run_for` waits
   in real time instead of stepping.

`bench/backends/dspace.py` is a template for steps 1–3 against VEOS/SCALEXIO and the ASAM XIL
API. It is **not validated**.
