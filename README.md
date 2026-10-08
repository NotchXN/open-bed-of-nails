# Open Bed of Nails

**Automated In-Circuit PCB Diagnostic Jig**

A standalone maintenance project for reproducible PCB checks and traceable repair evidence. A versioned recipe defines the board, test points, electrical settings, dependencies, stimuli, limits, and failure actions. Every run keeps its recipe snapshot, measurements, untested checks, and cleanup outcome.

**v0.1.0 is a working software prototype with an in-memory fixture simulator.** No physical instrument, MCU, relay, or PCB is controlled. Real acquisition, fixture firmware, verified schematics, and physical validation are future milestones. The demo board, fault values, limits, and point coordinates are synthetic.

## Run the demo

Use Python 3.11 or newer. Open a terminal in this repository:

```console
python -m bed_of_nails demo --output demo-output
```

Open `demo-output/report.html` in a normal browser, or open the included `examples/demo/report.html` immediately. The self-contained report requires no server, account, or network connection. It includes a selectable before/retest view, fixture point map, searchable measurement table, and action log.

The demo deliberately fails the 3.3 V rail in the before run. Its dependent functional checks are untested. The retest passes all eight checks, and comparison records that the rail failure cleared. This is simulated test evidence, not a claim that a physical board was repaired.

Files generated:

| File | Purpose |
| --- | --- |
| `before.json`, `after.json` | Complete run records with recipe snapshots and actions |
| `before.csv`, `after.csv` | Measurement values, limits, statuses, reasons, and measurement timestamps |
| `comparison.json` | Same-board, same-recipe retest comparison |
| `report.html` | Interactive offline comparison report |
| `scenarios/*.json` | Eleven deterministic fault-scenario records |
| `scenario-summary.json` | Status and shutdown outcomes for those scenarios |

## Commands

Validate the included recipe:

```console
python -m bed_of_nails validate bed_of_nails/demo-controller-rev-a.json
```

Run a simulated test and export evidence:

```console
python -m bed_of_nails run --serial DEMO-0001 --scenario healthy --output runs/healthy.json --csv runs/healthy.csv --report runs/healthy.html
python -m bed_of_nails run --serial DEMO-0001 --scenario short --output runs/short.json
```

List the simulator fault scenarios with descriptions, or summarize a saved run without rendering HTML:

```console
python -m bed_of_nails scenarios
python -m bed_of_nails summary runs/short.json
```

`summary` prints identity, counts, diagnostics, shutdown errors and every check that did not pass; it exits `1` when the run status is not `PASS`.

Compare and render saved records:

```console
python -m bed_of_nails compare examples/demo/before.json examples/demo/after.json --output runs/comparison.json --report runs/comparison.html
python -m bed_of_nails report examples/demo/after.json --output runs/retest.html
```

Exit codes: `0` for a passing run/retest/summary or completed non-test command, `1` for a run/retest/summary that did not pass, and `2` for input or file errors. `demo` returns zero when its artifacts are generated successfully, even though its intentionally faulty example runs do not pass. Output paths must be distinct and cannot overwrite source recipes or input runs.

Direct module execution requires no third-party packages. Optionally install with `python -m pip install .` to use the `bed-of-nails` command.

## What the runner enforces

- Recipe validation before invoking a backend.
- Initial output-off confirmation and cleared stimuli.
- Board model/revision matching and fixture readiness checks.
- Unpowered resistance gates before power-up; a failed or unavailable gate stops the sequence.
- Inclusive measurement limits and dependencies on earlier passing checks.
- Unavailable measurements recorded as `UNTESTED`, never silently passed.
- Best-effort stimulus reset, output-off confirmation, and transport closure during teardown.
- A shutdown-confirmation error prevents an overall `PASS`, even if every measurement passed.

These are software and simulator behaviors. A real fixture needs independent hardware interlocks, protection, discharge checks, and measured power-state feedback. Python cleanup cannot guarantee shutdown after a process kill, host crash, or loss of instrument power/control.

## Demo coverage and result meanings

The synthetic board has 16 mapped points and eight checks: ground continuity, supply-to-ground resistance signature, supply current, 5 V rail, 3.3 V rail, logic-buffer high/low output, and diagnostic UART echo. Some mapped points are unused by this recipe. A point map is not full board coverage.

| Overall status | Meaning |
| --- | --- |
| `PASS` | Every recipe check passed and final output shutdown was confirmed by the backend |
| `FAIL` | At least one measurement failed its limits |
| `INCOMPLETE` | Required checks were untested, with no failed measurement or abort/error |
| `ABORTED` | Fixture/identity readiness failed or the operator interrupted the run |
| `ERROR` | Instrument, result-validation, or cleanup error |

Errors and aborts take precedence over measurement failures. Results always retain every check. The simulated shutdown-error scenario intentionally shows eight passing measurements but an overall `ERROR` with shutdown unconfirmed.

The simulator implements the published demo wiring and check IDs. A different board recipe can be validated, but arbitrary circuit behavior is not simulated; unsupported paths remain untested. In-circuit resistance is a board-specific signature because parallel paths and semiconductor junctions affect it. This project does not identify every faulty component or provide a universal PCB tester.

## Development

```console
python -m unittest discover -s tests -v
```

The **58 tests** cover recipe validation (including bounded test `metadata`), gating and shutdown behavior, fault scenarios, interrupted/error runs, traceability, comparisons, exports, and full CLI workflows.

With Node.js available, an optional smoke test checks the generated report's JavaScript syntax, embedded demo data, run selection, filters, inspector and export wiring with a small DOM substitute (not a browser rendering test):

```console
node tests/report-smoke.cjs demo-output/report.html
```

GitHub Actions runs the suite, demo, compare, summary, the report smoke test and a packaging check on Windows/Linux with Python 3.11-3.13. See [CHANGELOG.md](CHANGELOG.md) for release notes.

```text
bed_of_nails/       Runner, simulator, recipe, file validation, CLI, HTML report
tests/             Software verification
examples/demo/     Ready-to-open simulated repair report and fault records
docs/              Architecture, formats, bench verification, roadmap
hardware/          Fixture requirements and conceptual OpenSCAD plate
.github/workflows/ Software CI
```

Read the [hardware plan](hardware/README.md), [recipe format](docs/recipe-format.md), [bench verification plan](docs/bench-verification.md), and [roadmap](docs/roadmap.md). The [validation record](docs/validation.md) lists checks performed and work still unverified.

## References and license

The runner uses Python's standard library. [OpenHTF](https://github.com/google/openhtf) is an optional future integration for hardware test execution and instrument plugs; it is not a dependency of this release. Hardware planning references [RP2040 documentation](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf) and [Keysight's in-circuit testing overview](https://www.keysight.com/de/de/products/in-circuit-test-for-manufacturing/in-circuit-test-systems.html?weglotPrefLang=en).

Original source, documentation, and the conceptual CAD file are supplied under the [MIT license](LICENSE). No third-party instrument software or fabrication-ready PCB design is bundled.
