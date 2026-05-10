# BaraCommLib Documentation

BaraCommLib is a lightweight, hardware‑agnostic robot control library written in Python.
It exposes a clean API for:
* Configuration parsing and validation (`config_manager`)
* Sensor abstraction (I²C devices, IMUs, ToF sensors – see `sensors`) 
* State machine orchestration (`state_machine`)
* Drive‑train primitives with encoder support (`Motors`, `drivetrain`) 
* PID controllers for motion control (`pid_controller`) 
* Telemetry logging and debugging utilities
* Optional computer‑vision helpers (color tracking, model inference – see `vision`).

The library is split into a small set of core modules; each has its own Markdown page that documents public classes/methods in detail.

## Table of Contents
- **[BaraRobot](bararobot.md)** — High‑level robot wrapper: config loading, sensor & motor initialization, high‑level actions.
- **[Configuration Management](configuration.md)** — `ConfigManager` and the validation logic for the YAML configuration file.
- **[Sensors System](sensors.md)** — Abstract base class, ToF / IMU implementations, multi‑bus handling and fail‑safe behaviour.
- **[Motors & Drive Train](motors.md)** — Motor driver abstraction, encoder handling and motion primitives (`drive`, `spin`).
- **[PID Controllers](pid_io.md)** — Generic PID controller plus position/velocity specialisations with clamping logic.
- **[Vision Module](vision.md)** — Optional camera capture thread, TFLite inference wrapper, colour‑tracking utilities.
- **[State Machine Framework](state_machine.md)** — Hierarchical state machine implementation used by `BaraRobot` for complex behaviours.
- **[Fail‑Safe Handling](fail_safe.md)** — How sensor errors are detected and how the robot is safely stopped.

> All source files live in ``/home/.../BarCommLib/src/baracommlib``.  The docs assume you have a working Python environment (Python 3.9+) with all dependencies installed via Poetry (`poetry install`).
