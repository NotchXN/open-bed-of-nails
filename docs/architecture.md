# Architecture

The test runner is independent of any maintenance-management application. The only executable backend shipped in v0.1 is an in-memory simulator.

```mermaid
flowchart LR
    R[Versioned JSON recipe] --> V[Validate and snapshot]
    V --> P[Identity and fixture preflight]
    P --> U[Unpowered gates]
    U --> S[Current-limited power request]
    S --> M[Rail and functional checks]
    M --> T[Teardown and shutdown confirmation]
    T --> E[Run JSON / CSV / offline HTML]
    E --> C[Same-board retest comparison]
```

| Module | Responsibility |
| --- | --- |
| `recipe.py` | Strict JSON parsing, recipe validation, canonical SHA256 |
| `backend.py` | Deterministic simulator, measurement values, action trace |
| `runner.py` | Preflight, gates, dependencies, test evaluation, cleanup |
| `records.py` | Run consistency checks, CSV exports, retest comparisons |
| `report.py` / `report.html` | Escaped self-contained report and local controls |
| `__main__.py` | CLI and artifact workflows |

The runner copies the validated recipe before running so later edits cannot change its snapshot. The digest identifies exact recipe content, including limits and configuration, rather than relying only on a version label.

The backend interface comprises `power_off`, `check_ready`, `power_on`, `clear_stimulus`, `apply_stimulus`, `settle`, `measure`, and `close`, plus provenance and actions. A future real adapter must implement measured shutdown confirmation, instrument errors/timeouts, contact validation, routing protection, and independent hardware cutoff behavior. It must not inherit a simulated readiness check as a real safety check.

During teardown the runner independently attempts stimulus clearing, power-off, and transport closure. Failure of one operation does not suppress subsequent cleanup attempts. Unconfirmed output-off or any cleanup error changes the run to `ERROR`. An uncaught process termination or external power/control loss still requires hardware fail-safe behavior.

The simulator logs settling requests without waiting or claiming a real instrument has settled. Nominal/fault values are fixed fixtures, not a circuit model. GPIO output values depend on the simulated input stimulus; unsupported test paths remain untested.

Run loading verifies recipe hashes, measurement-versus-limit statuses, test-list completeness, timestamps, and overall status consistency. These checks detect accidental inconsistencies. JSON files and recipe hashes are not digital signatures and do not authenticate hardware provenance or operator identity.

The HTML report escapes script delimiters in embedded JSON and uses `textContent` for record text. CSV text fields are neutralized when they could be interpreted as spreadsheet formulas. Reports can be generated entirely offline.
