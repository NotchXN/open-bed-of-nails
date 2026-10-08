# Validation record

Prepared 3 October 2026.

## Completed

- 54 automated tests passed locally on Python 3.12.14 on Windows.
- Demo generation and full CLI run/export/compare/report workflows passed.
- Eleven deterministic simulation scenarios produced internally consistent run records.
- Gates prevent simulated power-up after failed/unavailable unpowered checks.
- Missing-rail prerequisites suppress dependent functional stimuli.
- Unavailable UART results stay untested; instrument and shutdown errors prevent passing status.
- Partial power-enable errors and operator interrupts still execute software cleanup in tests.
- Run hashes, measurements/statuses, identity-compatible comparisons, CSV formula handling, report script-tag escaping, and source/output path protection checked.

The generated report's embedded JavaScript syntax and JSON payload are checked separately during local packaging. This is not a browser interaction or visual layout test.

## Still unverified

- Physical fixture contacts, instrument acquisition, controller firmware, hardware interlock/cutoff, discharge, electrical ratings, and measurement accuracy.
- Report visual layout and controls in a browser. The app's browser policy disallows local `file:` previews; no browser workaround was attempted for this build.
- Concept plate rendering, manufacturability, receiver fit, and board alignment.
- Remote GitHub Actions matrix; this repository has not been published.

Simulation results and software tests establish implementation behavior under the tested inputs. They do not establish physical hardware behavior or complete PCB fault coverage.

## Revision 0.1.1 (8 October 2026)

- Full suite re-run on Linux with Python 3.13: 58 tests passed.
- New tests cover bounded test metadata validation, `measured_at` in CSV exports, and the `scenarios`/`summary` commands including exit codes.
- Report JavaScript executed against the regenerated demo output with the Node.js DOM-substitute smoke test (`tests/report-smoke.cjs`); still not a browser rendering test.
- Packaging verified with `python -m pip install .` followed by the console script `--version`.
- `examples/demo/` regenerated from the 0.1.1 code so bundled artifacts match the current output format.
- The remote GitHub Actions matrix has still not been run; the workflow now also performs the steps above.
