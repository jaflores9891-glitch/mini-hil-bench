# AEB requirements

Requirements for the AEB function under test. The calibration values come from the `[ecu]`
section of the bench TOML file. Tests reference requirements with `@pytest.mark.req("REQ-AEB-00x")`,
and the IDs appear in the *Requirements* column of the HTML report.

Common preconditions unless stated otherwise: ego speed ≥ 10 km/h, object valid
(`ObjValid = 1`) and closing (`ObjRelSpeed < 0`). TTC = distance / closing speed.
"Onset TTC" is the ground-truth TTC (from the plant model) at the first `AebCommand` frame with
the new state. The tolerance of 0.15 s covers radar latency (20 ms), the radar cycle (20 ms)
and sensor noise.

| ID | Description | Acceptance criterion | Covered by |
|----|-------------|----------------------|------------|
| REQ-AEB-001 | The ECU shall issue a warning when TTC drops below 2.6 s. | Onset TTC of `WARNING` in [2.45, 2.60] s. `BrakeRequest = 0` while in `WARNING`. | `test_regression.py::test_warning_issued_when_ttc_drops_below_warning_threshold` |
| REQ-AEB-002 | The ECU shall request partial braking when TTC drops below 1.6 s. | Onset TTC of `PARTIAL_BRAKE` in [1.45, 1.60] s. `DecelRequest = 4.0 m/s²` and `BrakeRequest = 1` while in `PARTIAL_BRAKE`. | `test_regression.py::test_partial_brake_at_partial_ttc_threshold`, `test_stress.py` |
| REQ-AEB-003 | The ECU shall request full braking when TTC drops below 0.9 s. | Onset TTC of `FULL_BRAKE` in [0.75, 0.90] s. `DecelRequest = 9.0 m/s²` while in `FULL_BRAKE`. | `test_regression.py::test_full_brake_at_full_ttc_threshold`, `test_stress.py` |
| REQ-AEB-004 | The vehicle shall not collide with an object ahead. | Stationary object, ego 20–50 km/h, initial TTC ≥ 1.6 s: the ego stops with a gap ≥ 1.0 m, also under ~60 % bus load. Lead braking at 6 m/s² from 50 km/h with a 25 m gap, a +1.0 m `ObjDistance` offset, or a 50 ms `RadarObject` delay: gap stays > 0 m. | `test_regression.py::test_no_collision_*`, `test_edge_cases.py::test_no_collision_over_speed_and_initial_distance`, `test_fault_injection.py::test_distance_offset_*`, `test_fault_injection.py::test_delayed_radar_frames_*`, `test_stress.py` |
| REQ-AEB-005 | The function shall be inactive below 10 km/h. | At 8, 9.5 and 9.9 km/h: no state other than `OFF`/`STANDBY` and no brake request. At 10.1 and 10.5 km/h: `WARNING` is issued. | `test_regression.py::test_no_activation_below_minimum_speed`, `test_edge_cases.py::test_activation_around_minimum_speed` |
| REQ-AEB-006 | The ECU shall not activate for irrelevant objects. | Receding object (lead faster than ego) or object with `ObjValid = 0`: no state other than `OFF`/`STANDBY`. | `test_regression.py::test_no_activation_for_receding_object`, `test_fault_injection.py::test_object_flagged_invalid_is_ignored` |
| REQ-AEB-007 | Loss of the radar message shall be detected. | No `RadarObject` for more than 100 ms: `FAULT` within 150 ms of the loss, latched, with `DecelRequest = 0` and `BrakeRequest = 0`. A single lost frame or a 50 ms delay shall not cause `FAULT`. | `test_fault_injection.py::test_radar_timeout_*`, `test_fault_injection.py::test_single_dropped_radar_frame_*`, `test_fault_injection.py::test_delayed_radar_frames_*` |
| REQ-AEB-008 | A frozen radar alive counter shall be detected. | Alive counter unchanged for 3 consecutive frames: `FAULT` within 130 ms of the freeze (4 radar cycles + 50 ms), with no brake request. | `test_fault_injection.py::test_frozen_alive_counter_sets_fault_without_braking` |
