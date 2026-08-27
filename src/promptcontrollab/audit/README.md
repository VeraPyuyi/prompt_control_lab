# Audit

## Purpose

`promptcontrollab.audit` explains what an AI coding run changed after execution. It summarizes Git diffs, tests, sensitive paths, dependencies, workflows, secret-like additions, agent manifests, PR review coverage, and claim boundaries.

## Use cases

- Review changed files and line counts between two Git revisions.
- Detect unexpected paths, public API changes, deleted tests, or security-sensitive edits.
- Build one `agent_run.json` that links prompt, policy, model, gate, diff, and tests.
- Produce a PR summary, GitHub check signal, Markdown review, or SARIF report.

## CLI commands

```bash
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit --sarif runs/audit/pcl.sarif
pcl agent-run build --run runs/quick --audit runs/audit --agent codex --out runs/agent_run.json
pcl pr-summary --audit runs/audit/audit_result.json --gate runs/quick/gate_result.json --out pr_summary.md
pcl github-app serve --host 0.0.0.0 --port 8080
pcl claim-check --run runs/quick
```

## Python API

The approved canonical package exposes audit and review builders:

```python
from promptcontrollab.audit import (
    build_agent_run_manifest,
    build_pr_summary,
    run_audit_diff,
    run_claim_check,
)
```

GitHub integration uses `verify_webhook_signature`, `summarize_pull_files`, and `handle_pull_request_payload` through the integrations layer.

## Inputs/Artifacts

- Inputs: Git revisions, expected paths, test records, audit/gate artifacts, policy path, and pull-request file metadata.
- Outputs: `audit_result.json`, `audit_summary.md`, optional `pcl.sarif`, `agent_run.json`, `pr_summary.json`, `pr_summary.md`, and claim-check reports.
- Secret-like findings are redacted before persistence.

## Dependencies

Local diff auditing uses Git, the standard library, and `core`. External secret scanners are optional executables. The self-hosted GitHub App requires the `bot` extra.

## Extension points

- Add file classifiers and structured findings with stable rule IDs.
- Add optional external scanners while preserving the built-in fallback.
- Add PR renderers or annotations from the same structured summary model.

## Limitations

- Diff classification and public API detection are heuristic, not full semantic analysis.
- Built-in secret matching is not a substitute for a dedicated secret scanner.
- Missing test records mean tests were not observed, not necessarily that no tests ran.

## Tests/Examples

Tests create temporary Git repositories and fake GitHub clients. Run:

```bash
python -m pytest tests -k "audit_diff or agent_run or pr_summary or github_app or claim_check"
```
