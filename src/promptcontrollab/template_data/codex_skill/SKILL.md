---
name: prompt_control_lab
description: Guard and improve prompts before expensive Codex, IDE, or CLI agent work. Use when a prompt is vague, broad, risky, costly, or should be optimized before implementation.
---

# prompt_control_lab

Use this skill before turning a broad or expensive user request into a larger Codex task.

```bash
pcl guard --prompt "<user prompt>" --profile coding --policy examples/guard.policy.yaml --token-mode balanced --json
```

If the prompt arrives through a wrapper:

```bash
echo "<user prompt>" | pcl guard --stdin --profile coding --policy examples/guard.policy.yaml --json
```

If `action=block`, stop and ask for a safer, narrower prompt. If `required_review=true`,
ask for human confirmation before running risky code edits.
