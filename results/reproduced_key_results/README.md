# Reproduced Key Results

This directory contains a committed smoke report from the maintained benchmark workflow:

```bash
OUTPUT_DIR=results/reproduced_key_results bash scripts/reproduce_key_results.sh
```

The files are intentionally small CSV/TXT artifacts so a reviewer can inspect the benchmark output
without rerunning the code first.

## What Is Included

| File | Purpose |
| --- | --- |
| `scenarios.txt` | Benchmark scenario inventory. |
| `detectors.txt` | Bundled detector inventory. |
| `rules.csv` | Full benchmark run for the deterministic rules baseline. |
| `classifier.csv` | Full benchmark run for the trajectory-aware classifier baseline. |
| `intent.csv` | Full benchmark run for the intent-drift diagnostic baseline. |
| `*_comparison.csv` | Detector comparison exports from the maintained compare run. |
| `rules_<category>.csv` | Category smoke checks for prompt injection, policy erosion, intent drift, and coordinated misuse. |

## Current Smoke Summary

| Detector | Detection rate | False positive rate | Role |
| --- | ---: | ---: | --- |
| Rules baseline | 100.0% | 0.0% | Deterministic guardrail baseline. |
| Classifier | 84.0% | 4.0% | Semantic trajectory baseline. |
| Intent tracker | 24.0% | 8.0% | Drift-only diagnostic baseline. |

These outputs are not a release decision. They are benchmark evidence that feeds downstream release
gates such as `safety-harness`.
