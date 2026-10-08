"""Sequential board-specific testing with conservative completion semantics."""

from copy import deepcopy
from datetime import datetime, timezone
from time import monotonic
from uuid import uuid4

from . import __version__
from .backend import FixtureNotReady, MeasurementUnavailable
from .recipe import number, recipe_digest, text, validate_recipe


def now():
    return datetime.now(timezone.utc).isoformat()


def overall_status(results, *, errors=False, aborted=False):
    if errors or any(r["status"] == "ERROR" for r in results):
        return "ERROR"
    if aborted:
        return "ABORTED"
    if any(r["status"] == "FAIL" for r in results):
        return "FAIL"
    if not results or any(r["status"] == "UNTESTED" for r in results):
        return "INCOMPLETE"
    return "PASS"


def run_tests(recipe, backend, *, serial_number, operator="Bench operator", fixture_id="SIM-FIXTURE-01",
              board_model=None, board_revision=None):
    recipe = deepcopy(validate_recipe(recipe))
    for value, label in ((serial_number, "Board serial"), (operator, "Operator"), (fixture_id, "Fixture ID")):
        text(value, label)
    board_model = recipe["board_model"] if board_model is None else text(board_model, "Board model")
    board_revision = recipe["board_revision"] if board_revision is None else text(board_revision, "Board revision")
    start = monotonic()
    result = {
        "schema_version": 1, "tool_version": __version__, "run_id": str(uuid4()),
        "started_at": now(), "ended_at": None, "provenance": backend.provenance,
        "scenario": getattr(backend, "scenario", "unspecified"),
        "board": {"model": board_model, "revision": board_revision, "serial_number": serial_number},
        "operator": operator, "fixture_id": fixture_id,
        "recipe": {"id": recipe["id"], "version": recipe["version"], "sha256": recipe_digest(recipe),
                   "snapshot": recipe},
        "status": "INCOMPLETE", "diagnostics": [], "results": [],
        "shutdown": {"confirmed_off": False, "errors": []}, "actions": [],
    }
    results = result["results"]
    for test in recipe["tests"]:
        results.append({
            "id": test["id"], "label": test["label"], "phase": test["phase"],
            "method": test["method"], "points": test["points"], "unit": test["unit"],
            "min": test["min"], "max": test["max"], "value": None,
            "status": "UNTESTED", "reason": "Run did not reach this test", "measured_at": None,
        })
    errors, aborted, powered, active_result = False, False, False, None
    try:
        if backend.power_off() is not True:
            raise RuntimeError("Initial output-off state could not be confirmed")
        backend.clear_stimulus()
        if (board_model, board_revision) != (recipe["board_model"], recipe["board_revision"]):
            raise FixtureNotReady("Board model/revision does not match the recipe")
        backend.check_ready()
        completed = {}
        for test, row in zip(recipe["tests"], results):
            active_result = row
            failed_deps = [dep for dep in test.get("depends_on", []) if completed[dep] != "PASS"]
            if failed_deps:
                row["reason"] = "Prerequisites did not pass: " + ", ".join(failed_deps)
                completed[test["id"]] = "UNTESTED"
                continue
            backend.check_ready()
            if test["phase"] != "unpowered" and not powered:
                backend.power_on(**recipe["power"])
                powered = True
            backend.clear_stimulus()
            if "stimulus" in test:
                backend.apply_stimulus(test["stimulus"])
            backend.settle(test.get("settle_ms", 0))
            try:
                measurement = backend.measure(test)
            except MeasurementUnavailable as error:
                row["reason"] = str(error)
                completed[test["id"]] = "UNTESTED"
                # An unavailable unpowered gate cannot permit power-up.
                if test["phase"] == "unpowered":
                    result["diagnostics"].append("Unpowered gate unavailable; run stopped before power-up")
                    break
                continue
            value = number(measurement.value, "Instrument result")
            if measurement.unit != test["unit"]:
                raise RuntimeError("Instrument unit does not match recipe unit")
            row.update(value=value, measured_at=now(), status="PASS" if row["min"] <= value <= row["max"] else "FAIL")
            row["reason"] = "Within inclusive limits" if row["status"] == "PASS" else "Outside inclusive limits"
            completed[test["id"]] = row["status"]
            if row["status"] == "FAIL" and test["on_fail"] == "stop":
                result["diagnostics"].append(f"Stopped on failed gate/check: {test['id']}")
                break
    except FixtureNotReady as error:
        aborted = True
        if active_result is not None and active_result["status"] == "UNTESTED":
            active_result["reason"] = str(error)
        result["diagnostics"].append(str(error))
    except KeyboardInterrupt:
        aborted = True
        result["diagnostics"].append("Operator interrupted the run")
    except Exception as error:
        errors = True
        if active_result is not None:
            active_result.update(status="ERROR", reason=str(error))
        result["diagnostics"].append(str(error))
    finally:
        for action in (backend.clear_stimulus, backend.power_off, backend.close):
            try:
                response = action()
                if action == backend.power_off:
                    if response is not True:
                        raise RuntimeError("Final output-off state could not be confirmed")
                    result["shutdown"]["confirmed_off"] = True
            except Exception as error:
                errors = True
                result["shutdown"]["errors"].append(str(error))
        result["ended_at"] = now()
        result["duration_ms"] = round((monotonic() - start) * 1000, 3)
        result["actions"] = deepcopy(backend.actions)
    result["status"] = overall_status(results, errors=errors, aborted=aborted)
    result["termination"] = {"errors": errors, "aborted": aborted}
    return result
