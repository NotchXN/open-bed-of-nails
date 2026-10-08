"""Only an in-memory simulator is shipped. No board or instrument is connected."""

from dataclasses import dataclass
from datetime import datetime, timezone


class FixtureNotReady(RuntimeError):
    pass


class MeasurementUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Measurement:
    value: float
    unit: str


SCENARIOS = {
    "healthy": "All supported demo checks pass",
    "short": "Supply-to-ground isolation gate fails before power-up",
    "open": "Ground continuity gate fails before power-up",
    "missing-rail": "3.3 V rail fails; dependent functional tests are untested",
    "overcurrent": "Current-limit reading fails and stops powered tests",
    "interlock-open": "Fixture lid is open at startup",
    "interlock-trip": "Fixture interlock opens after the first powered measurement",
    "contact-failure": "Fixture contact readiness check fails",
    "instrument-error": "Simulated instrument communication error",
    "unsupported-uart": "UART echo capability is unavailable",
    "shutdown-error": "Simulated power-off confirmation fails during teardown",
}


class Simulator:
    provenance = "simulated"

    def __init__(self, scenario="healthy"):
        if scenario not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario}")
        self.scenario = scenario
        self.powered = False
        self.lid_closed = scenario != "interlock-open"
        self.stimulus = None
        self.current_limit_ma = None
        self.actions = []

    def log(self, action, **details):
        self.actions.append({"at": datetime.now(timezone.utc).isoformat(), "action": action, **details})

    def check_ready(self):
        self.log("check_fixture", lid_closed=self.lid_closed)
        if not self.lid_closed:
            raise FixtureNotReady("Fixture interlock is open")
        if self.scenario == "contact-failure":
            raise FixtureNotReady("Fixture contact check failed")

    def power_on(self, voltage_v, current_limit_ma):
        self.check_ready()
        self.powered = True
        self.current_limit_ma = current_limit_ma
        self.log("power_on", voltage_v=voltage_v, current_limit_ma=current_limit_ma)

    def power_off(self):
        if self.scenario == "shutdown-error" and self.powered:
            self.log("power_off", confirmed=False)
            raise RuntimeError("Power-off confirmation unavailable")
        self.powered = False
        self.log("power_off", confirmed=True)
        return True

    def clear_stimulus(self):
        self.stimulus = None
        self.log("clear_stimulus")

    def settle(self, milliseconds):
        # Simulation records the request; it does not sleep or assert real settling.
        self.log("settle", requested_ms=milliseconds, simulated=True)

    def apply_stimulus(self, stimulus):
        self.check_ready()
        if not self.powered:
            raise RuntimeError("Cannot apply a stimulus while power is off")
        self.stimulus = dict(stimulus)
        self.log("stimulus", **stimulus)

    def measure(self, test):
        self.check_ready()
        expects_power = test["phase"] != "unpowered"
        if self.powered != expects_power:
            raise RuntimeError("Measurement attempted in the wrong electrical state")
        if test["method"] == "uart_echo" and self.scenario == "unsupported-uart":
            raise MeasurementUnavailable("UART echo capability is unavailable")
        if test["id"] == "supply_current" and self.scenario == "instrument-error":
            raise RuntimeError("Simulated instrument communication failed")
        nominal = {
            "ground_continuity": 0.18, "supply_isolation": 18000.0, "supply_current": 38.4,
            "rail_5v": 5.01, "rail_3v3": 3.29, "gpio_high": 3.26,
            "gpio_low": 0.04, "uart_loopback": 1.0,
        }
        if test["id"] not in nominal:
            raise MeasurementUnavailable("This simulator only implements the published demo test IDs")
        expected_units = {
            "ground_continuity": "ohm", "supply_isolation": "ohm", "supply_current": "mA",
            "rail_5v": "V", "rail_3v3": "V", "gpio_high": "V", "gpio_low": "V", "uart_loopback": "bool",
        }
        expected_points = {
            "ground_continuity": ["TP02", "TP03"], "supply_isolation": ["TP01", "TP02"],
            "supply_current": ["TP01", "TP02"], "rail_5v": ["TP04", "TP02"],
            "rail_3v3": ["TP05", "TP02"], "gpio_high": ["TP07", "TP02"],
            "gpio_low": ["TP07", "TP02"], "uart_loopback": ["TP11", "TP12"],
        }
        if test["points"] != expected_points[test["id"]]:
            raise MeasurementUnavailable("Measurement path is outside the simulator's demo wiring")
        value = nominal[test["id"]]
        if test["id"] in ("gpio_high", "gpio_low"):
            if self.stimulus is None or self.stimulus.get("point") != "TP10":
                raise MeasurementUnavailable("Demo logic-buffer input requires a TP10 stimulus")
            value = 3.26 if self.stimulus["level"] == 1 else 0.04
        if self.scenario == "short" and test["id"] == "supply_isolation":
            value = 8.0
        elif self.scenario == "open" and test["id"] == "ground_continuity":
            value = 12.0
        elif self.scenario == "missing-rail" and test["id"] == "rail_3v3":
            value = 0.08
        elif self.scenario == "overcurrent" and test["id"] == "supply_current":
            value = self.current_limit_ma
        unit = expected_units[test["id"]]
        self.log("measure", test_id=test["id"], value=value, unit=unit, powered=self.powered)
        if self.scenario == "interlock-trip" and test["id"] == "supply_current":
            self.lid_closed = False
            self.powered = False  # Model an independent hardware interlock cutoff.
            self.log("hardware_interlock_trip", simulated=True)
        return Measurement(value, unit)

    def close(self):
        self.log("close")
