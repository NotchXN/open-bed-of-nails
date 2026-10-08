"""Run: python -m bed_of_nails --help."""

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .backend import SCENARIOS, Simulator
from .recipe import load_recipe
from .records import compare_runs, counts, export_csv, load_run, validate_run, write_json
from .report import render_report
from .runner import run_tests


def recipe_default():
    return Path(__file__).with_name("demo-controller-rev-a.json")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Standalone PCB test runner (simulation-only v0.1)")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Generate before/after repair examples and all fault scenarios")
    demo.add_argument("--output", type=Path, default=Path("demo-output"))
    demo.add_argument("--recipe", type=Path, default=recipe_default())
    run = commands.add_parser("run", help="Execute a recipe using the in-memory simulator")
    run.add_argument("--recipe", type=Path, default=recipe_default())
    run.add_argument("--scenario", choices=SCENARIOS, default="healthy")
    run.add_argument("--serial", required=True)
    run.add_argument("--operator", default="Bench operator")
    run.add_argument("--fixture", default="SIM-FIXTURE-01")
    run.add_argument("--board-model")
    run.add_argument("--board-revision")
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--report", type=Path)
    run.add_argument("--csv", type=Path)
    check = commands.add_parser("validate", help="Validate a recipe without running tests")
    check.add_argument("recipe", type=Path)
    commands.add_parser("scenarios", help="List the simulator fault scenarios and their meaning")
    inspect = commands.add_parser("summary", help="Summarize a saved run record without rendering a report")
    inspect.add_argument("input", type=Path)
    compare = commands.add_parser("compare", help="Compare matching before/after runs")
    compare.add_argument("before", type=Path)
    compare.add_argument("after", type=Path)
    compare.add_argument("--output", type=Path, required=True)
    compare.add_argument("--report", type=Path)
    report = commands.add_parser("report", help="Render a saved run")
    report.add_argument("input", type=Path)
    report.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def summary(run):
    return {"status": run["status"], "provenance": run["provenance"], "run_id": run["run_id"],
            "counts": counts(run), "shutdown_confirmed": run["shutdown"]["confirmed_off"]}


def run_summary(run):
    """Operator-facing digest of a validated run: identity, counts and attention items."""
    attention = [{"id": row["id"], "label": row["label"], "status": row["status"], "reason": row["reason"],
                  "value": row["value"], "unit": row["unit"], "min": row["min"], "max": row["max"]}
                 for row in run["results"] if row["status"] != "PASS"]
    return {
        **summary(run), "scenario": run["scenario"], "board": run["board"],
        "recipe": {"id": run["recipe"]["id"], "version": run["recipe"]["version"],
                   "sha256": run["recipe"]["sha256"]},
        "fixture_id": run["fixture_id"], "operator": run["operator"],
        "started_at": run["started_at"], "ended_at": run["ended_at"], "duration_ms": run["duration_ms"],
        "termination": run["termination"], "shutdown_errors": run["shutdown"]["errors"],
        "diagnostics": run["diagnostics"], "attention": attention,
    }


def check_paths(inputs, outputs):
    inputs = {p.resolve() for p in inputs if p is not None}
    outputs = [p.resolve() for p in outputs if p is not None]
    if len(set(outputs)) != len(outputs):
        raise ValueError("Output paths must be distinct")
    if inputs.intersection(outputs):
        raise ValueError("Output must not overwrite an input recipe or run")


def demo(args):
    recipe = load_recipe(args.recipe)
    outputs = [args.output / name for name in
               ("before.json", "after.json", "before.csv", "after.csv", "comparison.json", "report.html", "scenario-summary.json")]
    outputs.extend(args.output / "scenarios" / f"{scenario}.json" for scenario in SCENARIOS)
    check_paths([args.recipe], outputs)
    before = run_tests(recipe, Simulator("missing-rail"), serial_number="DEMO-0001")
    after = run_tests(recipe, Simulator("healthy"), serial_number="DEMO-0001")
    for name, run in (("before", before), ("after", after)):
        write_json(validate_run(run), args.output / f"{name}.json")
        export_csv(run, args.output / f"{name}.csv")
    comparison = compare_runs(before, after)
    write_json(comparison, args.output / "comparison.json")
    render_report([before, after], args.output / "report.html", comparison=True)
    scenarios = []
    for scenario in SCENARIOS:
        run = run_tests(recipe, Simulator(scenario), serial_number="DEMO-FAULT-001")
        write_json(validate_run(run), args.output / "scenarios" / f"{scenario}.json")
        scenarios.append({"scenario": scenario, **summary(run)})
    write_json(scenarios, args.output / "scenario-summary.json")
    return {"provenance": "simulated", "before": before["status"], "after": after["status"],
            "cleared_failures": comparison["cleared_failures"], "scenarios": len(scenarios),
            "output": str(args.output.resolve())}


def main(argv=None):
    args = parse_args(argv)
    try:
        exit_code = 0
        if args.command == "demo":
            result = demo(args)
        elif args.command == "validate":
            recipe = load_recipe(args.recipe)
            result = {"valid": True, "recipe": recipe["id"], "version": recipe["version"], "tests": len(recipe["tests"])}
        elif args.command == "scenarios":
            result = {"provenance": "simulated", "scenarios": [{"name": name, "description": description}
                                                              for name, description in SCENARIOS.items()]}
        elif args.command == "summary":
            run = load_run(args.input)
            result = run_summary(run)
            exit_code = 0 if run["status"] == "PASS" else 1
        elif args.command == "run":
            check_paths([args.recipe], [args.output, args.csv, args.report])
            recipe = load_recipe(args.recipe)
            run = run_tests(recipe, Simulator(args.scenario), serial_number=args.serial,
                            operator=args.operator, fixture_id=args.fixture,
                            board_model=args.board_model, board_revision=args.board_revision)
            write_json(validate_run(run), args.output)
            if args.csv:
                export_csv(run, args.csv)
            if args.report:
                render_report([run], args.report)
            result = summary(run)
            exit_code = 0 if run["status"] == "PASS" else 1
        elif args.command == "compare":
            check_paths([args.before, args.after], [args.output, args.report])
            before, after = load_run(args.before), load_run(args.after)
            result = compare_runs(before, after)
            write_json(result, args.output)
            if args.report:
                render_report([before, after], args.report, comparison=True)
            exit_code = 0 if after["status"] == "PASS" else 1
        else:
            check_paths([args.input], [args.output])
            result = {"report": str(render_report([load_run(args.input)], args.output).resolve())}
        print(json.dumps(result, indent=2, allow_nan=False))
        return exit_code
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
