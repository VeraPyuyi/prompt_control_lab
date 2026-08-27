# Core

## Purpose

`promptcontrollab.core` contains shared infrastructure used by every feature domain: configuration, JSON and JSONL I/O, common schemas, errors, optional-dependency checks, and version data. It remains independent of product-level modules.

## Use cases

- Load project defaults from `.promptcontrol.yaml`.
- Read and write deterministic local artifacts.
- Share typed task, prediction, and metric records.
- Report missing optional dependencies without importing product domains.

## CLI commands

Core has no standalone CLI command. User-facing commands consume these helpers through their owning domain.

## Python API

The approved canonical package exports infrastructure such as:

```python
from promptcontrollab.core import (
    PromptControlLabError,
    TaskRecord,
    load_project_config,
    read_json,
    stable_digest,
    write_json,
)
```

Implementation modules include `config`, `files`, `schemas`, `errors`, `optional`, and `version`.

## Inputs/Artifacts

- Inputs: `.promptcontrol.yaml`, JSON, JSONL, paths, and environment state.
- Outputs: normalized configuration values, typed records, JSON/JSONL files, and stable digests.
- Core helpers do not define domain-specific run artifacts.

## Dependencies

Core uses the Python standard library and the package's default dependency-free runtime. It must not import preflight, evaluation, control, audit, evidence, diagnostics, provenance, or integrations.

## Extension points

- Add backward-compatible configuration accessors.
- Add shared schemas only when two or more domains use the same contract.
- Register optional features through explicit dependency checks and actionable install messages.

## Limitations

- The YAML reader intentionally supports a small dependency-free subset, not the full YAML specification.
- Stable digests identify serialized content; they are not signatures or authenticity proofs.

## Tests/Examples

See configuration, file, schema, and error coverage under `tests/`. Run:

```bash
python -m pytest tests -k "config or files or schema or errors"
```
