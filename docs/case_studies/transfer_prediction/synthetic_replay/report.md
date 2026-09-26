# Fixed control-diagnostic transfer predictions

**SYNTHETIC TEST DATA; not research results.**

Evidence status: `historical_observation`.
Input SHA256: `cee3817d64f54eb4817282e384b7831c33acdf76fb1945389b416713ec36beee`.
External prediction lock: `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`.

G = AUC(state diagnostic) - AUC(reference loss).

| Model | Score | Valid pairs | Full MAE | Cheap MAE | Mean MAE | Zero MAE |
|---|---|---:|---:|---:|---:|---:|
| synthetic-model | primary | 1/1 | 0.2 | 0.4 | 0.5 | 1 |
| synthetic-model | norm | 1/1 | 0.2 | 0.4 | 0.5 | 1 |

The input declares historical observation, locked prediction, or independent confirmation. This script recomputes fixed-score AUC gaps and prediction errors; it never fits a rule on behavior labels.
Undefined AUCs remain null; pairs.csv retains every pair. Prospective isolation, raw tensor/token replay, and simultaneous intervals require the separate research bundle.
Improvement over a common mean tests pair-specific information; improvement over cheap forecasts tests added control-measurement information. Point estimates do not replace corrected intervals.
Better predictions alone do not establish evaluation efficiency: probes, scoring, and completed behavioral checks must also be charged.

Theory and practice: [control-response theory](https://arxiv.org/abs/2606.17762), [PromptControlLab](https://github.com/VeraPyuyi/prompt_control_lab).
