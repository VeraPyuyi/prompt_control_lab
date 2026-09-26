# Measurement value under a fixed audit budget

[中文说明](README.zh.md)

This bounded [PromptControlLab](https://github.com/VeraPyuyi/prompt_control_lab)
research case connects control-theory questions, fixed soft-prompt cohort-transfer
scores, and measured audit costs. Its operational question is whether a diagnostic
queue discovers more behavioral changes after paying for measurement. It provides
an importable standard-library module and a research script; it adds no Cockpit flow.

The supplied [historical research record](source_records.json) covers
**54 pairs at native decode cap 8**.
Its cost test is **NO_GO**: the measured source mean for direct audit exceeds the
paid selector in all three models. This is a historical observation from the user’s
records. There is no fresh efficiency confirmation and no new 384-step training
result. The small fixture below is explicitly synthetic and does not supply those
empirical claims.

## Run the accounting case

From a source checkout, without installing PromptControlLab or optional dependencies:

```console
python -S scripts/run_measurement_value_case.py --input docs/case_studies/measurement_value/source_records.json --out measurement-value-output
```

The [checked English report](historical_replay/report.md),
[Chinese report](historical_replay/report.zh.md), and
[per-pair CSV](historical_replay/strategies.csv) come from this exact input.
For a four-item smoke example, replace the input with `synthetic_test.json` in the
same directory. See [record provenance and licensing](DATA.md).
The script creates deterministic `results.json`, `strategies.csv`, `report.md`, and
`report.zh.md`. It records the SHA256 of the exact input bytes. The reports aggregate
by model and strategy; the CSV retains each pair, while JSON also retains the full
queues, completed prefixes, and exact rational accounting terms. The script does
not call a model, launch training, or estimate unrecorded costs.

The API is `promptcontrollab.measurement_value.analyze_document(document)`.
`fixed_order(case, strategy)` reads only `item_ids` and the requested fixed score.
The source-checkout script loads `src` itself; ordinary Python callers can install
the package or add the checkout’s `src` directory to their import path.

## Input contract: `measurement-value/v1`

The top-level object contains:

| Field | Meaning |
|---|---|
| `schema_version` | Exactly `measurement-value/v1` |
| `evidence_status` | Explicitly `historical_observation`, `locked_prediction`, or `independent_confirmation` |
| `synthetic` | Required Boolean; synthetic records must use `true` |
| `provenance` | Optional public-safe source metadata, including timing and score definitions |
| `cases` | Nonempty array with unique `(model, pair)` coordinates |

Each case contains `model`, `pair`, unique nonempty string `item_ids`, aligned
`scores.loss`, `scores.primary`, `scores.norm` arrays, aligned binary 0/1
`behavior.risk_source` and `behavior.risk_target` arrays, and a `costs` object:

| Cost field | Unit and scope |
|---|---|
| `generation_pair_seconds` | Aligned array; complete source-plus-target behavioral audit per item |
| `budget_seconds` | B, the total wall-clock budget for this model/pair |
| `direct_sort_seconds` | Fixed direct queue construction cost |
| `scan_seconds` | Exactly `loss`, `primary`, `norm`; full-pool fixed score scan costs |
| `sort_seconds` | Exactly `loss`, `primary`, `norm`; queue sorting costs |
| `probe_seconds`, `selection_seconds` | Optional pair of fields; additional diagnostic measurement and selection costs |

Every cost must be a finite, nonnegative JSON number. Booleans and numeric strings
are rejected. Aggregate time totals must also be representable as finite output
numbers; overflowing totals produce a validation error and are never clipped.
Scores must be finite numbers and can be signed. Costs must use the same timing
basis. If a measured `selector_overhead_seconds` already includes probe
and CPU selection time, it may be supplied as `probe_seconds` with
`selection_seconds=0`, with that aggregation recorded in provenance. Do not add the
same measured interval twice. Both optional paid fields must be present together;
if absent, paid rows are omitted and `paid_cost_status` is `not_supplied`.

## Predetermined queues and the budget identity

`direct` sorts by SHA256 of UTF-8 `item_id`, ascending. `loss`, `primary`, and `norm`
sort their supplied scores descending, then by the same SHA256 tie break. An item-ID
fallback makes even a hash collision deterministic. Labels and costs never reorder
these queues. Input array positions carry alignment, not audit priority.

The base strategies pay direct sorting or the selected score’s scan plus sorting.
Their `paid_direct`, `paid_loss`, `paid_primary`, and `paid_norm` versions also pay
the supplied probe plus selection costs. **Paid direct still pays for probes when
the decision falls back to direct.** The replay includes the longest full paired
prefix whose overhead plus cumulative audit cost is at most B. It stops at the
first unaffordable item and cannot skip it for a cheaper later item. Decimal costs
are compared exactly as supplied in JSON. If overhead exceeds B, K is zero;
`required_seconds` records that infeasible overhead, not time spent in a valid run.

The discovery event is `abs(risk_target-risk_source)`. Both deterioration and
improvement count. The separately reported `risk_increases` and `risk_decreases`
sum to Y. With K completed audits and precision p, Y = Kp. Relative to unpaid direct:

```text
delta_Y = Y_s - Y_0
        = K_s * (p_s - p_0) - (K_0 - K_s) * p_0
```

This is a standard accounting identity. The first term is precision enrichment at
the selected audit count; the second is the effect of the changed audit count.
The latter can be negative when K_s exceeds K_0. JSON stores both terms as exact
rational strings. When K_s=0, p_s is null and the count extension
`Y_s-K_s*p_0` is used. When K_0=0, p_0 and both decomposition terms are null, while
K, Y, and delta_Y remain available.

The break-even precision is `Y_0/K_s`, undefined when K_s=0. The
`precision_threshold_gt_one` flag marks an audit count at which even perfect
precision cannot match direct. Strictly more discoveries require precision above
the threshold. This arithmetic describes the supplied case; it does not guarantee
future gains or establish a statistical effect.

## A separate label-free locked decision

`locked_decision(request)` accepts the schema below. Forecasts must be externally
frozen predictions of discoveries **after all costs and the budget cutoff**, never
observed Y copied from this replay. The interface does not learn these predictions
and cannot verify when a caller actually froze them.

```json
{
  "schema_version": "measurement-value-decision/v1",
  "phase": "before_probe",
  "evidence_status": "locked_prediction",
  "context": {"model": "m", "pair": "p", "decode_cap": 8, "budget_seconds": 100},
  "forecast": {
    "frozen": true,
    "freeze_id": "externally-recorded-freeze-reference",
    "basis": "full_cost_net_discoveries",
    "validity_scope": {"model": "m", "pair": "p", "decode_cap": 8, "budget_seconds": 100},
    "uniform_action": "loss",
    "baseline_discoveries": {"direct": 10, "loss": 9, "uniform": 9},
    "paid_discoveries": {"direct": 8, "loss": 7, "primary": 10.5, "norm": 9}
  }
}
```

These numbers are **synthetic interface values**, not experimental predictions.
The four context fields must exactly match the frozen validity scope. The optional
forecast `status` is `valid` by default; a failed forecast produces
`insufficient_evidence` with `direct` before the probe and `paid_direct` after it.
Missing, unfrozen, incompatible, or unsupported forecasts do the same when controls
are usable. Every post-probe result retains the actual incurred-cost ledger below.

`uniform` means a source-fixed diagnostic action, recorded by `uniform_action`.
It is not a random audit queue. In the original full-source records all models
chose `loss`; its queue is the loss queue. A caller can obtain that queue with
`fixed_order(case, uniform_action)`. Its net forecast is retained separately as an
explicit baseline input.

The best paid forecast must be unique and at least 5% above the best of the direct,
loss, and uniform forecasts. A zero baseline requires at least one predicted
discovery. A paid tie or insufficient gain prefers the direct queue: `direct`
before the probe, `paid_direct` after the probe. Choosing a paid strategy is a
locked prediction, not confirmation of its benefit.

`before_probe` rejects `control_diagnostics`, `incurred_costs`, and unknown fields,
including supplied expensive control scores. For `after_probe`, add the following
fields to the request above (these example numbers are synthetic):

```json
{
  "phase": "after_probe",
  "incurred_costs": {"probe_seconds": 1.5, "selection_seconds": 0.5},
  "control_diagnostics": {
    "status": "valid",
    "validity_scope": {"model": "m", "pair": "p", "decode_cap": 8, "budget_seconds": 100},
    "features": {"x6": 0.2}
  }
}
```

`incurred_costs` is required after the probe and must contain exactly finite,
nonnegative `probe_seconds` and `selection_seconds`. Every post-probe result echoes
this ledger and its `incurred_seconds` total, including all fallback results.
A missing or malformed ledger is an input error; unrecorded costs are never
silently treated as zero. The supplied net forecasts already include full costs:
the decision function neither subtracts this ledger again nor re-estimates forecasts.

Before reading diagnostics or comparing forecasts, the decision checks the actual
incurred total C against B. If C is equal to or greater than B, it returns
`insufficient_evidence`, preserves `paid_direct`, and sets
`further_evaluation_allowed=false`; this paid identity records incurred costs and
does not authorize another audit. `budget_status` is `exhausted` at equality and
`exceeded` above the budget. `remaining_budget_seconds` is the signed balance B-C:
zero at exhaustion and negative after overspending. The original ledger and total
remain unchanged. This gate takes precedence over uniform fallback, failed controls,
and any favorable forecast. With positive balance, `budget_status=available` and
`further_evaluation_allowed=true`; other validity checks still apply.

The diagnostic object must contain exactly `status`, `validity_scope`, and `features`.
Its status must be `valid`, its scope must match the context, and its feature map
must be nonempty, with nonempty names and finite numeric scalar values. Booleans,
numeric strings, arrays, NaN, infinity, failed status, and unknown fields are unusable.
This validates declared feature availability and numeric inputs; it is not a
Pontryagin certificate. After-probe forecasts require valid diagnostics by default.
An externally frozen forecast that consumes no control features can explicitly set
`forecast.requires_control_diagnostics=false` and omit the diagnostic object. An
attached invalid diagnostic object is never ignored, even with that declaration.

Invalid or missing required controls bypass the count comparison and return
`fallback_uniform` with `paid_<uniform_action>` when the source-fixed action is
available. That action requires a nonempty `freeze_id`, `frozen=true`, matching
validity scope, and an allowed `uniform_action` in a locked-prediction request.
This fallback uses the frozen action declaration, not a predicted discovery count.
Otherwise the result is `insufficient_evidence` with `paid_direct`. Both paths retain
the incurred ledger. No post-probe fallback can recover the unpaid direct identity.

Changing finite diagnostic values does not rewrite the externally supplied forecasts.
An optional `behavior` field is ignored entirely in either phase: adding or changing
labels cannot alter the decision. This phase separation records information
availability; callers must enforce the actual acquisition and freeze protocol.

## Theory origin and what is measured here

The theory reference is **arXiv:2606.17762v3**. Its HTML and formal PDF number some
results differently; the titles identify the intended results:

| Result title | HTML / PDF | Role |
|---|---|---|
| [Finite-horizon Green certificate](https://arxiv.org/html/2606.17762v3#S3.Thmtheorem2) | Theorem 3.2 / 3.2 | Uniform linear inverse from hyperbolicity and scaled boundary transversality |
| [Uniform reconstruction with smooth endpoint rows](https://arxiv.org/html/2606.17762v3#S4.Thmtheorem1) | Theorem 4.1 / 4.1 | Local nonlinear reconstruction under the Green property and regularity |
| [A posteriori existence and local uniqueness certificate](https://arxiv.org/html/2606.17762v3#S5.Thmtheorem3) | Proposition 5.3 / 5.2 | Residual, inverse-Jacobian, and tube conditions for local existence and uniqueness |
| [Exponential decay of sensitivity to the terminal reward](https://arxiv.org/html/2606.17762v3#S5.Thmtheorem9) | Theorem 5.9 / 5.5 | Conditional terminal-to-initial sensitivity decay |

See the [versioned formal PDF](https://arxiv.org/pdf/2606.17762v3). These results
concern local stationary Pontryagin branches; optimality needs additional conditions.

Here **T** is that theory’s control horizon, **L** is the generation decode cap,
and **B** is a wall-clock audit budget. They cannot be substituted for one another.
AdamW training of a static soft prompt does not automatically instantiate the
theorem’s Pontryagin boundary-value system. The selector’s normalized gold-choice
Taylor feature `x6` is a **readout linearization error**, not the primary diagnostic
score or the full Pontryagin stationarity residual. The frozen ridge definitions of
primary and norm are recorded in [DATA.md](DATA.md).
These records do not verify a hyperbolic transition M, boundary matrices, or the
a posteriori inverse-Jacobian and tube bounds.

The theory supplies conditional mathematical structure. The fixed control scores
are empirical surrogates, and the cost replay is an operational measurement layer.
Neither a successful replay nor a positive delta_Y is a control-theory certificate.
The evidence labels record separately declared historical observation, locked
prediction, and independent confirmation. File presence, valid coordinates, or a
matching checksum never promotes one state to another; an independent confirmation
must be supplied with its own protocol and records.

## Verification

```console
python -m pytest tests/test_measurement_value.py
```

Focused tests cover paid overhead, both risk directions, fixed queue ties, label
isolation, full-prefix budgets, zero counts, exact decomposition, invalid inputs,
frozen forecast scope, the gain threshold, and deterministic standalone outputs.
