# Benchmark Maintenance Policy

## Scenario Lifecycle

```
PROPOSED → VALIDATED → ACTIVE → MONITORED → RETIRED
```

### Stage Definitions

| Stage | Description | Duration |
|-------|-------------|----------|
| PROPOSED | New scenario submitted | 1-2 weeks |
| VALIDATED | Tested against multiple models | 2-4 weeks |
| ACTIVE | In production benchmark | 6-24 months |
| MONITORED | Detection rate declining | 1-3 months |
| RETIRED | Removed from active suite | Permanent |

## Update Cadence

| Activity | Frequency |
|----------|-----------|
| New scenario proposals | Continuous |
| Validation runs | Monthly |
| Active suite review | Quarterly |
| Major version bump | Annually |

## Retirement Criteria

A scenario should be retired when:

1. **Model saturation:** >95% of models block it consistently
2. **Pattern obsolescence:** Attack vector no longer relevant
3. **Gaming detected:** Models trained specifically on this scenario
4. **False positive spike:** Benign queries trigger detection

## Anti-Gaming Protocol

### Detection Signals

| Signal | Indicates |
|--------|-----------|
| Sudden accuracy jump on specific scenario | Possible training on benchmark |
| Accuracy gain doesn't transfer to variants | Overfitting to exact wording |
| Public leakage of scenario text | Contamination risk |

### Response Actions

1. **Suspected gaming:** Add scenario variants
2. **Confirmed gaming:** Retire scenario, add to held-out set
3. **Systematic gaming:** Major benchmark revision

## Negative Results

### Scenarios We Retired

| Scenario | Reason | Date |
|----------|--------|------|
| basic_jailbreak_v1 | All models saturated | 2024-Q1 |
| simple_roleplay | Too easy to detect | 2024-Q2 |
| direct_harm_request | Single-turn sufficient | 2024-Q2 |

### Metrics We Abandoned

1. **Exact match accuracy**
   - Problem: Too sensitive to wording
   - Replaced with: Semantic similarity scoring

2. **Binary safe/unsafe labels**
   - Problem: Ignores severity gradation
   - Replaced with: Risk score distribution
