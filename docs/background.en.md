# Background

PromptControlLab is an open-source local control loop for prompts and AI agents. It makes the path from intent to execution inspectable: review the request, choose an authorization boundary, record normalized events, explain the resulting decision, and preserve versioned artifacts for later review.

## Why a control loop

Prompt and agent runs often cross boundaries that a score alone cannot describe. A request may call a model, let an agent act in a project, expose sensitive text to a provider, or continue after evidence becomes weak. PromptControlLab turns those choices into explicit local steps:

1. **Before:** inspect intent, scope, provider or agent, redaction, and authorization.
2. **Run:** observe bounded, normalized events without silently expanding authority.
3. **Why:** attach reasons and event references to diagnoses and gates.
4. **After:** compare recorded outcomes with the requested objective.
5. **Decision:** preserve allow, suggest, gate, or insufficient-evidence results.
6. **History:** reopen the JSON artifacts; rebuild the optional SQLite index when needed.

The control loop can stop at inspection, call a selected model, or supervise an agent at a declared scope. It does not require a hosted service and does not infer permission from the presence of credentials.

## Evidence boundary

Versioned JSON and JSONL are the source of truth. Reports and the local UI are views over that evidence. A recorded decision is not a causal result or safety proof, and missing events remain missing evidence.

## Advanced diagnostics

Prompt evaluation, tri-split statistics, soft/hard projection, hidden-state trajectory, Riccati surrogate, time-varying soft control, and PEOC evidence import remain optional Advanced Diagnostics. They can deepen a supported investigation, but they are not prerequisites for the default local control path.
