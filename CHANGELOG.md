# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-14

### Added

- DBC with `VehicleState`, `RadarObject` and `AebCommand` (classic CAN).
- Plant model: ego longitudinal dynamics, lead object profiles, radar with seeded noise,
  latency, range limit and alive counter.
- Virtual AEB ECU with a TTC state machine (`OFF`, `STANDBY`, `WARNING`, `PARTIAL_BRAKE`,
  `FULL_BRAKE`, `FAULT`), radar timeout and alive-counter diagnostics.
- XIL-style bench ports (`ModelAccessPort`, `FaultInjectionPort`, `Bench`) with
  TOML-based variable mapping.
- Deterministic virtual backend on python-can virtual buses with a fault gateway
  (drop, freeze, offset, delay, silence) and BLF logging.
- dSPACE backend template (not validated) and `bench_dspace.toml`.
- BLF log reader and scenario plots, attached to the pytest-html report on failure.
- Unit and system tests with `smoke`, `regression`, `edge_case`, `fault_injection` and
  `stress` markers, and requirement traceability through the `req` marker.
- GitHub Actions CI (ruff, pytest, report artifacts), issue and pull request templates.
