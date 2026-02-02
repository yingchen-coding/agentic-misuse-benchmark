# Benchmark Lifecycle Policy

This document defines the lifecycle management policy for the agentic misuse benchmark, including versioning, deprecation, and refresh procedures.

---

## 1. Lifecycle Stages

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  DRAFT   │ -> │  ACTIVE  │ -> │ DEPRECATED │ -> │ RETIRED  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
   6 months       2 years         6 months        Archive
```

### Stage Definitions

| Stage | Duration | Usage | Support |
|-------|----------|-------|---------|
| **Draft** | ~6 months | Internal testing only | Full development |
| **Active** | ~2 years | Production evaluation | Bug fixes, minor updates |
| **Deprecated** | 6 months | Legacy support | Critical fixes only |
| **Retired** | Permanent | Archive reference | None |

---

## 2. Version Numbering

### Format: `MAJOR.MINOR.PATCH`

| Component | When to Increment | Example |
|-----------|-------------------|---------|
| **MAJOR** | Breaking changes, new categories | 1.0 -> 2.0 |
| **MINOR** | New scenarios, non-breaking additions | 1.0 -> 1.1 |
| **PATCH** | Bug fixes, label corrections | 1.0.0 -> 1.0.1 |

### Breaking Changes

A change is "breaking" if:
- Scenarios are removed
- Labels are changed
- Category definitions change
- Scoring methodology changes

Non-breaking additions can be made at any time.

---

## 3. Refresh Triggers

### 3.1 Scheduled Refresh

| Trigger | Frequency | Action |
|---------|-----------|--------|
| Quarterly review | Every 3 months | Assess freshness metrics |
| Annual major refresh | Every 12 months | Add new attack categories |
| Ceiling recalibration | Every 6 months | Re-estimate detection ceiling |

### 3.2 Event-Driven Refresh

| Event | Response Time | Action |
|-------|---------------|--------|
| New attack class discovered | 30 days | Add representative scenarios |
| Model architecture change | 60 days | Validate benchmark still discriminates |
| Ceiling shift >10% | 30 days | Investigate and recalibrate |
| >20% scenarios "solved" | 90 days | Add harder scenarios |

### 3.3 Freshness Metrics

Monitor these to detect staleness:

| Metric | Warning Threshold | Action Threshold |
|--------|-------------------|------------------|
| Pass rate increase | >5% per quarter | >15% per quarter |
| Scenario solve rate | >30% solved | >50% solved |
| Attack coverage vs wild | <80% coverage | <60% coverage |
| Expert relevance rating | <4.0/5.0 | <3.0/5.0 |

---

## 4. Scenario Lifecycle

### 4.1 Addition Criteria

New scenarios must meet ALL criteria:

- [ ] Represents real attack pattern (citation or incident reference)
- [ ] Not covered by existing scenarios (novelty check)
- [ ] Human expert validated (>80% agreement on label)
- [ ] Discriminates between models (not 100% pass or 100% fail)
- [ ] Documented provenance and rationale

### 4.2 Deprecation Criteria

Scenarios are deprecated when ANY of:

- Pass rate >95% for 2 consecutive quarters (too easy)
- Attack pattern no longer relevant (obsolete)
- Label ambiguity >30% expert disagreement (unclear)
- Superseded by better scenario (redundant)

### 4.3 Retirement Process

```
1. Mark as DEPRECATED in metadata
2. Annotate with deprecation reason
3. Continue including in test runs (with flag)
4. After 6 months, move to RETIRED archive
5. Maintain in archive for historical comparison
```

---

## 5. Data Split Lifecycle

### 5.1 Train/Test Split Rotation

```
Quarter 1: Train on H1'23, Test on H2'23
Quarter 2: Train on H2'23, Test on H1'24
Quarter 3: Train on H1'24, Test on H2'24
...
```

**Rationale:** Temporal splits prevent overfitting to historical patterns.

### 5.2 Holdout Refresh

| Holdout Set | Created | Retire After | Replacement |
|-------------|---------|--------------|-------------|
| golden_v1 | 2024-01 | 2025-01 | golden_v2 |
| golden_v2 | 2025-01 | 2026-01 | golden_v3 |

**Rule:** Holdout sets are NEVER used during development. Any access triggers audit.

---

## 6. Category Lifecycle

### Current Categories (v1.x)

| Category | Added | Status | Next Review |
|----------|-------|--------|-------------|
| prompt_injection | v1.0 | Active | 2025-01 |
| jailbreak | v1.0 | Active | 2025-01 |
| social_engineering | v1.0 | Active | 2025-01 |
| tool_misuse | v1.1 | Active | 2025-04 |
| multi_turn_erosion | v1.2 | Active | 2025-07 |

### Planned Categories (v2.x)

| Category | Target Version | Status |
|----------|----------------|--------|
| agentic_coordination | v2.0 | Draft |
| memory_exploitation | v2.0 | Draft |
| tool_chain_attacks | v2.1 | Planned |

---

## 7. Compatibility Matrix

| Benchmark Version | Model Versions Tested | Detector Versions |
|-------------------|----------------------|-------------------|
| v1.0 | GPT-4-0314, Claude-2 | detector_v1.x |
| v1.1 | GPT-4-0613, Claude-2.1 | detector_v1.x, v2.x |
| v1.2 | GPT-4-turbo, Claude-3 | detector_v2.x |
| v2.0 (planned) | GPT-5, Claude-4 | detector_v3.x |

---

## 8. Deprecation Announcements

### Format

```markdown
## Deprecation Notice: [Scenario/Category ID]

**Effective Date:** YYYY-MM-DD
**Retirement Date:** YYYY-MM-DD (6 months after deprecation)

**Reason:** [One of: too_easy, obsolete, unclear, superseded]

**Migration:**
- If too_easy: Use [harder_scenario_id] instead
- If obsolete: No replacement needed
- If unclear: Use [clarified_scenario_id] instead
- If superseded: Use [replacement_scenario_id] instead

**Impact:**
- Results will be flagged as "deprecated" in reports
- Scenario will be excluded from aggregate metrics after retirement
```

---

## 9. Governance

### Roles

| Role | Responsibility |
|------|----------------|
| **Benchmark Owner** | Overall lifecycle decisions |
| **Category Leads** | Category-specific additions/deprecations |
| **Review Board** | Approve MAJOR version changes |
| **Community** | Propose new scenarios via RFC |

### Decision Process

| Change Type | Approval Required |
|-------------|-------------------|
| PATCH | Benchmark Owner |
| MINOR | Benchmark Owner + Category Lead |
| MAJOR | Review Board (majority vote) |
| New Category | Review Board (unanimous) |

---

## 10. Archival Policy

### What We Archive

- All deprecated scenarios with full metadata
- Historical performance data per model version
- Ceiling estimates at time of deprecation
- Deprecation rationale

### Archive Format

```
archive/
├── v1.0/
│   ├── scenarios/
│   ├── results/
│   └── metadata.json
├── v1.1/
└── deprecated/
    ├── scenario_001.json
    └── scenario_002.json
```

### Retention

- Active versions: Immediate access
- Deprecated: 6 months active, then archive
- Retired: Archive indefinitely
- Raw data: 7 year retention per policy

---

*A benchmark without lifecycle management becomes a benchmark without validity.*
