# Inter-Query Deep Audit

Scenarios: 25 vulnerable traces.

## Headline

| Detector | Single recall | Inter recall | Recall CI (inter) | Query FPR (inter) | Inter-only wins | Single-only wins | p(inter better) |
|---|---:|---:|---:|---:|---:|---:|---:|
| rules | 1.000 | 1.000 | [1.0, 1.0] | 0.000 | 0 | 0 | 1.000000 |
| classifier | 0.640 | 0.840 | [0.68, 0.96] | 0.022 | 5 | 0 | 0.031250 |
| intent | 0.000 | 0.240 | [0.08, 0.4] | 0.044 | 6 | 0 | 0.015625 |

## History Window Ablation

### rules

| Visible history turns | Trace recall | Query FPR | Mean lead |
|---:|---:|---:|---:|
| 0 | 1.000 | 0.000 | 0.56 |
| 1 | 1.000 | 0.000 | 0.56 |
| 2 | 1.000 | 0.000 | 0.56 |
| 3 | 1.000 | 0.000 | 0.56 |
| full | 1.000 | 0.000 | 0.56 |

### classifier

| Visible history turns | Trace recall | Query FPR | Mean lead |
|---:|---:|---:|---:|
| 0 | 0.640 | 0.022 | 0.25 |
| 1 | 0.640 | 0.022 | 0.25 |
| 2 | 0.760 | 0.022 | 0.26 |
| 3 | 0.760 | 0.022 | 0.26 |
| full | 0.760 | 0.022 | 0.26 |

### intent

| Visible history turns | Trace recall | Query FPR | Mean lead |
|---:|---:|---:|---:|
| 0 | 0.000 | 0.000 | 0.00 |
| 1 | 0.520 | 0.222 | 0.62 |
| 2 | 0.560 | 0.200 | 1.07 |
| 3 | 0.480 | 0.200 | 1.17 |
| full | 0.480 | 0.200 | 1.17 |

## Benign-Only Hard Negatives

| Detector | Mode | Query FPR | Trace flag rate | Flags / turns |
|---|---|---:|---:|---:|
| rules | single_query | 0.000 | 0.000 | 0 / 45 |
| rules | inter_query | 0.000 | 0.000 | 0 / 45 |
| classifier | single_query | 0.022 | 0.042 | 1 / 45 |
| classifier | inter_query | 0.022 | 0.042 | 1 / 45 |
| intent | single_query | 0.000 | 0.000 | 0 / 45 |
| intent | inter_query | 0.044 | 0.083 | 2 / 45 |

## Interpretation

The classifier result is the strongest evidence: the same detector gains recall when it can see cross-turn context, while query-level false positives stay flat in the headline comparison. The rules detector is a negative control: it barely changes because it is surface-pattern driven and not designed to use trajectory state. The intent tracker is a mechanism probe: it is mostly useless with no history and only becomes meaningful as visible history grows.

The hard-negative section is deliberately conservative: it strips attack turns and asks whether the detector flags the remaining benign-looking context. This is not a deployment FPR estimate, but it is a better stress test than counting only isolated benign turns inside vulnerable traces.
