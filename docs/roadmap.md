# Roadmap

## v0.1 - Software foundation (implemented)

Recipe validation, simulator, dependency-aware test runner, conservative status/cleanup handling, portable run records, retest comparison, CSV exports, offline HTML report, tests, CI configuration, and hardware planning. v0.1.1 adds bounded metadata validation, `scenarios`/`summary` commands, measurement timestamps in CSV and a report smoke test.

## v0.2 - Real board and receive/status prototype

Choose one board model/revision. Produce a verified point map and mechanical adapter. Build controller firmware for status, interlock/voltage feedback, watchdog, and output-off confirmation before enabling powered testing. Define a bounded USB command protocol with request IDs and timeouts.

## v0.3 - Instrument and switching adapters

Add actual DMM/supply interfaces and protected routing. Implement discharge/readiness measurements and settling. Validate current-limited power-up and unpowered gates with independent hardware cutoff. Do not implement a backend by replacing simulated values while retaining simulated readiness checks.

## v0.4 - Board-specific diagnosis and repair pilot

Characterize a known-good board, create limits with uncertainty, and seed representative faults on a designated bench unit. Add diagnostic firmware/functional checks, instrument/calibration provenance, and repeatable before/after repair evidence. Publish coverage and false-failure rates.

## v1.0 - Reproducible physical fixture

Publish verified schematics, controller firmware, switching/wiring diagrams, editable CAD, a validated BOM, instrument setup, electrical limits, and bench results. Add interchangeable board adapters only after the first family is validated. An optional OpenHTF integration can reuse the recipe/backend boundary later.

Suggested next milestone issues: choose a real PCB; map and verify 16 pads; validate pogo contact repeatability; design independent cutoff; define status/discharge feedback; implement a read-only controller status prototype. Dates and measured performance targets follow board/component evaluation.
