# Measurement value under a fixed budget

Cost replay of the supplied records.

Declared evidence status: `historical_observation`.
Input file SHA256: `eafacdb018e50f40199012e6d422599bcd92477d6e34089f53e5ca45fbdd2257`.

The input declares this status; integrity and label availability do not upgrade evidence.
A discovery is abs(risk_target-risk_source); both risk increases and decreases count.
K counts completed paired audits, p their discovery fraction, and Y discoveries.
Every delta_Y compares with the unpaid direct strategy in the same case.

The table aggregates by model and strategy. strategies.csv retains each case;
results.json retains the full queues and exact decomposition.
Cases without both probe_seconds and selection_seconds have no paid-strategy rows.

| Model | Strategy | Pairs | Total K | Total Y | Mean Y | Total delta_Y |
|---|---|---:|---:|---:|---:|---:|
| granite | direct | 19 | 4580 | 1286 | 67.684211 | 0 |
| granite | loss | 19 | 1207 | 626 | 32.947368 | -660 |
| granite | norm | 19 | 1883 | 619 | 32.578947 | -667 |
| granite | paid_direct | 19 | 4343 | 1219 | 64.157895 | -67 |
| granite | paid_loss | 19 | 971 | 506 | 26.631579 | -780 |
| granite | paid_norm | 19 | 1645 | 540 | 28.421053 | -746 |
| granite | paid_primary | 19 | 1333 | 442 | 23.263158 | -844 |
| granite | primary | 19 | 1567 | 528 | 27.789474 | -758 |
| ministral | direct | 19 | 5431 | 1144 | 60.210526 | 0 |
| ministral | loss | 19 | 1496 | 706 | 37.157895 | -438 |
| ministral | norm | 19 | 2143 | 285 | 15.000000 | -859 |
| ministral | paid_direct | 19 | 5051 | 1064 | 56.000000 | -80 |
| ministral | paid_loss | 19 | 1119 | 518 | 27.263158 | -626 |
| ministral | paid_norm | 19 | 1758 | 221 | 11.631579 | -923 |
| ministral | paid_primary | 19 | 831 | 150 | 7.894737 | -994 |
| ministral | primary | 19 | 1218 | 230 | 12.105263 | -914 |
| qwen35 | direct | 16 | 6400 | 690 | 43.125000 | 0 |
| qwen35 | loss | 16 | 1277 | 516 | 32.250000 | -174 |
| qwen35 | norm | 16 | 1624 | 272 | 17.000000 | -418 |
| qwen35 | paid_direct | 16 | 6293 | 677 | 42.312500 | -13 |
| qwen35 | paid_loss | 16 | 893 | 404 | 25.250000 | -286 |
| qwen35 | paid_norm | 16 | 1241 | 210 | 13.125000 | -480 |
| qwen35 | paid_primary | 16 | 1102 | 210 | 13.125000 | -480 |
| qwen35 | primary | 16 | 1485 | 256 | 16.000000 | -434 |

`delta_Y = K_s*(p_s-p_0) - (K_0-K_s)*p_0`.

This is a standard accounting identity, not a new theorem from the paper. Exact rational terms are retained in JSON. p is null at K=0; the precision decomposition is undefined at K_0=0, while Y and delta_Y remain defined.

The break-even precision is Y_0/K_s. A value above one means even perfect precision cannot match direct at that audit count. This describes observed counts and gives no guarantee for a future case.

T is the paper's control horizon, L the decode cap, and B the wall-clock budget; they are distinct quantities.

Theory boundaries and the separate locked-decision interface: [measurement-value case documentation](https://github.com/VeraPyuyi/prompt_control_lab/tree/main/docs/case_studies/measurement_value).
