# Public benchmark protocol

This protocol documents how to compare PromptControlLab against external benchmark exports without claiming production superiority.

## Required fields

- `protocol_version`
- `benchmark_name`
- `provider`
- `model`
- `prompt_version`
- `dataset_version`
- `metric_id` and `metric_version`
- `score_mode` (`preserve` or `recompute`)
- `negative_results_allowed`
- `replay_entry` (local bundle path, relative to the declaration file; commands and URLs are never executed)
- `limitations`

## Rules

- Do not claim a win over another tool without paired, versioned evidence.
- Preserve external scores separately from derived scores.
- Record exclusions and missing data explicitly.
- Existing 60-run Codex evidence remains historical only; it cannot be upgraded to a production conclusion.
- Any new paid model run is external pending and must not be fabricated.

## Callable validation and reproducible evidence

The dependency-free implementation is `promptcontrollab.evaluation.experiments.protocol.validate_protocol`. Its fixed v1 schema requires exactly the fields above: nonempty text identities, `protocol_version="1"`, `negative_results_allowed=true`, and a nonempty array of text limitations. Unknown fields, unsupported versions, invalid types, commands, and URLs are rejected. Schema validation checks the declaration; replay additionally checks its selected metric ID/version and score mode against the saved experiment. Provider/model/prompt/dataset labels remain declarations, not authenticated provenance.

The concrete source evidence is [synthetic-import.json](../examples/experiments/synthetic-import.json); its declaration is [public-benchmark-protocol.json](../examples/experiments/public-benchmark-protocol.json). From an installed checkout, generate and replay these predetermined outputs with **zero model calls**:

```sh
python scripts/replay_public_benchmark_example.py --out benchmark-example
python -m promptcontrollab experiment protocol --input benchmark-example/protocol.json
python -m promptcontrollab experiment protocol --input benchmark-example/protocol.json --out benchmark-replay
```

The first command creates `benchmark-example/experiment.zip`, the declaration, and `benchmark-example/replay/report.json`. The last command independently replays that bundle, writing `report.json`, `assessment.original.json`, `assessment.recomputed.json`, `comparison.json`, records, and standalone bilingual HTML. A successful run reports passed protocol, byte integrity, and numerical replay; unsuccessful integrity or numerical replay exits nonzero. This fixture is not evidence of superiority over any tool. Existing historical bytes and receipt hashes remain unchanged.

## Failure datasets and cost evidence

A downloaded `experiment-failure-dataset/v1` JSON can be uploaded as a JSON dataset, or referenced by a new experiment config's `data` path. Reimport retains IDs, inputs, reviewed answers, metadata, dataset version, source experiment/hash and full record lineage in `meta.failure_lineage`. This creates a new immutable experiment. It never appends to or resumes the source experiment's withheld/train partitions. Previously inspected examples cannot support a fresh untouched-generalization claim about the source experiment.

Costs distinguish `reserved_cost` (admission bound), `estimated_cost` (reported tokens times a frozen tariff), `reported_cost` (explicit provider/import receipt), and `actual_cost` (explicit actual amount only). `price_snapshot` and `price_source` describe the tariff; each cost kind retains its currency. `known_cost` is a compatibility projection with an explicit `cost_basis`, not an actual invoice. Totals with multiple currencies remain null and `cost_by_currency` retains separate totals. No implicit FX conversion occurs. Legacy unspecified global-rate units are labeled `legacy`; report actual billing amounts only with a declared currency.
