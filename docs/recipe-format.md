# Recipe format v1

The canonical demo recipe is `bed_of_nails/demo-controller-rev-a.json`. All limits and geometry in that recipe are synthetic. A real board needs its own schematic-derived and experimentally validated specification.

Required identity fields: integer `schema_version=1`, text `id`, `version`, `board_model`, `board_revision`, and `description`.

`power` contains `voltage_v` and `current_limit_ma`. The software accepts values in `(0, 24] V` and `(0, 500] mA`; these validation caps are not a physical fixture rating.

`test_points` defines unique point IDs, net labels, and nonnegative `x_mm`, `y_mm` coordinates. Coordinates describe one documented board view. A future fixture must define PCB orientation, mirroring, datum, tolerances, and pogo receiver positions explicitly.

Every test has:

| Field | Meaning |
| --- | --- |
| `id`, `label` | Unique stable check ID and operator-readable label |
| `phase` | `unpowered`, `powered`, or `functional`, in that order |
| `method` | `resistance`, `current`, `voltage`, or `uart_echo` |
| `points` | Two distinct defined points |
| `unit` | `ohm`, `mA`, `V`, or `bool`, matching the method |
| `min`, `max` | Inclusive finite limits |
| `on_fail` | `stop` or `continue`; unpowered gates must stop |
| `depends_on` | Optional earlier test IDs that must all pass |
| `settle_ms` | Optional integer 0-10000; default 0; simulation records the request only |
| `stimulus` | Optional functional GPIO input with defined point and integer level 0/1 |

Resistance tests can occur only in the unpowered phase. At least one unpowered gate is required; the actual set of safe gates depends on the board and hardware adapter. Current-test upper limits cannot exceed the configured supply limit. UART echo returns numeric 1 for success, 0 for failure; v0.1 does not implement a real UART transaction.

A sample functional check:

```json
{
  "id": "gpio_high",
  "label": "Logic buffer high output",
  "phase": "functional",
  "method": "voltage",
  "points": ["TP07", "TP02"],
  "unit": "V",
  "min": 2.8,
  "max": 3.5,
  "on_fail": "continue",
  "depends_on": ["rail_3v3"],
  "settle_ms": 50,
  "stimulus": {"kind": "gpio", "point": "TP10", "level": 1}
}
```

A failed or unavailable prerequisite marks its dependent check `UNTESTED`. The runner does not improvise a measurement or stimulus to bypass it. Unknown test execution fields and extra power/stimulus keys are rejected rather than silently ignored. Optional test `metadata` has no execution effect; it must be a flat object of at most 32 entries whose values are text (at most 1000 characters), finite numbers, booleans or null, so that it stays printable and hash-stable. New required execution behavior needs a format/runner change.

Strict JSON parsing rejects duplicate keys and non-finite numbers. Recipe hashes are SHA256 over sorted-key, compact canonical JSON. Run records embed the full snapshot, hash, recipe identity, board serial/model/revision, fixture ID, operator, timestamps, status, test rows, diagnostics, action trace, and shutdown result.

Comparisons require matching board identity (including serial), fixture ID, provenance, and exact recipe hash. They reject an earlier retest or comparing a run to itself. `PASS_ON_RETEST` means the later run passed this recipe; it does not prove a particular repair caused the improvement or that all board functions are healthy.
