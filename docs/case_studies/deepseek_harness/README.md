# DeepSeek Harness Real-Session Case

This public-safe case records one bounded, real DeepSeek Harness coding session. It separates lifecycle facts, PromptControlLab diagnostics, and claim boundaries.

## What Was Observed

- The native Cordis plugin ran against Harness `0.1.1-rc.2` at commit `b150a551...` through one persistent local stdio bridge.
- Four matched model request/response pairs reported the public identity `deepseek-official/deepseek-v4-flash`.
- Four terminal tool results contained two file reads, one bounded file write, and one test execution.
- The disposable repository finished with 3/3 tests passing. Only `src/math_utils.py` changed, with one added and one deleted line.
- The test result recorded `is_error=false` and an explicit process exit code of `0`; machine acceptance requires both signals.
- Captured Harness usage metadata contained 13,401 input tokens and 619 output tokens. No cache-token or billing-cost claim is made.
- The captured response did not expose a provider-issued request ID. PromptControlLab local request identifiers are not presented as provider identifiers.

## What The Diagnostics Explain

An earlier run exposed a context-and-negation false positive in the heuristic guard. After the focused rule fix, the verified model-backed run produced `low` preflight risk and a `suggest` decision.

A later review found that `is_error=false` only proves the tool wrapper completed; it does not prove a shell test returned success. The redacted protocol now retains the integer `exitCode` while dropping stdout and stderr. Missing exit status remains `unknown`, nonzero is `fail`, and only zero is `pass`. A fresh live run recorded exit code `0` and directly classified as `converging`. The final control decision remains the conservative `suggest`.

## Credential Boundary

The credential was supplied ephemerally to the live process. A credential-shape scan found zero matches in three listed local scopes: the disposable task worktree, PromptControlLab control artifacts, and DeepSeek Harness session artifacts. This is a scoped observation, not a guarantee about unscanned external systems.

## Reproducible Public Artifacts

- [Derived evidence](live_session_evidence.json) contains the sanitized lifecycle, usage, diagnostic, and scan aggregates.
- [Status](live_session_status.json) references the evidence and records the integration checks.

This case proves that one real, bounded lifecycle was captured through preflight, model requests, tool reads, a file edit, and passing tests. It does not identify hidden model weights, prove semantic safety, establish strict causality, or generalize performance from one task.
