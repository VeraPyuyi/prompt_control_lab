---
name: prompt_control_lab
description: Guard and improve prompts before expensive Codex, IDE, or CLI agent work. Use when a prompt is vague, broad, risky, costly, or should be optimized before implementation.
---

# prompt_control_lab

Use this skill before turning a broad or expensive user request into a larger Codex task.

## What To Do

1. If the user provides a prompt to guard, run:

```bash
pcl guard --prompt "<user prompt>" --profile coding --token-mode balanced --json
```

2. If the prompt is from stdin or a wrapper, use:

```bash
echo "<user prompt>" | pcl guard --stdin --profile coding --json
```

3. Read the JSON:

- `action=suggest`: show or use the `improved_prompt`.
- `action=auto`: use the `improved_prompt` directly if the user allowed automatic guarding.
- `action=block`: stop and ask the user to revise the prompt using the returned `reasons`.

4. Mention estimated token cost if it matters for the task.

## Profiles

- Use `--profile coding` for code edits, tests, reviews, and refactors.
- Use `--profile research` for papers, experiments, benchmarks, and analysis.
- Use `--profile general` for ordinary prompt cleanup.

## Token Controls

- Default: `--token-mode balanced`
- Shorter prompt: `--token-mode aggressive`
- Budgeted prompt: `--max-tokens 120`

The token count is an offline estimate, not a model-specific tokenizer guarantee.
