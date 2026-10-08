import contextlib
from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import shutil
import unittest
import uuid

from bed_of_nails.__main__ import main, recipe_default
from bed_of_nails.backend import Measurement, MeasurementUnavailable, SCENARIOS, Simulator
from bed_of_nails.recipe import load_recipe, recipe_digest, strict_json, validate_recipe
from bed_of_nails.records import compare_runs, counts, export_csv, load_run, validate_run, write_json
from bed_of_nails.report import render_report
from bed_of_nails.runner import run_tests


@contextlib.contextmanager
def scratch():
    root = (Path.cwd() / ".test-work").resolve()
    root.mkdir(exist_ok=True)
    path = root / uuid.uuid4().hex
    path.mkdir()
    try:
        yield path
    finally:
        if path.resolve().parent != root or path.is_symlink():
            raise RuntimeError("Test cleanup escaped the scratch directory")
        shutil.rmtree(path)


def recipe():
    return load_recipe(recipe_default())


def run(scenario="healthy", backend=None, **kwargs):
    return run_tests(recipe(), backend or Simulator(scenario), serial_number="TEST-001", **kwargs)


class RecipeTests(unittest.TestCase):
    def test_demo_recipe(self):
        source = recipe()
        self.assertEqual(len(source["test_points"]), 16)
        self.assertEqual(len(source["tests"]), 8)

    def test_digest_ignores_key_order(self):
        source = recipe()
        self.assertEqual(recipe_digest(source), recipe_digest(dict(reversed(list(source.items())))))

    def test_digest_changes_with_limits(self):
        source = recipe()
        edited = deepcopy(source)
        edited["tests"][0]["max"] = 0.5
        self.assertNotEqual(recipe_digest(source), recipe_digest(edited))

    def invalid(self, edit):
        source = recipe()
        edit(source)
        with self.assertRaises(ValueError):
            validate_recipe(source)

    def test_schema_and_identity(self):
        for key, value in (("schema_version", True), ("version", ""), ("board_model", None)):
            self.invalid(lambda r, k=key, v=value: r.update({k: v}))

    def test_power_envelope(self):
        for key, value in (("voltage_v", 0), ("voltage_v", 25), ("current_limit_ma", 501), ("voltage_v", float("nan"))):
            self.invalid(lambda r, k=key, v=value: r["power"].update({k: v}))

    def test_duplicate_points(self):
        self.invalid(lambda r: r["test_points"].append(r["test_points"][0]))

    def test_duplicate_tests(self):
        self.invalid(lambda r: r["tests"].append(r["tests"][-1]))

    def test_unknown_point(self):
        self.invalid(lambda r: r["tests"][0].update(points=["TP02", "MISSING"]))

    def test_bad_point_type(self):
        self.invalid(lambda r: r["tests"][0].update(points=[{}, "TP02"]))

    def test_phase_order_and_gate_presence(self):
        self.invalid(lambda r: r["tests"].reverse())
        self.invalid(lambda r: r.update(tests=r["tests"][2:]))

    def test_gate_failure_must_stop(self):
        self.invalid(lambda r: r["tests"][0].update(on_fail="continue"))

    def test_resistance_never_powered(self):
        self.invalid(lambda r: r["tests"][2].update(method="resistance", unit="ohm"))

    def test_method_units_and_limits(self):
        self.invalid(lambda r: r["tests"][0].update(unit="V"))
        self.invalid(lambda r: r["tests"][0].update(min=2, max=1))
        self.invalid(lambda r: r["tests"][0].update(min=True))
        self.invalid(lambda r: r["tests"][2].update(max=101))

    def test_forward_dependency_rejected(self):
        self.invalid(lambda r: r["tests"][0].update(depends_on=["rail_3v3"]))

    def test_stimulus_and_settling(self):
        self.invalid(lambda r: r["tests"][0].update(stimulus={"kind": "gpio", "point": "TP10", "level": 1}))
        self.invalid(lambda r: r["tests"][5]["stimulus"].update(level=True))
        self.invalid(lambda r: r["tests"][0].update(settle_ms=-1))

    def test_nonfinite_and_duplicate_json(self):
        with self.assertRaises(ValueError):
            strict_json('{"x":NaN}')
        with self.assertRaises(ValueError):
            strict_json('{"x":1,"x":2}')

    def test_unknown_execution_fields_are_not_silently_ignored(self):
        self.invalid(lambda r: r["tests"][0].update(settle_milliseconds=500))
        self.invalid(lambda r: r["power"].update(enable_without_interlock=True))

    def test_metadata_must_be_a_simple_object(self):
        valid = deepcopy(recipe())
        valid["tests"][0]["metadata"] = {"note": "probe pad near C12", "torque_ncm": 2.5, "verified": True, "ref": None}
        validate_recipe(valid)
        self.invalid(lambda r: r["tests"][0].update(metadata="free text"))
        self.invalid(lambda r: r["tests"][0].update(metadata={"nested": {"x": 1}}))
        self.invalid(lambda r: r["tests"][0].update(metadata={"list": [1, 2]}))
        self.invalid(lambda r: r["tests"][0].update(metadata={"nan": float("nan")}))
        self.invalid(lambda r: r["tests"][0].update(metadata={"long": "x" * 1001}))
        self.invalid(lambda r: r["tests"][0].update(metadata={str(i): i for i in range(33)}))


