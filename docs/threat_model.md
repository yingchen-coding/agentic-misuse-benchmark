# Threat Model Coverage Matrix

## Overview

This document maps benchmark scenarios to attacker capabilities, intent clarity, and harm domains to ensure systematic coverage and identify gaps.

---

## Threat Model Dimensions

### Attacker Capability Levels

| Level | Description | Example |
|-------|-------------|---------|
| **L1: Naive** | No adversarial intent, accidental misuse | User stumbles into harmful territory |
| **L2: Script Kiddie** | Uses known attack templates | Copy-paste jailbreaks from forums |
| **L3: Sophisticated** | Adapts attacks based on feedback | Iterates on failed attempts |
| **L4: Expert** | Designs novel attack strategies | Creates new decomposition patterns |

### Intent Clarity Levels

| Level | Description | Detection Difficulty |
|-------|-------------|---------------------|
| **Explicit** | Harmful intent stated directly | Easy (single-turn detection works) |
| **Implicit** | Intent inferable from context | Medium (requires context) |
| **Obfuscated** | Intent actively hidden | Hard (trajectory analysis needed) |
| **Emergent** | Intent emerges from benign steps | Very Hard (no single smoking gun) |

### Harm Domains

| Domain | Examples | Severity Range |
|--------|----------|----------------|
| **Information** | Doxxing, privacy violation | Medium-High |
| **Manipulation** | Social engineering, fraud | Medium-High |
| **Technical** | Malware, hacking assistance | High-Critical |
| **Physical** | Weapons, dangerous synthesis | Critical |
| **Systemic** | Election manipulation, mass harm | Critical |

---

## Scenario Coverage Matrix

| Scenario | Capability | Intent | Harm Domain | Turns |
|----------|------------|--------|-------------|-------|
| prompt_injection_basic | L2 | Explicit | Technical | 1-2 |
| prompt_injection_nested | L3 | Obfuscated | Technical | 3-5 |
| policy_erosion_gradual | L3 | Emergent | Various | 5-10 |
| policy_erosion_rapid | L2 | Implicit | Various | 3-5 |
| intent_drift_subtle | L3 | Obfuscated | Various | 5-8 |
| intent_drift_explicit | L2 | Implicit | Various | 3-5 |
| coordinated_misuse_basic | L3 | Emergent | Information | 5-10 |
| coordinated_misuse_advanced | L4 | Obfuscated | Systemic | 10+ |
| decomposition_chemistry | L3 | Emergent | Physical | 4-6 |
| decomposition_technical | L3 | Emergent | Technical | 4-6 |
| context_manipulation | L3 | Obfuscated | Various | 3-5 |
| tool_hallucination | L2 | Implicit | Technical | 2-4 |
| authority_spoofing | L3 | Obfuscated | Manipulation | 3-5 |
| persona_exploitation | L3 | Obfuscated | Various | 4-7 |

### Coverage Gaps Identified

- ❌ L1 (Naive) attackers underrepresented
- ❌ Systemic harm scenarios limited
- ❌ Very long trajectories (20+ turns) not covered

---

## Failure Cost Asymmetry

### Why False Negatives Are Worse

| Error Type | Immediate Cost | Long-term Cost |
|------------|----------------|----------------|
| **False Positive** | User friction, support tickets | Trust erosion, churn |
| **False Negative** | Potential harm occurs | Liability, reputation damage, regulatory action |

**Asymmetry ratio:** We estimate FN cost is 10-100x FP cost for safety-critical applications.

### Implications for Detector Design

1. **Threshold bias:** Default toward lower thresholds (more sensitive)
2. **Escalation path:** FPs can be recovered via human review
3. **Audit trail:** FNs require forensic capability

---

## Ceiling Analysis

### Theoretical Detection Limits

Even a perfect detector faces fundamental limits:

| Scenario Type | Max Detectable | Reason |
|---------------|----------------|--------|
| Explicit harmful intent | ~99% | Clear signal |
| Implicit harmful intent | ~90% | Requires inference |
| Obfuscated intent | ~75% | Adversarial hiding |
| Emergent intent | ~60% | No single-turn signal |
| Zero-day attacks | ~40% | Out of distribution |

### Why 100% Is Impossible

1. **Dual-use knowledge:** Same information can be benign or harmful
2. **Intent ambiguity:** Legitimate research vs. malicious preparation
3. **Adversarial adaptation:** Attackers evolve faster than detectors
4. **False flag attacks:** Making benign queries look suspicious

### Preventing Benchmark Overfitting

To avoid detectors gaming our benchmark:

1. **Held-out test set:** 20% of scenarios never published
2. **Scenario mutation:** Regular refresh with new variants
3. **Out-of-distribution eval:** Test on scenarios from other benchmarks
4. **Human red-team:** Periodic expert attack sessions
5. **Negative examples:** Include hard benign cases that look suspicious

---

## Benchmark Limitations

### What This Benchmark Does NOT Cover

- Real-time adaptive attackers (our attacks are static per run)
- Multi-user coordinated attacks (single conversation only)
- Attacks exploiting external tool state
- Social engineering of human operators

### Known Biases

- English-language bias
- Western cultural context bias
- Technical domain overrepresentation
- Synthetic attack patterns (not from real incidents)

---

## Recommendations for Benchmark Users

1. **Don't use accuracy as sole metric** — consider precision/recall tradeoff
2. **Test on out-of-distribution scenarios** — don't trust in-distribution results
3. **Monitor for concept drift** — attacks evolve, re-evaluate regularly
4. **Combine with human red-teaming** — benchmarks are necessary but not sufficient
