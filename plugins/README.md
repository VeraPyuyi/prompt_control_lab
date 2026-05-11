# prompt_control_lab plugin adapters

This directory contains thin adapters that let IDE and CLI agents use `pcl guard` before a
prompt reaches the model.

Current status:

- `claude-code/`: working `UserPromptSubmit` hook prototype.
- `cursor/`: integration notes for rules and command-based workflows.
- `codex/`: integration notes for skills and CLI wrappers.

The stable core is the CLI:

```bash
pcl guard --prompt "Fix this bug" --profile coding --token-mode balanced --json
```

For hook or wrapper integrations, prefer stdin:

```bash
echo "Fix this bug" | pcl guard --stdin --profile coding --json
```
