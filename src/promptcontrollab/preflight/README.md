# Preflight

## Purpose

`promptcontrollab.preflight` checks and improves a prompt before an AI agent or model spends tokens or changes files. It combines heuristic risk detection, team policy rules, prompt rewriting, token budgeting, scaffold checks, and workflow selection.

## Use cases

- Detect vague, destructive, security-sensitive, or overly broad instructions.
- Apply a team-owned guard policy before agent execution.
- Produce a clearer prompt with bounded output and verification requirements.
- Estimate prompt tokens and recommend the appropriate PromptControlLab workflow.

## CLI commands

```bash
pcl guard --prompt "Fix this bug" --profile coding --policy examples/guard.policy.yaml
pcl improve --prompt "Answer the question" --token-mode balanced
pcl start --choice guard --prompt "Fix this bug"
pcl choose --need "Check an agent prompt before execution"
pcl scaffold-check --scaffold runs/scaffold
```

## Python API

The approved canonical package exposes the primary preflight entry points:

```python
from promptcontrollab.preflight import (
    choose_tool_for_need,
    guard_prompt,
    improve_prompt,
    load_guard_policy,
)
```

Supporting types include `PromptGuardResult`, `PromptImprovement`, `PromptContext`, `GuardPolicy`, and `GuardViolation`.

## Inputs/Artifacts

- Inputs: prompt text or file, profile, mode, policy file, token mode, optional run context, and language.
- Outputs: `guard_result.json`, `improved_prompt.txt`, `prompt_improvement.json`, `prompt_diff.md`, and scaffold-check reports when requested.
- JSON output retains stable fields for CLI, hook, MCP, and skill consumers.

## Dependencies

The default preflight path is local and dependency-free. It depends on `core` for configuration and files and may read existing run artifacts as bounded context.

## Extension points

- Add guard profiles and policy rules without changing the stable result schema.
- Add language-aware guidance and risk categories.
- Add tool-choice lanes or prompt context extractors with deterministic outputs.

## Limitations

- Guard decisions are heuristic governance signals, not proof that an agent action is safe.
- Token counts are estimates and may differ from provider billing tokenizers.
- Offline rewriting does not run a model or guarantee that the revised prompt performs better.

## Tests/Examples

Examples live in `examples/guard.policy.yaml`, plugin documentation, and preflight tests. Run:

```bash
python -m pytest tests -k "guard or improve or policy or scaffold or tool_choice"
```
