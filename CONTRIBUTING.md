# Contributing

Run `python -m unittest discover -s tests -v` and keep reproducible fixtures for behavior changes. Never turn an unavailable check into a pass or suppress a shutdown error to improve results.

New board support needs editable point maps, an explicit board revision, measured reference signatures, routing/protection information, and documented limits. Add hardware adapters only with real readiness/discharge feedback and independent fail-safe behavior.

Shared captures should be simulated or approved for publication. Remove private board identifiers and operational details. Keep simulated and measured provenance explicit. Update recipe versions and retain snapshots when limits or execution configuration change.
