# v0.2.0-alpha.1 public pre-release checklist

This checklist separates automated release evidence from actions that require the repository
owner's explicit approval. The repository must remain private and PR #3 must remain unmerged
until the owner completes the final inspection.

## Acceptance evidence

- [x] The controlled three-seed SFT pilot completed with 9 checkpoint runs and 6 paired gates.
- [x] The public-safe checkpoint case preserves the conservative `hold` decision and its claim
  boundary.
- [x] One bounded, real DeepSeek Harness lifecycle captured model requests, tool activity, a
  bounded edit, and a test process with exit code `0`.
- [x] The public-safe Harness case excludes raw prompts, raw model responses, credentials, private
  paths, and provider-request-ID claims that were not observed.

## Automated release verification

- [ ] Full Python tests pass on the final candidate commit.
- [ ] Ruff and strict mypy pass on the final candidate commit.
- [ ] DeepSeek Harness TypeScript contracts and build pass.
- [ ] Wheel and sdist build from the candidate source tree.
- [ ] A fresh environment can install the wheel and run `pcl --help`, `pcl doctor --json`, and
  `pcl quickstart`.
- [ ] README links, UTF-8 text, and release-version references pass the release checks.
- [ ] Tracked files and a fresh-clone Git history pass the scoped credential-shape scan.
- [ ] Release artifact checksums are generated after the final candidate build.

Local checks against an uncommitted tree do not complete this section. Record these items only
after the exact candidate commit exists and its CI and release artifacts have been verified.

## Maintainer inspection and publication

- [ ] Review the complete PR #3 diff and public-safe case-study artifacts.
- [ ] Rotate the credential that was used for the live DeepSeek acceptance session.
- [ ] Confirm the repository description, topics, and public claims.
- [ ] Mark PR #3 ready, merge it into `main`, and confirm CI on the merge commit.
- [ ] In one owner-controlled maintenance window, change visibility to Public, immediately enable
  GitHub Private Vulnerability Reporting, and verify that **Report a vulnerability** is available.
  If enablement or verification fails, return the repository to Private before any announcement,
  tag, or release.
- [ ] Create signed or annotated tag `v0.2.0-alpha.1`.
- [ ] Create a GitHub Pre-release and attach wheel, sdist, checksums, and release notes.
- [ ] Upload the same verified artifacts to PyPI only if trusted publishing or a valid release
  credential is configured; otherwise keep the release GitHub-only.

## Allowed public wording

The candidate may be described as a local-first evidence, diagnosis, and control loop for prompts,
checkpoints, and AI agents. The two real cases demonstrate that the bounded workflows executed and
produced auditable artifacts. They do not establish universal model improvement, production safety,
strict causal mechanisms, or hidden model-weight identity.
