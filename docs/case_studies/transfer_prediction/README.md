# Fixed diagnostic transfer across prompt cohorts

[中文](README.zh.md)

This runnable research case measures how accurately externally fixed forecasts
predict a control diagnostic's utility on a new prompt cohort. It connects the
control-response study to the [measurement-value case](../measurement_value/README.md):
predicting useful information and recovering its measurement cost are separately
testable questions.

The quantity is `G = AUC(state diagnostic) - AUC(reference loss)`. Two fixed state
scores are evaluated against full-control, cheap-feature, common development-mean,
and zero forecasts. `binary_auc` preserves ties and undefined one-class panels.
`fixed_predictions` reads only forecast metadata. `analyze_document` then compares
those predictions with observed labels; it performs no fitting.

```console
python -S scripts/run_transfer_prediction_case.py --input docs/case_studies/transfer_prediction/synthetic_test.json --out transfer-example
```

The supplied example is **synthetic** and tests the interface only. The actual
GSM8K record will be imported from `publication/compact_case.json` after the
separate raw-evidence replay passes. This directory currently contains no new
GSM8K empirical result. The script emits JSON, a complete pair/score/predictor CSV,
and English/Chinese reports. It requires only the Python standard library and
preserves earlier reports by requiring a new output directory.

## Input contract

`schema_version` is `control-transfer/v1`. Required metadata includes
`evidence_status` (`historical_observation`, `locked_prediction`, or
`independent_confirmation`), a Boolean `synthetic`, `endpoint_policy`
(`disjoint` or `shared_fixed_cases`), and an external `prediction_lock_sha256`.
Independent prompt confirmation requires disjoint endpoints.

Each entry in `pairs` contains a unique `(model, pair_id)`, increasing integer
`left_seed`/`right_seed`, `pairing_type` (`adjacent_seed` or `selection_loss`), and
`predictions.primary`/`predictions.norm`. Each prediction object contains finite
`full`, `cheap`, `uniform_mean`, and `zero` values. The zero baseline is zero and
the common-mean baseline is constant within each model and score.

Observed records additionally contain identical ordered `item_ids` within a
model, aligned finite `scores.loss`, `scores.primary`, `scores.norm`, and integer
binary behavior. Behavior is either `{risk_source, risk_target}` or
`{risk_change}`. In the latter form, direction counts remain null. A
`locked_prediction` record omits behavior, and its observed gaps/errors stay null.

The output reports all pairs, common valid coverage, AUC gaps, prediction errors,
and six mean-absolute-error improvements. An improvement over the common mean
measures pair-specific information; improvement over the cheap forecast measures
additional information from control responses. Simultaneous intervals and
prospective isolation are established in the separate research bundle. The
compact script preserves the input's declared evidence status and does not
upgrade point estimates to a successful hypothesis test.

The [control-theory paper](https://arxiv.org/abs/2606.17762) supplies conditional
response and reconstruction results. Empirical response features and behavioral
prediction still require their own tests. Control horizon `T`, generation cap
`L`, and evaluation budget `B` remain separate. The companion cost case evaluates
whether measured information offsets the behavioral inspections lost to scoring
and probing. No new efficiency claim follows from a prediction error alone.

This interface and its synthetic fixture are covered by the repository's
Apache-2.0 license. A future empirical import must retain its input, prediction,
raw-replay, and source hashes, as well as the original data licensing record.
