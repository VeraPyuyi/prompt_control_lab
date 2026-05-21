# prompt_control_lab for Claude Code

This prototype connects `prompt_control_lab` to Claude Code as a `UserPromptSubmit` hook.

What it does:

- reads the user prompt from Claude Code hook JSON on stdin
- runs the local `prompt_control_lab` guard
- returns `additionalContext` with a clearer, lower-cost prompt suggestion
- optionally returns `decision: block` when `--mode gate` detects high risk

## Install

From the repository root, copy the example hook config into your Claude Code settings and adjust
the script path if needed:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python \"D:/path/to/prompt_control_lab/plugins/claude-code/hooks/prompt_guard.py\" --mode suggest --profile coding --token-mode balanced --max-tokens 300 --policy \"D:/path/to/prompt_control_lab/examples/guard.policy.yaml\""
          }
        ]
      }
    ]
  }
}
```

## Modes

- `--mode suggest`: add a prompt suggestion as extra context.
- `--mode auto`: mark the guarded prompt as auto-usable in the guard result.
- `--mode gate`: block prompts that exceed the configured estimated token budget or look high risk.
- `--policy path/to/guard.policy.yaml`: apply the same team guard policy used by `pcl guard`.

Policy files use a dependency-free parser. The bundled example uses flat keys, and the hook also
accepts the small nested `rules:` style supported by the CLI.

## Notes

The token count is an offline estimate. It does not use a model-specific tokenizer. The hook is
designed as a thin adapter; core behavior lives in the Python package and `pcl guard`.
