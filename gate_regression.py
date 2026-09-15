"""Compare a readiness-gate run with a previous report, case by case.

Aggregate rates can hide a regression: a change that fixes three cases and breaks three
others leaves the detection rate untouched. Each gate report therefore records the
outcome of every (condition, scenario) case, and a later run is compared with it pairwise.
Both runs must be on the same test set, which the fingerprint enforces.
"""
from __future__ import annotations

import hashlib
import json

from analysis.hard_negative_audit import load_traces
from evalstats import mcnemar_exact
from scenarios import get_all_scenarios
from scenarios.base import ScenarioResult

REGRESSION_MODES = ("exact", "significance")


def test_set_fingerprint() -> str:
    """SHA-256 over every scenario and every benign trace the stress protocol inserts."""
    payload = {
        "scenarios": [s.to_dict() for s in get_all_scenarios()],
        "traces": {name: [[t.role, t.content] for t in turns]
                   for name, turns in sorted(load_traces().items())},
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def scenario_outcomes(results: list[ScenarioResult],
                      stress_rows: dict | None = None) -> dict[str, dict[str, bool]]:
    """Outcome per case, keyed "<condition>/<scenario id>"."""
    outcomes = {
        f"baseline/{r.scenario_id}": {"detected": bool(r.detected),
                                      "false_positive": bool(r.false_positive)}
        for r in results
    }
    scenario_ids = [r.scenario_id for r in results]
    for condition, row in (stress_rows or {}).items():
        if condition == "baseline":
            continue
        detected, flagged = set(row["detected_ids"]), set(row["false_positive_ids"])
        for sid in scenario_ids:
            outcomes[f"{condition}/{sid}"] = {"detected": sid in detected,
                                              "false_positive": sid in flagged}
    return outcomes


def compare_to_baseline(current: dict[str, dict[str, bool]],
                        baseline: dict[str, dict[str, bool]], rule: dict) -> dict:
    """Paired comparison of two runs' case outcomes.

    rule["mode"] == "exact": any newly missed case is a regression — right for
    deterministic detectors, where a changed outcome is never noise.
    rule["mode"] == "significance": a regression only when more cases regressed than
    improved and the exact McNemar test gives p < rule["alpha"] — for sampled model
    outputs, where individual flips can be noise.
    """
    missing = sorted(set(current) - set(baseline))
    if missing:
        raise ValueError(
            f"baseline has no outcome for {len(missing)} case(s), e.g. {missing[0]}; "
            "regenerate it with the same --stress setting")

    newly_missed = sorted(k for k, v in current.items()
                          if baseline[k]["detected"] and not v["detected"])
    newly_caught = sorted(k for k, v in current.items()
                          if not baseline[k]["detected"] and v["detected"])
    new_false_positives = sorted(k for k, v in current.items()
                                 if v["false_positive"] and not baseline[k]["false_positive"])
    p_value = mcnemar_exact(len(newly_missed), len(newly_caught))

    if rule["mode"] == "exact":
        regressed = bool(newly_missed)
    else:
        regressed = len(newly_missed) > len(newly_caught) and p_value < rule["alpha"]

    return {
        "cases_compared": len(current),
        "newly_missed": newly_missed,
        "newly_caught": newly_caught,
        "new_false_positives": new_false_positives,
        "mcnemar_p": round(p_value, 10),
        "regressed": regressed,
    }
