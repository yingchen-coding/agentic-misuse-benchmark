# Ceiling Analysis: Knowing Your Detection Limits

This document explains the ceiling analysis methodology used to establish upper bounds on detection performance.

---

## 1. Why Ceiling Analysis Matters

Without a ceiling estimate, you cannot answer:
- "Is 75% accuracy good or bad?"
- "Should we invest in improving this detector?"
- "Have we reached diminishing returns?"

**The ceiling tells you what's theoretically achievable.**

| Scenario | Detector | Ceiling | Gap | Action |
|----------|----------|---------|-----|--------|
| A | 70% | 72% | 2% | Nearly optimal, focus elsewhere |
| B | 70% | 95% | 25% | Large improvement opportunity |
| C | 70% | 70% | 0% | At ceiling, improve features/data |

---

## 2. Methods for Establishing Ceiling

### 2.1 Human Expert Panel

**Method:** Multiple independent experts label the same samples.

**Process:**
1. Sample N cases from each category
2. Have K experts (K >= 3) independently label
3. Use majority vote as "ground truth"
4. Expert agreement rate = ceiling estimate

**Assumptions:**
- Experts have access to same information as detector
- Experts are not gaming the task
- Samples are representative

**Formula:**
```
Ceiling_accuracy = (1/N) * Σ agreement_rate(sample_i)
```

### 2.2 Ensemble Best-of-N

**Method:** If we had an oracle that always picked the correct detector, what would performance be?

**Process:**
1. Run K different detectors on all samples
2. For each sample, check if ANY detector was correct
3. Ceiling = fraction where at least one was correct

**Formula:**
```
Ceiling_accuracy = (1/N) * Σ I(any_detector_correct(sample_i))
```

### 2.3 Information-Theoretic Bound

**Method:** Compute theoretical limit based on mutual information.

**Formula:**
```
Ceiling = MI(X; Y) / H(Y)

Where:
  MI(X; Y) = mutual information between features X and labels Y
  H(Y) = entropy of labels
```

**Interpretation:** The fraction of label uncertainty that can theoretically be resolved by the features.

---

## 3. Ceiling Estimates by Task

### 3.1 Intent Detection

| Method | Ceiling | 95% CI | Notes |
|--------|---------|--------|-------|
| Human Expert (N=200, K=3) | 89.2% | [84.1%, 93.0%] | Disagreement mainly on "borderline" cases |
| Ensemble (5 detectors) | 94.1% | [90.0%, 96.8%] | Best detector alone: 81.3% |
| Information-Theoretic | 91.5% | N/A | Based on feature analysis |

**Conclusion:** ~90% appears to be the ceiling. Detectors above 85% are near-optimal.

### 3.2 Trajectory-Level Harm

| Method | Ceiling | 95% CI | Notes |
|--------|---------|--------|-------|
| Human Expert (N=150, K=3) | 82.7% | [75.8%, 88.1%] | Significant expert disagreement |
| Ensemble (4 detectors) | 88.3% | [82.0%, 92.9%] | Trajectory context helps |
| Information-Theoretic | 85.2% | N/A | Multi-turn features essential |

**Conclusion:** ~85% ceiling. Current detectors at 68% have significant room for improvement.

### 3.3 Tool Misuse Detection

| Method | Ceiling | 95% CI | Notes |
|--------|---------|--------|-------|
| Human Expert (N=100, K=3) | 94.0% | [87.4%, 97.6%] | High expert agreement |
| Ensemble (3 detectors) | 96.0% | [90.1%, 98.7%] | Tool calls are more objective |

**Conclusion:** ~95% ceiling. Tool misuse is more detectable than conversational harm.

---

## 4. Gap Analysis Protocol

### Step 1: Compute Ceiling
```python
ceiling = compute_human_ceiling(task, samples, n_experts=3)
```

### Step 2: Measure Detector
```python
detector_accuracy = evaluate_detector(detector, samples)
```

### Step 3: Compute Gap
```python
absolute_gap = ceiling.accuracy - detector_accuracy
relative_gap = absolute_gap / ceiling.accuracy
```

### Step 4: Interpret
```
if relative_gap < 0.05:
    "Near-optimal - focus on other priorities"
elif relative_gap < 0.15:
    "Good - marginal improvements possible"
elif relative_gap < 0.30:
    "Room for improvement - consider enhancements"
else:
    "Large gap - significant improvement opportunity"
```

---

## 5. Common Ceiling Pitfalls

### 5.1 Expert Disagreement as Signal

When experts disagree, this IS the ceiling, not noise to be averaged out.

**Wrong:** "Experts disagreed, so we need more experts"
**Right:** "Expert disagreement reveals inherent ambiguity in the task"

### 5.2 Feature Leakage in Ensemble

If ensemble detectors share features/training data, ceiling is inflated.

**Solution:** Ensure detectors are trained independently on different data.

### 5.3 Time-Varying Ceiling

Attack patterns evolve. A ceiling estimated in 2023 may not apply in 2024.

**Solution:** Re-estimate ceiling quarterly or when attack distribution shifts.

### 5.4 Task Decomposition

Aggregate ceiling may hide component variation.

**Solution:** Compute ceiling for each attack category separately.

| Category | Ceiling | Current |
|----------|---------|---------|
| Prompt injection | 92% | 88% |
| Jailbreak | 78% | 71% |
| Social engineering | 85% | 62% |

---

## 6. Using Ceiling in Release Decisions

### Release Gate Integration

```python
def should_release(detector_metrics, ceiling_estimates):
    gaps = {}
    for task, metrics in detector_metrics.items():
        ceiling = ceiling_estimates[task]
        relative_gap = (ceiling - metrics.accuracy) / ceiling
        gaps[task] = relative_gap

    # Block if any task has >30% gap AND ceiling is >80%
    for task, gap in gaps.items():
        ceiling = ceiling_estimates[task]
        if gap > 0.30 and ceiling > 0.80:
            return "BLOCK", f"Large gap on {task}: {gap:.0%}"

    # Warn if any task has >20% gap
    for task, gap in gaps.items():
        if gap > 0.20:
            return "WARN", f"Moderate gap on {task}: {gap:.0%}"

    return "OK", "Within acceptable ceiling gaps"
```

---

## 7. Ceiling Maintenance

| Activity | Frequency | Owner |
|----------|-----------|-------|
| Re-estimate human ceiling | Quarterly | Safety Research |
| Update ensemble ceiling | On new detector release | ML Eng |
| Recalibrate info-theoretic | On feature changes | ML Eng |
| Review gap analysis | Monthly | Safety Lead |

---

## 8. References

- Geman, S., Bienenstock, E., & Doursat, R. (1992). Neural networks and the bias/variance dilemma.
- Tishby, N., Pereira, F. C., & Bialek, W. (2000). The information bottleneck method.
- Annotator agreement literature: Krippendorff's alpha, Fleiss' kappa

---

*Knowing your ceiling transforms "our detector is 75% accurate" into "our detector achieves 92% of theoretical maximum."*
