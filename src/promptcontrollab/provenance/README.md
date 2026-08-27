# Provenance

## Purpose

`promptcontrollab.provenance` records public prompt and model identity, compares identities across runs, and reports when a result is confounded by model drift or incomplete provenance.

## Use cases

- Extract a provider-declared model ID from an API response or prediction file.
- Record a prompt ID, version, file, and content digest in a run manifest.
- Detect provider/model changes between current and historical runs.
- Warn about aliases, unknown models, and comparisons that are not prompt-only.

## CLI commands

```bash
pcl model-detect --response response.json --provider openai
pcl model-detect --model gpt-4o --provider openai --verify
pcl model-drift --run runs/current --history runs/previous --out runs/current/model_drift.json
pcl validity --baseline runs/previous --candidate runs/current --out runs/current/comparison_validity.json
```

## Python API

The approved canonical package exposes identity builders and comparison functions:

```python
from promptcontrollab.provenance import (
    build_prompt_identity,
    compare_model_identities,
    detect_model_identity,
    run_model_drift,
)
```

`ModelIdentity` carries the provider, public model ID, source, confidence, verification metadata, warnings, and bounded provenance evidence.

## Inputs/Artifacts

- Inputs: response JSON, prediction JSONL, declared provider/model, prompt files, and run manifests.
- Outputs: model identity payloads, prompt identity blocks, provenance warnings, and `model_drift.json`.
- Prompt and response digests support comparison and integrity checks but do not replace authenticated receipts.

## Dependencies

Offline detection uses the standard library and `core`. Online verification is provider-specific, requires explicit credentials, and remains optional.

## Extension points

- Add provider-specific response extractors and metadata verification.
- Add new alias-risk rules while preserving dated model identifiers.
- Add stronger receipt or provider-log evidence without changing lower provenance levels.

## Limitations

- A response `model` field identifies the public model ID reported by the provider; it does not prove hidden weights or an internal build.
- An intercepted or modified response can falsify unauthenticated metadata.
- Behavioral probes may support an investigation but are not reliable model identity proofs.

## Tests/Examples

See model identity, drift, validity, and manifest tests. Run:

```bash
python -m pytest tests -k "model_identity or model_drift or prompt_identity or validity"
```
