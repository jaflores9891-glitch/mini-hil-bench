---
name: Bug report
about: Report a failing test, wrong ECU behaviour or a bench problem
title: "[BUG] "
labels: bug
---

## Summary

<!-- One sentence describing the problem. -->

## Affected requirement

<!-- e.g. REQ-AEB-004. See docs/requirements.md. -->

## Steps to reproduce

1. Bench config: <!-- e.g. config/bench_virtual.toml -->
2. Command: <!-- e.g. pytest -m fault_injection -k timeout -->
3. Scenario / fault: <!-- ego speed, initial gap, lead profile, injected fault -->

## Expected result

## Actual result

## Evidence

- BLF log: <!-- reports/logs/<test_name>.blf -->
- Plot: <!-- reports/plots/<test_name>.png -->
- HTML report / CI run link:

## Root cause category

- [ ] Software (ECU function)
- [ ] Test environment (plant model, bench, configuration)
- [ ] Automation (test script, fixtures, CI)
- [ ] Hardware
- [ ] Unknown (to be analysed)

## Environment

- OS:
- Python version:
- Commit:
