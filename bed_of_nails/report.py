"""Self-contained offline run/comparison report."""

import json
from pathlib import Path

from .records import compare_runs, validate_run


def render_report(runs, path, *, comparison=False):
    if not runs:
        raise ValueError("Report requires at least one run")
    for run in runs:
        validate_run(run)
    data = {"runs": runs, "comparison": compare_runs(*runs) if comparison else None}
    encoded = json.dumps(data, allow_nan=False).replace("<", "\\u003c")
    encoded = encoded.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    template = Path(__file__).with_name("report.html").read_text(encoding="utf-8")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(template.replace("/*RUN_DATA*/null", encoded), encoding="utf-8")
    return target
