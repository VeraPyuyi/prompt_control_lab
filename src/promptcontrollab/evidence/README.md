# Evidence

## Purpose

`promptcontrollab.evidence` imports, reconciles, and interprets external experiment evidence. It connects evaluation, prompt-reach adapters, post-training checkpoints, and bounded research artifacts to auditable source manifests and decision gates.

## Use cases

- Scan a read-only experiment tree and build a deterministic source manifest.
- Import Promptfoo, Langfuse, LangSmith, DeepEval, Prompt Optimizer, PEOC, or server evidence.
- Reconcile local and remote evidence without copying private or large source assets.
- Compare SFT/DPO/PPO/GRPO-related checkpoints with capability-aware evidence gates.

## CLI commands

```bash
pcl evidence scan --root /path/to/evidence --profile prompt-reach-v2 --out manifest.json
pcl evidence import --manifest manifest.json --out runs/evidence --portable
pcl evidence merge --primary local.json --secondary server.json --out runs/merged
pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate
pcl research-import peoc --bundle /path/to/read-only-bundle --out runs/peoc
pcl posttrain-gate --baseline runs/checkpoint-000 --candidate runs/checkpoint-500 --policy examples/posttrain.policy.yaml --out runs/posttrain-gate
```

## Python API

The approved canonical package exposes source ingestion and post-training entry points:

```python
from promptcontrollab.evidence import (
    EvidenceImportOptions,
    import_evidence_manifest,
    run_posttrain_gate,
    scan_evidence_root,
)
```

Adapters cover prompt reachability, readout alignment, routing, projection, and prompt stability. Evidence cards, gates, pilot plans, and PEOC import options support specialized pipelines.

## Inputs/Artifacts

- Inputs: read-only roots, source manifests, external tool exports, checkpoint run directories, policies, and adapter-specific JSON/CSV summaries.
- Outputs: `server_evidence_manifest.json`, `source_manifest.json`, `evidence_matrix.json`, `source_gap_report.json`, `interpretability_report.json/html`, `claim_check.json`, and post-training gate artifacts.
- Portable imports copy only approved derived files; large models, private prompts, and raw datasets remain outside the bundle.

## Dependencies

Scanning and most imports use the default runtime plus `core`, `provenance`, and `evaluation`. Controlled post-training execution requires the `posttrain` extra; scientific evidence adapters may require `research`.

## Extension points

- Register evidence profiles and adapters with deterministic discovery and normalized output.
- Add external-tool importers that preserve source provenance and claim boundaries.
- Add capability-aware gate checks that distinguish missing, not applicable, and failed evidence.

## Limitations

- Imported historical evidence can explain recorded associations but cannot create missing experimental controls.
- `mixed`, `inconclusive`, and `requires_reanalysis` are not confirmed improvements.
- Post-training diagnostics assist checkpoint selection; they do not replace training or prove causal mechanisms.

## Tests/Examples

See `docs/case_studies/`, evidence fixtures, and post-training tests. Run:

```bash
python -m pytest tests -k "evidence or ingest or peoc or posttrain"
```
