# Local experiment examples

These examples use the `experiment/v1` JSON contract. Run and optimization jobs
make real provider requests; import jobs score already recorded predictions.
Credentials are referenced by environment variable name and never placed in JSON.

`synthetic-import.json` is an explicitly synthetic fixture for learning the report
format. Its predetermined difference is not evidence that a model improved.

`live-run.json` compares two prompts on a small exact-answer arithmetic task.
`live-optimize.json` searches the same baseline prompt with GEPA, then compares the
frozen selection on a withheld split. Replace `model` and the localhost `base_url`
with the OpenAI-compatible service you actually intend to use, and set
`PCL_EXPERIMENT_API_KEY`. A localhost server that ignores credentials can use a
non-secret placeholder value for that variable. Remote endpoints require HTTPS.
The examples deliberately use a conversational baseline against an exact-answer
metric to illustrate how a format contract affects scoring; this is not a
representative model capability benchmark.

```text
pip install "promptcontrollab[ui,optimize]"
pcl experiment run --config examples/experiments/live-run.json
pcl experiment import --config examples/experiments/synthetic-import.json
pcl experiment optimize --config examples/experiments/live-optimize.json
```

Optimization uses GEPA 0.1.4 and shares the experiment's finite request, output-token
and elapsed-time budgets for both task and reflection calls. The runtime reserves
capacity for the final baseline/selection comparison before search. GEPA receives
training and validation data only. Training examples produce reflection feedback;
only complete validation scores can select a candidate. No improvement is a valid
completed search and keeps the baseline. Only the final withheld comparison can
support a claim about performance outside search.

The defaults are five rounds, one proposal per round, and stopping after two rounds
without validation improvement. Checkpoints are JSON. Resume keeps the original
call ledger and budgets, and starts a new GEPA pass from the fully validated best
prompt; it does not deserialize or replay GEPA pickle state. These examples do not
contain measured live-model results.
