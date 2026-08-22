# Open control-event benchmark

This directory contains a deterministic, no-network benchmark for the
PromptControlLab control protocol. It checks the existing analyzer's
classification contract against five small synthetic event sessions. No API
key or third-party package is required.

## Schema

`manifest.json` uses
`prompt_control_lab.control_benchmark_manifest.v1` and contains:

- `benchmark_id`: stable benchmark identifier.
- `description`: short benchmark purpose.
- `claim_boundary`: the shared interpretation limit.
- `cases`: ordered case records.

Each case declares `case_id`, a relative JSONL `fixture`, `expected_label`, a
brief `evidence_boundary`, and sparse `baseline_run` metadata. Each JSONL event
has exactly `sequence`, `event_type`, and `payload` fields. Fixtures contain
synthetic observable metadata only; they contain no raw instructions,
credentials, private reasoning traces, or commercial content.

## Run

From the repository root, install the checkout once and run the module:

```powershell
python -m pip install -e .
python -m promptcontrollab.control_benchmark examples/control-benchmark/manifest.json
```

API use:

```python
from pathlib import Path

from promptcontrollab.control_benchmark import run_benchmark

result = run_benchmark(Path("examples/control-benchmark/manifest.json"))
```

## Output

The result schema is `prompt_control_lab.control_benchmark_result.v1`. Each
case reports `observed`, `expected`, `pass`, its evidence boundary, the full
stability report, and an unscored attribution report. Aggregate fields are
`passed_cases`, `total_cases`, and `accuracy`.

The sparse comparison metadata intentionally makes attribution
`insufficient_evidence`. This preserves the analyzer's association-only
boundary; benchmark accuracy scores only the expected stability label.

## Limitations

The events are synthetic and selected to exercise documented thresholds. The
benchmark does not evaluate a real agent, prompt effectiveness, hidden model
state, causal effects, deployment behavior, or universal safety. Passing means
only that the current deterministic analyzer matches this fixture contract.
