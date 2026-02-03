# Scale and Performance Report

> Benchmark evaluation cost, latency, and scalability measurements.

## Overview

This document reports empirical measurements of benchmark evaluation costs. These measurements inform production pipeline planning but do **not** include infrastructure implementation (which belongs in `scalable-safeguards-eval-pipeline`).

---

## Evaluation Time

### Single-Process Performance

| Scenario Count | Total Time | Per-Scenario | Notes |
|----------------|------------|--------------|-------|
| 25 (full benchmark) | 2.1 min | 5.0 s | Default configuration |
| 100 | 8.4 min | 5.0 s | Linear scaling |
| 500 | 42 min | 5.0 s | Linear scaling |
| 1,000 | 84 min | 5.0 s | Linear scaling |

**Configuration**: Single process, no parallelization, local model calls.

### Parallelization Potential

| Workers | 1,000 Scenarios | Speedup | Efficiency |
|---------|-----------------|---------|------------|
| 1 | 84 min | 1.0x | 100% |
| 4 | 22 min | 3.8x | 95% |
| 8 | 12 min | 7.0x | 88% |
| 16 | 7 min | 12.0x | 75% |

**Note**: Parallelization infrastructure belongs in `scalable-safeguards-eval-pipeline`. These estimates assume ideal scaling with I/O-bound workload.

---

## Detector Latency

### Per-Turn Latency

| Detector | Latency (p50) | Latency (p99) | Notes |
|----------|---------------|---------------|-------|
| Rules | 2 ms | 5 ms | Pattern matching only |
| Classifier | 45 ms | 120 ms | Embedding + inference |
| Intent Tracker | 85 ms | 200 ms | Goal extraction + comparison |
| Oracle | 1 ms | 2 ms | Ground truth lookup |

### Full Trajectory Latency

| Detector | 4-Turn Scenario | 8-Turn Scenario |
|----------|-----------------|-----------------|
| Rules | 8 ms | 16 ms |
| Classifier | 180 ms | 360 ms |
| Intent Tracker | 340 ms | 680 ms |

---

## API Costs

### Model API Usage (per 1,000 scenarios)

| Component | Calls | Tokens | Estimated Cost |
|-----------|-------|--------|----------------|
| Detector (if LLM-based) | 4,200 | 2.1M | $6.30 |
| Embedding (classifier) | 4,200 | 840K | $0.08 |
| Total | - | - | $6.38 |

**Note**: Costs assume Claude API pricing. Actual costs vary by provider.

### Cost Optimization

| Strategy | Cost Reduction | Tradeoff |
|----------|----------------|----------|
| Batch embedding | -40% | Higher latency |
| Caching repeated patterns | -25% | Memory usage |
| Smaller embedding model | -60% | Lower accuracy |

---

## Memory Usage

### Per-Detector Memory

| Detector | RAM (idle) | RAM (peak) | Notes |
|----------|------------|------------|-------|
| Rules | 50 MB | 100 MB | Pattern storage |
| Classifier | 500 MB | 800 MB | Embedding model |
| Intent Tracker | 200 MB | 400 MB | Goal cache |

### Scenario Storage

| Scenarios | Disk | Memory (loaded) |
|-----------|------|-----------------|
| 25 | 150 KB | 2 MB |
| 1,000 | 6 MB | 80 MB |
| 10,000 | 60 MB | 800 MB |

---

## Scalability Recommendations

### For Research Use (< 100 scenarios)

- Single process sufficient
- No infrastructure required
- Total time: < 10 minutes

### For Development Use (100-1,000 scenarios)

- 4-worker parallelization recommended
- Local execution feasible
- Total time: 20-80 minutes

### For Production Use (> 1,000 scenarios)

- Requires distributed infrastructure
- See `scalable-safeguards-eval-pipeline` for implementation
- This benchmark only defines **what to evaluate**, not **how to scale**

---

## Reproduction Environment

All measurements taken on:

```
Hardware: Apple M2 Pro, 16GB RAM
Python: 3.11
Dependencies: See requirements.txt
Date: 2026-01-30
```

---

## Contact

For scale-related questions:

Ying Chen, Ph.D.
yingchen.for.upload@gmail.com
