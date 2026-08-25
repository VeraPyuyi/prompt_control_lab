# Security Policy

## Reporting a vulnerability

Do not report a vulnerability in a public issue, discussion, pull request, or social-media post.

PromptControlLab accepts vulnerability reports only through
**GitHub Private Vulnerability Reporting**:

1. Open the repository's [**Security advisories**](https://github.com/VeraPyuyi/prompt_control_lab/security/advisories) page.
2. Select **Advisories**.
3. Select **Report a vulnerability**.
4. Include affected versions, reproduction steps, impact, and a minimal proof of concept.

Private Vulnerability Reporting is enabled for this public repository.
No security-reporting email address is used by this project.

Please do not include a real API key, private prompt, private dataset record, hidden reasoning,
or unrelated personal data. Use redacted placeholders and the smallest artifact needed to
reproduce the issue.

## Scope

Security-relevant reports include, but are not limited to:

- credential or private-prompt persistence;
- policy-gate bypasses that contradict the documented mode;
- unsafe path handling or unintended file overwrite;
- webhook-signature or GitHub App authentication failures;
- command execution outside an explicitly authorized boundary;
- malicious artifact deserialization; and
- sensitive information exposed through reports, logs, plugins, or templates.

PromptControlLab guard, audit, attribution, and stability outputs are heuristic governance and
diagnostic signals. They reduce obvious risk but do not prove that an agent action, model, or
checkpoint is safe.

## Supported versions

Security fixes target the latest published pre-release and the active `main` branch. Older alpha
snapshots may be asked to reproduce the issue on the latest version before a fix is prepared.
