# Fail‑Safe & Sensor Recovery System

BaraCommLib guarantees that the robot stops moving if a critical sensor has been continuously failing for **≥ 5 seconds**.
The mechanism is distributed: each :class:`~baracommlib.sensors.AbstractSensor` monitors its own health, and when it decides the situation cannot be recovered locally it triggers a global fail‑safe routine that safely halts the drivetrain and rebuilds all sensors of the same type on the affected I²C bus.

---
## 1. Detection – `AbstractSensor._polling_loop`
The background thread runs this loop until :py:meth:`stop` clears ``self._running``:
```python
while self._running:
    if not self._paused:
        try:
            val = self._read_hardware()
            with lock:  # protect shared state
                self._latest_reading = SensorReading(val, now(), True)
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            if first_error_time is None:
                first_error_time = now()
            logging.error(f"Error reading sensor {self.sensor_id}: {e}")
            with lock: self._latest_reading = SensorReading(None, now(), False)
            # Trigger fail‑safe after 5 s of continuous failures
            if now() - first_error_time >= 5.0:
                logging.critical("Sensor %s failed >5 sec – triggering recover.")
                threading.Thread(target=self.on_critical_failure,
                                 args=(self.sensor_type, self.bus_id)).start()
                # Stop this thread; SensorsManager will re‑create it later
                first_error_time = None
                consecutive_errors = 0
    time.sleep(self._poll_rate)
```
* **`consecutive_errors`** – count of successive failures.
* **`first_error_time`** – timestamp when the current failure streak began. If the streak lasts five seconds, fail‑safe is invoked.
* The thread sleeps for ``self._poll_rate`` (default 30 ms) between attempts to keep CPU usage low.

---
## 2. Escalation – Callback to `SensorsManager`
The sensor launches a background thread that calls the callback supplied during :class:`~baracommlib.sensors.SensorsManager` construction:
```python
threading.Thread(target=self.on_critical_failure,
                 args=(self.sensor_type, self.bus_id)).start()
```
### `SensorsManager._handle_sensor_failure(sensor_type: str, bus_id: str)`
| Parameter | Role |
|-----------|------|
| ``sensor_type`` | e.g., "tof" or "imu" – the kind of sensor that failed. |
| ``bus_id``     | Identifier of the I²C bus (matches config). |

The handler performs three steps:
1. **Stop drivetrain** – calls whatever callback was passed when initializing :class:`SensorsManager` (normally `self.drivetrain.stop`).
2. **Remove failing sensors** – iterates over ``self.sensors``; for each sensor whose type and bus match, it invokes its own :meth:`stop()` method and deletes the entry from the dictionary.
3. **Re‑create sensors of that type on that bus** – re‑instantiates all configurations found in `config['sensors'][sensor_type]` that belong to ``bus_id`` and starts them sequentially (important for ToF devices so they can negotiate unique I²C addresses).

All steps run inside the callback thread, keeping the original sensor’s polling loop from blocking.

---
## 3. Recovery – Re‑initialising Sensors
Re‑instantiation logic is essentially a copy of normal boot:
```python
if sensor_type == "tof":
    for cfg in sensors_cfg.get("tof", []):
        if cfg["bus"] == bus_id:
            s = ToFSensor(cfg, self.buses[bus_id], …)
            self.sensors[s.sensor_id] = s
            s.start()
```
The library sleeps briefly (≈ 50 ms) between each sensor’s start to allow the I²C address negotiation to complete.
For IMUs it simply recreates and starts them without special sequencing.

---
## Practical Usage & Customisation
| Task | What you need to set |
|------|---------------------|
| **Provide a stop callback** – `SensorsManager(config, stop_robot_callback=self.drivetrain.stop)` is already done in :class:`BaraRobot.__init__`. |
| **Change fail‑safe threshold** – edit the literal ``5.0`` inside *sensors.py*’s `_polling_loop`.
| **Add a custom sensor class** – inherit from `AbstractSensor`, call super with appropriate ``sensor_type`` and ``bus_id``, ensure `_read_hardware()` raises an exception on error; fail‑safe will pick it up automatically. |

---
## Key Functions & Methods (Quick Reference)
- :class:`~baracommlib.sensors.AbstractSensor._polling_loop`
- :meth:`SensorsManager._handle_sensor_failure(sensor_type, bus_id)`
- :class:`Motors.coast()` / ``stop()`` – the safe stop routine invoked by fail‑safe.

---
## Testing & Verification
Run the bundled test on a PC (mocked hardware):
```bash
cd /home/helemen7/Coding/Robotica/BaraCommLib
PYTHONPATH=./src python tests/test_general.py
```
It injects a sensor that always raises an exception, waits for > 5 seconds and confirms the drivetrain has been stopped.

---
## Troubleshooting Common Issues
| Symptom | Likely Cause |
|---------|--------------|
| Drivetrain does not stop after fail‑safe triggers | `stop_robot_callback` was *not* passed to :class:`SensorsManager`.  Verify you call `self.sensors_manager = SensorsManager(self.config, stop_robot_callback=self.drivetrain.stop)` in your robot class.
| Sensor keeps failing even after recovery | Loose I²C wiring or incorrect bus frequency. Reduce the ``frequency`` field (e.g., to 100 kHz) and retry.
| No “failed >5 s” log message | Logging is configured at a level lower than INFO/CRITICAL, or `logging.basicConfig(level=logging.INFO)` has not been called before sensors start.

---
## Extending the Fail‑Safe for New Sensor Types
1. Create your sensor subclass inheriting :class:`AbstractSensor`.
2. In its ``__init__`` call `super().__init__(..., sensor_type="mytype", bus_id=…)`.
3. Make sure `_read_hardware()` raises an exception when hardware is unreachable; returning ``None`` or a stale value will not trigger fail‑safe.
4. The default :class:`SensorsManager._handle_sensor_failure` already knows how to rebuild all sensors of type "mytype" on the same bus, so no additional code is required.

That covers every public function involved in BaraCommLib’s built‑in fail‑safe mechanism.
