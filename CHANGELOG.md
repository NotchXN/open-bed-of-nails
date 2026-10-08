# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.1] - 2026-10-08

### Added

- `scenarios` command listing every simulator fault scenario with its description.
- `summary` command producing an operator digest of a saved run (identity, counts,
  diagnostics, shutdown errors and every check that did not pass) with a pass/fail exit code.
- `measured_at` column in CSV exports.
- `tests/report-smoke.cjs` Node.js smoke test for the generated report, run in CI.
- CI exercises `summary`, a packaging install and the console script, and uploads the
  demo output as a workflow artifact.

### Fixed

- Optional test `metadata` was accepted with any JSON type. It is now validated as a
  flat, bounded object of text, finite numbers, booleans or null so that recipes stay
  printable and hash-stable.

### Changed

- `pyproject.toml` uses the SPDX `license` expression and declares classifiers.

## [0.1.0] - 2026-10-03

- Initial standalone software prototype: recipe validation, in-memory simulator,
  dependency-aware runner, run records, comparisons, CSV export, offline HTML report,
  tests, CI and hardware planning.
