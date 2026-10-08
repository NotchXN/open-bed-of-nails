# Physical bench verification plan

These checks are future work, not completed results.

## Fixture readiness

Select one board family/revision and publish its pad coordinates, orientation, instrument routing, and test firmware state. Verify alignment, contact force, accessible pad condition, and repeatability across removal/reinsertion. Distinguish poor pogo contact from an actual open circuit.

## Electrical state and protection

Verify output-disabled boot/reset, independent interlock cutoff, watchdog timeout, disconnect behavior, current limiting, and fault shutdown. Confirm terminal voltage and discharge before resistance tests, including an externally powered DUT case. Test switching order and transient behavior against the board's protection envelope.

## Measurement validation

Compare fixture measurements with reference instruments and characterize lead/contact resistance, switch leakage, uncertainty, and settling. Use a known-good board to establish expected signatures, then intentionally seed supported opens, shorts, missing rails, and logic/communication faults on a designated bench board.

Publish detection coverage and false failures for this recipe. Repeat testing with the board removed/reinserted to quantify fixture repeatability. Do not claim full component isolation from a limited set of in-circuit readings.

## Repair evidence

Retain a before run and a separate retest for the same board serial, fixture, and recipe content. Review every failed and untested check. Store instrument/calibration references with real acquisition evidence in a future format revision. A recipe hash preserves configuration identity; it is not an authenticated instrument record.

## Report and CAD verification

Check the offline report in target browsers, including run selection, filters, record inspection, export, and print layout. Render the OpenSCAD concept and validate receiver holes, supports, mirroring, and board fit against actual component drawings before creating a real plate.
