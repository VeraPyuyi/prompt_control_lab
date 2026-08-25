## Summary

- What user-visible problem does this change solve?
- What is intentionally outside this pull request?

## Changed contracts and artifacts

- CLI/API/schema changes:
- Generated or migrated artifacts:
- Backward-compatibility notes:

## Verification

- [ ] `python -m pytest`
- [ ] `python -m ruff check .`
- [ ] `python -m mypy src tests`
- [ ] `npm run check` in `plugins/deepseek-harness` when relevant
- [ ] Fresh wheel install and sdist member inspection when packaging or template data changed

Paste concise results or link the corresponding CI run.

## Evidence and claim boundary

- What was observed?
- What can it explain?
- What can it not prove?
- What should a reviewer do next?

## Privacy and safety

- [ ] No API key, private prompt, hidden reasoning, private dataset record, model weight, or machine-specific private path is included.
- [ ] Security vulnerabilities are being handled through GitHub Private Vulnerability Reporting rather than this pull request.
- [ ] Guard, audit, attribution, or stability signals are not presented as safety or strict causal proofs.

## Documentation

- [ ] English and Chinese user documentation are synchronized when the user-facing workflow changed.
- [ ] Screenshots are attached for visible UI changes.
