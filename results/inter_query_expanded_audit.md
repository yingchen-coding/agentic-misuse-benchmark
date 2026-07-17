# Expanded Inter-Query Audit

Combined traces: 75 ({'original': 25, 'metamorphic': 25, 'adaptive': 25}).

| Detector | Single recall | Inter recall | Inter CI | Query FPR | Inter-only | Single-only | p(inter better) |
|---|---:|---:|---:|---:|---:|---:|---:|
| rules | 0.920 | 0.920 | [0.853, 0.973] | 0.000 | 0 | 0 | 1.000000 |
| classifier | 0.520 | 0.693 | [0.587, 0.8] | 0.022 | 13 | 0 | 0.000122 |
| intent | 0.000 | 0.240 | [0.147, 0.347] | 0.044 | 18 | 0 | 0.000004 |

## By Suite

### rules

| Suite | Single recall | Inter recall | Query FPR |
|---|---:|---:|---:|
| original | 1.000 | 1.000 | 0.000 |
| metamorphic | 0.960 | 0.960 | 0.000 |
| adaptive | 0.800 | 0.800 | 0.000 |

### classifier

| Suite | Single recall | Inter recall | Query FPR |
|---|---:|---:|---:|
| original | 0.640 | 0.840 | 0.022 |
| metamorphic | 0.560 | 0.760 | 0.022 |
| adaptive | 0.360 | 0.480 | 0.022 |

### intent

| Suite | Single recall | Inter recall | Query FPR |
|---|---:|---:|---:|
| original | 0.000 | 0.240 | 0.044 |
| metamorphic | 0.000 | 0.240 | 0.044 |
| adaptive | 0.000 | 0.240 | 0.044 |

## Interpretation

This is a deterministic stress audit, not an independent external benchmark. Its value is that the same single-vs-inter-query contrast is rerun after label-preserving surface changes. If the context gain disappears under these variants, the paper's main claim is brittle.
