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
- `replay_entry` (offline bundle path or replay command)
- `limitations`

## Rules

- Do not claim a win over another tool without paired, versioned evidence.
- Preserve external scores separately from derived scores.
- Record exclusions and missing data explicitly.
- Existing 60-run Codex evidence remains historical only; it cannot be upgraded to a production conclusion.
- Any new paid model run is external pending and must not be fabricated.
