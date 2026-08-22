# GitHub Discussion Draft

**Title:** Request for maintainer feedback: PromptControlLab local control plugin for DeepSeek Harness

We would value maintainer feedback on a community-maintained PromptControlLab integration for DeepSeek Harness. The current implementation is a native Cordis plugin that maps Harness lifecycle events into PromptControlLab's versioned local event protocol.

## Scope proposed for review

- Compatibility is deliberately locked to Harness `0.1.1-rc.2` at commit `b150a551b8d465e31e418e1b2eaf5e79bbb7d28e` while the event surface is reviewed.
- `agent/session-start`, `agent/pre-step`, request events, tool events, turn-end signals, session events, and disposal are mapped to explicit PromptControlLab bridge methods.
- Suggest mode fails open with a bounded warning; gate mode fails closed when a decision cannot be obtained.
- Raw prompts are transport-only by default. Stored tool data is reduced to argument hashes/keys and result status/counts; assistant content, hidden reasoning, and API keys are not persisted.
- Feedback is bounded to 600 characters and a 256-item queue. Automatic recovery is off by default and, when enabled, is limited to one attempt.
- Harness's built-in repeat-tool reminder and timeout behavior remain authoritative. The plugin records those events and collaborates with the existing guards instead of replacing them.

## Questions for maintainers

1. Are the selected lifecycle events and their ordering appropriate for a Cordis plugin?
2. Which event payload fields should be treated as stable public contracts, and which should remain compatibility-locked?
3. Is the separation between suggest and gate failure behavior consistent with Harness operator expectations?
4. Are there additional privacy or bounded-feedback constraints maintainers would recommend?
5. What compatibility tests would be most useful before considering any wider community documentation?

Reference material: [pinned Harness source](https://github.com/deepseek-ai/deepseek-harness/tree/b150a551b8d465e31e418e1b2eaf5e79bbb7d28e), [architecture](https://github.com/deepseek-ai/deepseek-harness/blob/b150a551b8d465e31e418e1b2eaf5e79bbb7d28e/docs/architecture.md), and [event reference](https://github.com/deepseek-ai/deepseek-harness/blob/b150a551b8d465e31e418e1b2eaf5e79bbb7d28e/docs/user/develop/framework/events.md).

This request for maintainer feedback does not imply official inclusion. There is no promise of adoption, endorsement, distribution, or inclusion in Harness. Any next step would depend on maintainer review and an explicit decision in the Harness project.
