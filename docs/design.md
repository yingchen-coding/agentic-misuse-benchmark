# Design Document: Agentic Misuse Benchmark

## Overview

This benchmark evaluates detection capabilities for **multi-turn misuse patterns** in agentic LLM systems. Unlike single-turn classification, it focuses on attacks that unfold across conversation trajectories.

## Problem Statement

Current misuse detection approaches are predominantly single-turn:
- Classify each input/output pair independently
- No context from conversation history
- No awareness of attack progression

This misses critical attack patterns:
- **Decomposed attacks**: Harmful request split across multiple benign-looking turns
- **Context manipulation**: Building false context to enable later exploitation
- **Gradual erosion**: Slowly pushing boundaries until violation occurs

## Design Principles

### 1. Trajectory-First Evaluation

Every metric considers the full conversation trajectory, not just individual turns. Detection is evaluated based on:
- Whether the attack was caught at any point
- How early in the attack sequence detection occurred
- False positives on benign context-building turns

### 2. Realistic Attack Patterns

Scenarios are based on documented real-world attack techniques:
- Prompt injection variants (direct, encoded, indirect)
- Social engineering progressions
- Context accumulation attacks
- Multi-step tool misuse

### 3. Graduated Difficulty

Each category includes scenarios ranging from obvious to subtle:
- **Easy**: Direct attacks with clear signatures
- **Medium**: Attacks requiring context awareness
- **Hard**: Subtle multi-step attacks with deferred payoff

### 4. Actionable Metrics

Metrics are designed to inform detector improvements:
- Per-category breakdown shows specific weaknesses
- Policy erosion reveals trajectory-level blind spots
- Intent drift quantifies semantic monitoring gaps

## Attack Taxonomy

### Prompt Injection

**Definition**: Attempts to override model instructions through crafted input.

**Variants**:
1. Direct instruction override
2. Delimiter-based injection
3. Roleplay/fiction wrapper
4. Encoded payload
5. Authority claim
6. Indirect injection via analyzed content

**Detection Challenge**: Distinguishing legitimate meta-discussion from actual injection.

### Policy Erosion

**Definition**: Gradual boundary-pushing that wears down safety policies.

**Variants**:
1. Escalation from benign to dangerous
2. Normalization through repetition
3. Emotional manipulation
4. Professional pretext
5. Persistence after refusal
6. Sycophancy exploitation

**Detection Challenge**: Each turn may be individually acceptable while trajectory is problematic.

### Intent Drift

**Definition**: Stated goal diverges from actual objective being pursued.

**Variants**:
1. Goal substitution via fiction
2. Context accumulation for later exploitation
3. Persona/role shift
4. Hypothetical to real transition
5. Research pretext drift
6. Debugging pretext

**Detection Challenge**: Requires tracking semantic consistency across turns.

### Coordinated Misuse

**Definition**: Multi-step attacks where individual components appear benign.

**Variants**:
1. Component assembly (benign parts → harmful whole)
2. Information aggregation
3. Split request across turns
4. Preparation and execution phases
5. Capability elicitation then exploitation
6. Trust building then exploitation

**Detection Challenge**: Requires connecting distributed attack components.

## Metrics

### Primary Metrics

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| Detection Rate | `detected / total_attacks` | Sensitivity to attacks |
| False Positive Rate | `false_alarms / benign_turns` | Specificity |
| Policy Erosion | `missed_attack_turns / attack_turns` | Trajectory blindness |
| Intent Drift | `max(0, late_suspicion - early_suspicion)` | Semantic tracking gap |

### Derived Metrics

**Trajectory Lift**: Improvement from trajectory-aware vs. per-turn detection
```
lift = trajectory_detection_rate - per_turn_detection_rate
```

**Early Detection Score**: How quickly attacks are caught
```
early_score = 1 - (detection_turn / total_turns)
```

## Baseline Detectors

### Rule-Based

Pattern matching for known signatures:
- Pros: Fast, interpretable, no training needed
- Cons: Misses novel attacks, no context awareness

### Embedding Classifier

Trajectory-aware classification using embeddings:
- Pros: Captures semantic patterns, trajectory-aware
- Cons: Requires training data, less interpretable

### Intent Tracker

Monitors goal consistency across turns:
- Pros: Directly addresses intent drift
- Cons: Requires goal extraction, computationally heavier

## Usage

### Run Single Detector
```bash
python run_benchmark.py --detector rules
```

### Compare Detectors
```bash
python run_benchmark.py --compare rules,classifier,intent
```

### Filter by Category
```bash
python run_benchmark.py --detector classifier --category policy_erosion
```

## Extension Points

### Adding Scenarios

1. Create scenario file in `scenarios/`
2. Define scenarios using `Scenario` dataclass
3. Register in `scenarios/__init__.py`

### Adding Detectors

1. Create detector file in `detectors/`
2. Extend `BaseDetector` class
3. Implement `detect_turn` and optionally `detect_trajectory`
4. Register in `detectors/__init__.py`

### Adding Metrics

1. Add metric function to `metrics.py`
2. Update `aggregate_metrics` to include new metric
3. Update `BenchmarkMetrics` dataclass

## Limitations

- Scenarios are manually crafted; adversarial generation is future work
- Baseline detectors are intentionally simple
- Ground truth relies on scenario design, not real-world outcomes
- Multi-agent coordination scenarios are simplified

## References

- Perez, E., et al. (2022). Ignore This Title and HackAPrompt.
- Greshake, K., et al. (2023). Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications.
- Wei, J., et al. (2023). Jailbroken: How Does LLM Safety Training Fail?
