# prompt_control_lab for Cursor

Cursor integration is currently a lightweight rules and command pattern.

Recommended use:

1. Keep prompt guidance in `.cursor/rules`.
2. Use `pcl guard` before sending expensive or ambiguous prompts.
3. For team workflows, wrap agent prompts with:

```bash
echo "Refactor this module" | pcl guard --stdin --profile coding --token-mode balanced --json
```

Suggested `.cursor/rules` snippet:

```text
Before acting on vague, broad, or expensive prompts, ask the user to run:
pcl guard --prompt "<their prompt>" --profile coding

Prefer prompts that define scope, target files, expected output, tests, and verification.
```

This adapter does not claim full prompt interception in Cursor. It provides a practical workflow
until a deeper extension or MCP adapter is added.
