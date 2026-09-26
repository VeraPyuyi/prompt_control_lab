# Offline research tools

All five JSON examples are explicitly **synthetic**, deterministic, portable, and
require no model download, provider key, GPU, or running research job. Run from
the repository root:

```console
python examples/research-tools/run_examples.py --out research-example-output
```

Each tool writes `report.json`, `metrics.csv`, `report.en.md`, `report.zh.md`, and
English/Chinese HTML reports. Reports include readable metric tables, separate
source/numerical/premise status cards, portable SVG figures and collapsed raw
JSON. The public Python entry point is
`analyze_research(kind: str, document: dict, out_dir: Path) -> dict` in
`promptcontrollab.diagnostics.research_tools`. Kinds are `readout`, `response`,
`measurement-value`, `transfer`, and `replay`.

- `readout.json`: saved per-sample paired outputs, parser rule/version/posthoc
  metadata, decoding metadata and token budgets. Parse success switches and
  correctness changes are separate targets. Per-condition AUCs retain ties and
  undefined values. `exact`, `boxed`, and `last_number` are explicit parser rules.
  A derived prefix additionally requires `prefix_tokens`, original `token_ids`,
  aligned `token_texts` that reconstruct the entire saved text, and `tokenizer_id`.
  Such a prefix is labeled a saved-token prefix, not a new shorter generation.
- `response.json`: supplied scalar losses and finite aligned control/response
  vectors. Optional orthonormal basis rows and response Jacobian enable subspace
  fraction and linear approximation residual. Zero denominators produce null.
  Readout definition, gold-label usage, calibration source and separation remain
  visible. The separation flag is declared metadata, not inferred evidence.
- `measurement-value.json`: exact decimal cost accounting, fixed label-free
  score queues, per-item paired-generation costs and full-prefix budget stopping.
  Optional `costs.transmission_seconds` is common upfront transfer time;
  `costs.transmission_pair_seconds` is an aligned array added to generation costs.
  Legacy v1 records omit these fields and retain their previous results.
  `locked_decision` also accepts transmission time in its incurred-cost ledger.
  Reports replay fixed queues at 21 fractions of each case's own budget and plot
  net discovery gain against direct evaluation; the full-budget endpoint equals
  the original accounting result. They also separate probe, selection, scan,
  sort, transmission and completed-generation costs. No budget curve refits
  scores or forecasts.
- `transfer.json`: externally frozen full/cheap/common-mean/zero forecasts.
  Shared item indices and connected endpoint components are resampled together
  across all six forecast comparisons. Simultaneous maximum-deviation intervals
  apply within each model. One connected component is explicitly conditional on
  that component. Undefined AUCs and unusable draws remain reported; no null is
  replaced by zero or 0.5. Optional `bootstrap` accepts integer `repetitions`
  (20–2000), integer `seed`, and `confidence` strictly between zero and one.
- `replay.json`: embedded JSON/text files, allowlisted checks and independent
  byte-integrity/numerical-tolerance/local-theory results. Embedded `json` hashes
  use sorted compact UTF-8 JSON; `text` hashes use exact UTF-8 bytes. No external
  paths, commands, recursive replay or pickle are accepted. Certificate kinds
  `posterior-certificate`, `green-certificate`, `terminal-sensitivity` reuse the
  repository's existing local certificate modules. Green checks accept inline
  numeric `arrays` containing `M`, `B0`, `BN`, optional `graph_S`, `horizons`, and
  `premises`. Terminal checks accept inline `records`. A passing local certificate
  is never promoted to an entire-LLM proof.
  SHA256 fields and exact recomputed-result byte hashes are reported separately
  from tolerance-based numerical/content comparisons.

The completed historical measurement-value case is available with
`--historical`. Its preserved 54 model/pair records cover the published 400-item
panels; source receipts and original licensing notes accompany that case. The
separate GSM8K transfer study remains pending and is not imported here. The old
`measurement_value` and `transfer_prediction` imports and case runners remain
available for compatibility.

## Evidence receipts

Evidence status remains explicitly declared. A 64-character hash is not proof
of a prospective lock. `independent_confirmation` requires actual embedded
`evidence_receipts` with these links:

1. `lock`: nonempty `payload`, its canonical `payload_sha256`, and zoned
   `frozen_at`. For transfer, the payload contains `forecasts_sha256`, hashing
   the ordered forecast-only pair records (model, pair_id, left_seed,
   right_seed, pairing_type, predictions). The top-level prediction lock hash
   must equal the canonical hash of this lock object.
2. `evaluation`: `lock_sha256`, zoned `started_at` after freezing, and
   `document_sha256`, hashing the input without `evidence_receipts`.
3. `cohorts`: nonempty disjoint `calibration_ids` and `evaluation_ids`, linked
   by `lock.payload.calibration_ids_sha256` and
   `evaluation.evaluation_ids_sha256` respectively.

For transfer, evaluation identities must equal the analyzed endpoint set using
`model:seed` strings. For measurement value they must equal its `model:pair`
coordinates; the lock additionally requires `policies_sha256` over the ordered
case records restricted to model, pair, item_ids, scores, and costs. These links
prevent unrelated but correctly hashed receipts from validating a different case.

Successful checks mean **locally consistent linked receipts**. Their dates and
real-world independence remain unauthenticated; reports keep
`temporal_independence_verified: false`. Historical inputs remain usable without
receipts, with that limitation visible.
