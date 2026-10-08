"""Portable reports and same-board, same-recipe retest comparison."""

import csv
from datetime import datetime
import json
from pathlib import Path

from .recipe import number, recipe_digest, strict_json, text, validate_recipe
from .runner import overall_status

STATUSES = {"PASS", "FAIL", "UNTESTED", "ERROR"}


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Timestamp must be ISO text with a timezone")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Timestamp must include a timezone offset")
    return stamp


def validate_run(run):
    if not isinstance(run, dict) or type(run.get("schema_version")) is not int or run["schema_version"] != 1:
        raise ValueError("Run requires schema_version 1")
    for key in ("run_id", "tool_version", "operator", "fixture_id", "provenance", "scenario"):
        text(run.get(key), key)
    for key in ("board", "recipe", "shutdown", "termination"):
        if not isinstance(run.get(key), dict):
            raise ValueError(f"{key} must be an object")
    if not isinstance(run.get("actions"), list) or not isinstance(run.get("diagnostics"), list):
        raise ValueError("Actions and diagnostics must be lists")
    if timestamp(run["ended_at"]) < timestamp(run["started_at"]):
        raise ValueError("Run end precedes start")
    number(run["duration_ms"], "Duration")
    if run["duration_ms"] < 0:
        raise ValueError("Duration cannot be negative")
    for key in ("model", "revision", "serial_number"):
        text(run["board"][key], key)
    snapshot = validate_recipe(run["recipe"]["snapshot"])
    if run["recipe"]["sha256"] != recipe_digest(snapshot):
        raise ValueError("Recipe snapshot digest does not match")
    if (run["recipe"]["id"], run["recipe"]["version"]) != (snapshot["id"], snapshot["version"]):
        raise ValueError("Recipe identity does not match its snapshot")
    rows = run["results"]
    if not isinstance(rows, list) or len(rows) != len(snapshot["tests"]):
        raise ValueError("Run must include every recipe test, including untested checks")
    for row, test in zip(rows, snapshot["tests"]):
        if not isinstance(row, dict):
            raise ValueError("Each test result must be an object")
        for key in ("id", "label", "phase", "method", "points", "unit", "min", "max"):
            if row.get(key) != test[key]:
                raise ValueError(f"Result {key} differs from the recipe snapshot")
        if not isinstance(row.get("status"), str) or row["status"] not in STATUSES or not isinstance(row.get("reason"), str):
            raise ValueError("Invalid test status or reason")
        if row["status"] in ("PASS", "FAIL"):
            value = number(row.get("value"), "Measured value")
            expected = "PASS" if test["min"] <= value <= test["max"] else "FAIL"
            if row["status"] != expected:
                raise ValueError("Test status does not agree with its measurement and limits")
            timestamp(row["measured_at"])
        elif row.get("value") is not None:
            number(row["value"], "Recorded value")
    shutdown, termination = run["shutdown"], run["termination"]
    if type(shutdown.get("confirmed_off")) is not bool:
        raise ValueError("Shutdown confirmation must be a boolean")
    for key in ("errors", "aborted"):
        if type(termination.get(key)) is not bool:
            raise ValueError("Termination flags must be boolean")
    if not shutdown["confirmed_off"] and not termination["errors"]:
        raise ValueError("Unconfirmed shutdown must make the run an error")
    expected_status = overall_status(rows, **termination)
    if run["status"] != expected_status:
        raise ValueError("Overall status conflicts with test results or termination flags")
    if run["status"] == "PASS" and (run["board"]["model"], run["board"]["revision"]) != (snapshot["board_model"], snapshot["board_revision"]):
        raise ValueError("Passing board identity does not match recipe")
    return run


def load_run(path):
    try:
        return validate_run(strict_json(Path(path).read_text(encoding="utf-8-sig")))
    except (KeyError, TypeError) as error:
        raise ValueError(f"Malformed run record: {error}") from error


def write_json(data, path):
    encoded = json.dumps(data, indent=2, allow_nan=False)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(encoded + "\n", encoding="utf-8")


def counts(run):
    return {status: sum(row["status"] == status for row in run["results"]) for status in sorted(STATUSES)}


def compare_runs(before, after):
    validate_run(before)
    validate_run(after)
    if before["run_id"] == after["run_id"]:
        raise ValueError("Comparison requires two distinct runs")
    for key in ("board", "fixture_id", "provenance"):
        if before[key] != after[key]:
            raise ValueError(f"Comparison requires matching {key}")
    if before["recipe"]["sha256"] != after["recipe"]["sha256"]:
        raise ValueError("Comparison requires the same recipe content and limits")
    if timestamp(after["started_at"]) < timestamp(before["started_at"]):
        raise ValueError("Retest precedes the before run")
    changes = []
    for first, second in zip(before["results"], after["results"]):
        changes.append({"test_id": first["id"], "label": first["label"], "unit": first["unit"],
                        "before_status": first["status"], "after_status": second["status"],
                        "before_value": first["value"], "after_value": second["value"]})
    cleared = [c["test_id"] for c in changes if c["before_status"] == "FAIL" and c["after_status"] == "PASS"]
    new_failures = [c["test_id"] for c in changes if c["before_status"] == "PASS" and c["after_status"] == "FAIL"]
    return {
        "schema_version": 1, "kind": "repair_comparison", "provenance": before["provenance"],
        "board": before["board"], "recipe_sha256": before["recipe"]["sha256"],
        "outcome": "PASS_ON_RETEST" if after["status"] == "PASS" else "RETEST_NOT_PASSED",
        "before_run_id": before["run_id"], "after_run_id": after["run_id"],
        "cleared_failures": cleared, "new_failures": new_failures, "changes": changes,
    }


def csv_text(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def export_csv(run, path):
    validate_run(run)
    fields = ["run_id", "serial_number", "recipe_version", "provenance", "test_id", "label", "phase",
              "status", "value", "unit", "min", "max", "reason", "measured_at"]
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for test in run["results"]:
            row = {"run_id": run["run_id"], "serial_number": run["board"]["serial_number"],
                   "recipe_version": run["recipe"]["version"], "provenance": run["provenance"],
                   "test_id": test["id"], **{key: test[key] for key in fields[5:]}}
            row["measured_at"] = "" if row["measured_at"] is None else row["measured_at"]
            writer.writerow({key: csv_text(value) if isinstance(value, str) else value for key, value in row.items()})
