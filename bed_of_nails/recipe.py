"""Validate recipes before constructing or invoking a test backend."""

import hashlib
import json
import math
from pathlib import Path

METHOD_UNITS = {"resistance": "ohm", "voltage": "V", "current": "mA", "uart_echo": "bool"}
PHASES = {"unpowered": 0, "powered": 1, "functional": 2}


def text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise ValueError(f"{label} must be nonempty text of at most 160 characters")
    return value


def number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def strict_json(raw):
    def reject(value):
        raise ValueError(f"Non-finite JSON number: {value}")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(raw, parse_constant=reject, object_pairs_hook=unique)


def validate_recipe(recipe):
    if not isinstance(recipe, dict) or type(recipe.get("schema_version")) is not int or recipe["schema_version"] != 1:
        raise ValueError("Recipe requires integer schema_version 1")
    for key in ("id", "version", "board_model", "board_revision", "description"):
        text(recipe.get(key), key)
    power = recipe.get("power")
    if not isinstance(power, dict):
        raise ValueError("power configuration is required")
    if set(power) != {"voltage_v", "current_limit_ma"}:
        raise ValueError("power accepts only voltage_v and current_limit_ma")
    if not 0 < number(power.get("voltage_v"), "Supply voltage") <= 24:
        raise ValueError("Software recipe voltage must be greater than 0 and at most 24 V")
    if not 0 < number(power.get("current_limit_ma"), "Current limit") <= 500:
        raise ValueError("Software recipe current limit must be greater than 0 and at most 500 mA")
    points = recipe.get("test_points")
    if not isinstance(points, list) or not points or len(points) > 128:
        raise ValueError("Recipe requires 1-128 test points")
    known_points = set()
    for point in points:
        if not isinstance(point, dict):
            raise ValueError("Test point must be an object")
        point_id = text(point.get("id"), "Test point ID")
        text(point.get("net"), "Net")
        if point_id in known_points:
            raise ValueError(f"Duplicate test point: {point_id}")
        known_points.add(point_id)
        for coordinate in ("x_mm", "y_mm"):
            if number(point.get(coordinate), coordinate) < 0:
                raise ValueError("Test point coordinates must be nonnegative")
    tests = recipe.get("tests")
    if not isinstance(tests, list) or not tests or len(tests) > 256:
        raise ValueError("Recipe requires 1-256 tests")
    prior_ids, prior_phase = set(), 0
    has_gate = False
    for test in tests:
        if not isinstance(test, dict):
            raise ValueError("Test must be an object")
        allowed = {"id", "label", "phase", "method", "points", "unit", "min", "max", "on_fail",
                   "depends_on", "settle_ms", "stimulus", "metadata"}
        if set(test) - allowed:
            raise ValueError("Unknown test fields: " + ", ".join(sorted(set(test) - allowed)))
        test_id = text(test.get("id"), "Test ID")
        text(test.get("label"), "Test label")
        if test_id in prior_ids:
            raise ValueError(f"Duplicate test: {test_id}")
        phase, method = test.get("phase"), test.get("method")
        if not isinstance(phase, str) or phase not in PHASES or PHASES[phase] < prior_phase:
            raise ValueError("Test phases must be unpowered, then powered, then functional")
        prior_phase = PHASES[phase]
        if not isinstance(method, str) or method not in METHOD_UNITS or test.get("unit") != METHOD_UNITS[method]:
            raise ValueError("Measurement method and unit must match the supported method table")
        if (phase == "unpowered") != (method == "resistance"):
            raise ValueError("Resistance tests must be unpowered; other methods require power")
        fail_action = test.get("on_fail")
        if fail_action not in ("stop", "continue"):
            raise ValueError("on_fail must be stop or continue")
        settle_ms = test.get("settle_ms", 0)
        if type(settle_ms) is not int or not 0 <= settle_ms <= 10000:
            raise ValueError("settle_ms must be an integer from 0 to 10000")
        if phase == "unpowered":
            has_gate = True
            if fail_action != "stop":
                raise ValueError("An unpowered gate failure must stop the run")
        lower, upper = number(test.get("min"), "Lower limit"), number(test.get("max"), "Upper limit")
        if lower > upper:
            raise ValueError("Lower limit must not exceed upper limit")
        if method in ("resistance", "current") and lower < 0:
            raise ValueError("Resistance and supply-current limits must be nonnegative")
        if method == "current" and upper > power["current_limit_ma"]:
            raise ValueError("Current-test upper limit exceeds the configured supply current limit")
        if method == "uart_echo" and (lower, upper) != (1, 1):
            raise ValueError("UART echo requires exact success value 1")
        selected = test.get("points")
        if not isinstance(selected, list) or len(selected) != 2 or any(not isinstance(p, str) or p not in known_points for p in selected):
            raise ValueError("Each test must reference two defined test points")
        if selected[0] == selected[1]:
            raise ValueError("A measurement must use two distinct test points")
        deps = test.get("depends_on", [])
        if not isinstance(deps, list) or any(not isinstance(dep, str) or dep not in prior_ids for dep in deps):
            raise ValueError("Dependencies must refer to earlier tests")
        stimulus = test.get("stimulus")
        if stimulus is not None:
            if phase != "functional" or not isinstance(stimulus, dict):
                raise ValueError("Stimulus is allowed only in functional tests")
            if set(stimulus) != {"kind", "point", "level"}:
                raise ValueError("GPIO stimulus accepts only kind, point and level")
            if stimulus.get("kind") != "gpio" or not isinstance(stimulus.get("point"), str) or stimulus["point"] not in known_points:
                raise ValueError("Only a defined GPIO stimulus point is supported")
            if type(stimulus.get("level")) is not int or stimulus["level"] not in (0, 1):
                raise ValueError("GPIO stimulus level must be integer 0 or 1")
        metadata = test.get("metadata")
        if metadata is not None:
            if not isinstance(metadata, dict) or len(metadata) > 32:
                raise ValueError("Test metadata must be an object with at most 32 entries")
            for key, value in metadata.items():
                text(key, "Metadata key")
                if isinstance(value, bool) or value is None:
                    continue
                if isinstance(value, str):
                    if len(value) > 1000:
                        raise ValueError("Metadata text must be at most 1000 characters")
                elif isinstance(value, (int, float)):
                    number(value, f"Metadata {key}")
                else:
                    raise ValueError("Metadata values must be text, numbers, booleans or null")
        prior_ids.add(test_id)
    if not has_gate:
        raise ValueError("At least one unpowered gate is required before any powered tests")
    return recipe


def recipe_digest(recipe):
    encoded = json.dumps(recipe, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_recipe(path):
    return validate_recipe(strict_json(Path(path).read_text(encoding="utf-8-sig")))
