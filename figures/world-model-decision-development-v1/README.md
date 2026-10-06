# Development action-ranking gate

This is designed development evidence, separate from the final evaluation panel.

[SVG](action-ranking-gate.svg) · [PDF](action-ranking-gate.pdf) · [PNG](action-ranking-gate.png)

Development evidence only: six designed law/environment arenas, each contributing three dependent focal-state comparisons. Left: the same legal observation and forecast randomness are used twice, substituting low versus high local infrastructure return b while keeping the other supplied coefficients fixed. Markers show the predicted private-utility advantage of investing all over redistributing all. Horizontal bars are declared gate tolerances, max(0.005, 3 times the paired planning Monte Carlo standard error); they are not 95% confidence intervals. Right: the realized paired evaluator-branch advantage under each arena’s actual planted law. The narrow gray band marks the ±0.005 material-value threshold, not uncertainty. Colors identify focal societies; marker shapes distinguish substituted laws and realized values. Labels list development case and society IDs. These cases were designed for task development, are not an IID evaluation law sample, and supply no estimate of general performance. No development result is pooled into the subsequent evaluation panel. Positive utility can reflect terminal wealth rather than additional consumption. All comparisons use the same 32-tick window and three-action menu.

Gate **passed**. Recorded qualification counts: known_positive_one=7, rank_switch=17, realized_one=6, realized_zero=11.

[Recorded state table](development-states.csv) · [Source/output hashes](manifest.json)

The renderer checks completed-study hashes, committed forecast gaps, stated Monte Carlo tolerances, action-rank qualification and realized branch arithmetic. No new forecasts, learning or rollouts occur. Colors follow Chromatic Field v1. All three exports are generated from the same saved state rows.

```bash
.venv/bin/python scripts/visualize_world_model_decision_gate.py
```
