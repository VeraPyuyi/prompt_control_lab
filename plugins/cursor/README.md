# prompt_control_lab for Cursor

Cursor integration has two layers:

- a lightweight rules and command pattern
- a dependency-free MCP-style stdio server that exposes `guard_prompt`

This adapter still does not claim full automatic prompt interception. It gives Cursor a callable
guard tool and a practical rule workflow.

Bundled rule file:

```text
plugins/cursor/rules/prompt_control_lab.mdc
```

Install inside a Cursor project:

```powershell
New-Item -ItemType Directory -Force .cursor\rules
Copy-Item plugins\cursor\rules\prompt_control_lab.mdc .cursor\rules\prompt_control_lab.mdc
```

Recommended use:

1. Keep prompt guidance in `.cursor/rules`.
2. Use `pcl guard` before sending expensive or ambiguous prompts.
3. Show `plain_summary` from JSON output when building custom wrappers.
4. For team workflows, wrap agent prompts with:

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

## Path Toward Automatic Guarding

A deeper Cursor integration should be implemented as one of these:

- a Cursor extension that calls `pcl guard --json` before prompt submission
- an MCP server that exposes `guard_prompt` as a callable tool
- a local wrapper command that reads a prompt, shows `plain_summary`, and copies or forwards the
  guarded prompt

The stable integration contract is the `pcl guard --json` payload, especially
`plain_summary`, `action`, `risk_level`, `improved_prompt`, and `token_report`.

## Optional MCP-Style Server

Run the local server:

```bash
python plugins/cursor/mcp_server.py
```

If your Cursor setup supports local MCP servers, point the server command to that script. The
server exposes one tool:

```text
guard_prompt
```

Example tool arguments:

```json
{
  "prompt": "Refactor this module",
  "profile": "coding",
  "token_mode": "balanced",
  "mode": "suggest"
}
```

The tool returns a JSON text payload with `plain_summary`, `risk_level`, `improved_prompt`,
`reasons`, and `token_report`, so a Cursor wrapper can show a human-readable suggestion before
the agent spends tokens.