class RunnerTests(unittest.TestCase):
    def test_healthy_pass_and_cutoff(self):
        backend = Simulator()
        result = run(backend=backend)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(counts(result)["PASS"], 8)
        self.assertTrue(result["shutdown"]["confirmed_off"])
        self.assertFalse(backend.powered)
        self.assertIsNone(backend.stimulus)
        self.assertEqual(result["actions"][-1]["action"], "close")

    def test_power_only_after_unpowered_gates(self):
        actions = run()["actions"]
        enable = next(i for i, a in enumerate(actions) if a["action"] == "power_on")
        preceding = [a["test_id"] for a in actions[:enable] if a["action"] == "measure"]
        self.assertEqual(preceding, ["ground_continuity", "supply_isolation"])

    def test_short_does_not_energize(self):
        result = run("short")
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(any(a["action"] == "power_on" for a in result["actions"]))
        self.assertEqual(counts(result)["UNTESTED"], 6)

    def test_open_does_not_energize(self):
        result = run("open")
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(any(a["action"] == "power_on" for a in result["actions"]))

    def test_failed_rail_skips_dependent_stimuli(self):
        result = run("missing-rail")
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(counts(result), {"ERROR": 0, "FAIL": 1, "PASS": 4, "UNTESTED": 3})
        self.assertFalse(any(a["action"] == "stimulus" for a in result["actions"]))

    def test_overcurrent_stops_other_powered_checks(self):
        result = run("overcurrent")
        measured = [a["test_id"] for a in result["actions"] if a["action"] == "measure"]
        self.assertEqual(measured, ["ground_continuity", "supply_isolation", "supply_current"])
        self.assertTrue(result["shutdown"]["confirmed_off"])

    def test_open_interlock_and_bad_contacts(self):
        for scenario in ("interlock-open", "contact-failure"):
            result = run(scenario)
            self.assertEqual(result["status"], "ABORTED")
            self.assertEqual(counts(result)["UNTESTED"], 8)
            self.assertFalse(any(a["action"] == "power_on" for a in result["actions"]))

    def test_interlock_trip_aborts_and_records_cutoff(self):
        result = run("interlock-trip")
        self.assertEqual(result["status"], "ABORTED")
        self.assertTrue(any(a["action"] == "hardware_interlock_trip" for a in result["actions"]))
        self.assertTrue(result["shutdown"]["confirmed_off"])

    def test_wrong_board_revision(self):
        result = run(board_revision="B")
        self.assertEqual(result["status"], "ABORTED")
        self.assertFalse(any(a["action"] == "power_on" for a in result["actions"]))

    def test_unavailable_uart_not_pass(self):
        result = run("unsupported-uart")
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(counts(result)["UNTESTED"], 1)

    def test_unavailable_gate_cannot_allow_power(self):
        class MissingGate(Simulator):
            def measure(self, test):
                raise MeasurementUnavailable("No resistance instrument")
        result = run(backend=MissingGate())
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertFalse(any(a["action"] == "power_on" for a in result["actions"]))

    def test_instrument_failure_is_error(self):
        result = run("instrument-error")
        self.assertEqual(result["status"], "ERROR")
        self.assertTrue(result["shutdown"]["confirmed_off"])

    def test_unknown_shutdown_never_pass(self):
        result = run("shutdown-error")
        self.assertEqual(counts(result)["PASS"], 8)
        self.assertEqual(result["status"], "ERROR")
        self.assertFalse(result["shutdown"]["confirmed_off"])
        self.assertTrue(result["shutdown"]["errors"])

    def test_nan_and_wrong_unit_rejected(self):
        for measurement in (Measurement(float("nan"), "ohm"), Measurement(0.1, "V")):
            class BadInstrument(Simulator):
                def measure(self, test):
                    return measurement
            result = run(backend=BadInstrument())
            self.assertEqual(result["status"], "ERROR")
            self.assertTrue(result["shutdown"]["confirmed_off"])

    def test_partial_enable_failure_still_shuts_down(self):
        class EnableError(Simulator):
            def power_on(self, **kwargs):
                self.powered = True
                raise RuntimeError("Enable acknowledgment lost")
        backend = EnableError()
        result = run(backend=backend)
        self.assertEqual(result["status"], "ERROR")
        self.assertFalse(backend.powered)

    def test_keyboard_interrupt_records_abort_and_cleanup(self):
        class Interrupted(Simulator):
            def measure(self, test):
                raise KeyboardInterrupt()
        result = run(backend=Interrupted())
        self.assertEqual(result["status"], "ABORTED")
        self.assertTrue(result["shutdown"]["confirmed_off"])

    def test_close_failure_keeps_error(self):
        class CloseError(Simulator):
            def close(self):
                super().close()
                raise RuntimeError("Transport close failed")
        result = run(backend=CloseError())
        self.assertEqual(result["status"], "ERROR")
        self.assertTrue(result["shutdown"]["confirmed_off"])

    def test_actual_stimulus_determines_simulated_logic_value(self):
        source = recipe()
        source["tests"][5]["stimulus"]["level"] = 0
        result = run_tests(source, Simulator(), serial_number="TEST-001")
        self.assertEqual(result["results"][5]["value"], 0.04)
        self.assertEqual(result["results"][5]["status"], "FAIL")

    def test_all_scenarios_produce_valid_records(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                validate_run(run(scenario))

    def test_recipe_snapshot_not_affected_by_later_edit(self):
        source = recipe()
        result = run_tests(source, Simulator(), serial_number="TEST-001")
        source["tests"][0]["max"] = 500
        self.assertEqual(result["recipe"]["snapshot"]["tests"][0]["max"], 1)


class RecordTests(unittest.TestCase):
    def test_saved_run_roundtrip(self):
        with scratch() as path:
            result = run()
            write_json(result, path / "run.json")
            self.assertEqual(load_run(path / "run.json"), result)

    def test_cleared_failure_comparison(self):
        result = compare_runs(run("missing-rail"), run())
        self.assertEqual(result["outcome"], "PASS_ON_RETEST")
        self.assertEqual(result["cleared_failures"], ["rail_3v3"])

    def test_identical_run_rejected(self):
        result = run()
        with self.assertRaises(ValueError):
            compare_runs(result, result)

    def test_mismatched_identity_fixture_or_origin(self):
        for field in ("board", "fixture_id", "provenance"):
            before, after = run(), run()
            if field == "board":
                after[field]["serial_number"] = "OTHER-BOARD"
            else:
                after[field] = "different"
            with self.assertRaisesRegex(ValueError, "matching"):
                compare_runs(before, after)

    def test_recipe_limit_change_prevents_comparison(self):
        source = recipe()
        before = run()
        source["tests"][0]["max"] = 0.9
        after = run_tests(source, Simulator(), serial_number="TEST-001")
        with self.assertRaisesRegex(ValueError, "same recipe"):
            compare_runs(before, after)

    def test_earlier_retest_rejected(self):
        before, after = run(), run()
        after["started_at"] = "2020-01-01T00:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "precedes"):
            compare_runs(before, after)

    def test_retest_not_passed(self):
        result = compare_runs(run(), run("missing-rail"))
        self.assertEqual(result["outcome"], "RETEST_NOT_PASSED")
        self.assertEqual(result["new_failures"], ["rail_3v3"])

    def test_tampered_recipe_or_test_status_rejected(self):
        result = run()
        result["recipe"]["snapshot"]["tests"][0]["max"] = 5
        with self.assertRaisesRegex(ValueError, "digest"):
            validate_run(result)
        result = run("missing-rail")
        result["results"][4]["status"] = "PASS"
        with self.assertRaisesRegex(ValueError, "measurement"):
            validate_run(result)

    def test_untested_cannot_be_hidden_by_overall_pass(self):
        result = run("unsupported-uart")
        result["status"] = "PASS"
        with self.assertRaisesRegex(ValueError, "Overall status"):
            validate_run(result)

    def test_missing_results_rejected(self):
        result = run()
        result["results"].pop()
        with self.assertRaises(ValueError):
            validate_run(result)

    def test_report_escapes_script_tags(self):
        with scratch() as path:
            result = run(operator="</script><script>alert(1)</script>")
            render_report([result], path / "report.html")
            content = (path / "report.html").read_text(encoding="utf-8")
            self.assertNotIn(result["operator"], content)
            self.assertIn("\\u003c/script>", content)
            self.assertNotIn("/*RUN_DATA*/null", content)

    def test_csv_neutralizes_labels_without_changing_numbers(self):
        with scratch() as path:
            result = run()
            result["board"]["serial_number"] = "=1+1"
            export_csv(result, path / "run.csv")
            with (path / "run.csv").open(encoding="utf-8", newline="") as stream:
                first = next(csv.DictReader(stream))
            self.assertEqual(first["serial_number"], "'=1+1")
            self.assertEqual(float(first["value"]), 0.18)
            self.assertEqual(first["measured_at"], result["results"][0]["measured_at"])

    def test_csv_measured_at_blank_for_untested(self):
        with scratch() as path:
            result = run("missing-rail")
            export_csv(result, path / "run.csv")
            with (path / "run.csv").open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            untested = [row for row in rows if row["status"] == "UNTESTED"]
            self.assertTrue(untested)
            self.assertTrue(all(row["measured_at"] == "" for row in untested))


class CliTests(unittest.TestCase):
    def invoke(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(args)
        return code, out.getvalue(), err.getvalue()

    def test_demo_compare_report_workflow(self):
        with scratch() as path:
            code, out, err = self.invoke(["demo", "--output", str(path)])
            self.assertEqual((code, err), (0, ""))
            self.assertEqual(json.loads(out)["scenarios"], 11)
            code, _, err = self.invoke(["compare", str(path / "before.json"), str(path / "after.json"),
                                        "--output", str(path / "retest.json"), "--report", str(path / "retest.html")])
            self.assertEqual((code, err), (0, ""))
            code, _, err = self.invoke(["report", str(path / "after.json"), "--output", str(path / "single.html")])
            self.assertEqual((code, err), (0, ""))

    def test_run_pass_fail_exit_codes_and_exports(self):
        with scratch() as path:
            for scenario, expected in (("healthy", 0), ("short", 1), ("shutdown-error", 1)):
                code, _, err = self.invoke(["run", "--serial", "TEST-001", "--scenario", scenario,
                                            "--output", str(path / f"{scenario}.json"),
                                            "--csv", str(path / f"{scenario}.csv"),
                                            "--report", str(path / f"{scenario}.html")])
                self.assertEqual((code, err), (expected, ""))

    def test_output_cannot_overwrite_input(self):
        with scratch() as path:
            target = path / "recipe.json"
            write_json(recipe(), target)
            original = target.read_bytes()
            code, _, err = self.invoke(["run", "--serial", "TEST-001", "--recipe", str(target), "--output", str(target)])
            self.assertEqual(code, 2)
            self.assertIn("overwrite", err)
            self.assertEqual(target.read_bytes(), original)

    def test_output_paths_must_differ(self):
        with scratch() as path:
            target = str(path / "same.json")
            code, _, err = self.invoke(["run", "--serial", "TEST-001", "--output", target, "--report", target])
            self.assertEqual(code, 2)
            self.assertIn("distinct", err)

    def test_scenarios_command_lists_every_simulator_scenario(self):
        code, out, err = self.invoke(["scenarios"])
        self.assertEqual((code, err), (0, ""))
        listed = json.loads(out)["scenarios"]
        self.assertEqual([item["name"] for item in listed], list(SCENARIOS))
        self.assertTrue(all(item["description"] for item in listed))

    def test_summary_command_reports_attention_items_and_exit_code(self):
        with scratch() as path:
            write_json(run("missing-rail"), path / "fail.json")
            write_json(run(), path / "pass.json")
            code, out, err = self.invoke(["summary", str(path / "fail.json")])
            self.assertEqual((code, err), (1, ""))
            digest = json.loads(out)
            self.assertEqual(digest["status"], "FAIL")
            self.assertEqual(digest["counts"]["UNTESTED"], 3)
            self.assertEqual([item["id"] for item in digest["attention"]][:1], ["rail_3v3"])
            self.assertEqual(len(digest["recipe"]["sha256"]), 64)
            code, out, err = self.invoke(["summary", str(path / "pass.json")])
            self.assertEqual((code, err), (0, ""))
            self.assertEqual(json.loads(out)["attention"], [])

    def test_validate_and_malformed_file_errors(self):
        code, _, err = self.invoke(["validate", str(recipe_default())])
        self.assertEqual((code, err), (0, ""))
        with scratch() as path:
            target = path / "bad.json"
            target.write_text('{"board":[]}', encoding="utf-8")
            code, _, err = self.invoke(["report", str(target), "--output", str(path / "report.html")])
            self.assertEqual(code, 2)
            self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()
