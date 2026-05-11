# prompt_control_lab for Codex

Codex integration is currently a skill and wrapper pattern.

Bundled local skill:

```text
plugins/codex/skills/prompt_control_lab/SKILL.md
```

Install on Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\skills\prompt_control_lab"
Copy-Item -Recurse -Force .\plugins\codex\skills\prompt_control_lab\* "$env:USERPROFILE\.codex\skills\prompt_control_lab\"
```

Restart Codex after copying the skill.

Recommended use:

```bash
pcl guard --prompt "Implement the feature" --profile coding --token-mode balanced
```

Wrapper pattern:

```bash
echo "Implement the feature" | pcl guard --stdin --profile coding --json
```

For a Codex skill, use `pcl guard` as the first step before passing a user prompt into a longer
workflow. The guard result gives:

- improved prompt
- estimated token cost
- risk level
- reasons
- suggested action

This keeps the core logic in `prompt_control_lab` and avoids duplicating prompt rules across
multiple agent environments.
