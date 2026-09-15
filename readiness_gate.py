#!/usr/bin/env python3
"""Readiness gate on measured benchmark metrics.

Runs each requested detector on the labeled scenarios, checks the measured metrics against
config/readiness_gate.yaml, and exits with the worst verdict so CI can act on it:
    0 = OK, 1 = WARN, 2 = BLOCK

The verdict is about detector metrics only. Per the README boundary statement it is an input to a
release gate, not a release decision.

Every rate check also reports its sample counts, a 95% Wilson interval, and whether the
suite is big enough to decide it ("resolved") or not ("underpowered", with the sample size
that would resolve it). --require-power turns underpowered checks into WARNs.

With --stress it also runs analysis/conversation_stress.py and checks every stress condition
(longer conversations, topic shifts, tool relay) for detection drop and benign-turn false positives.

With --baseline it compares every (condition, scenario) outcome with a previous --output report
on the same test set and blocks on regressions, per the `regression` section of the config.

Run:  python3 readiness_gate.py --detector rules
      python3 readiness_gate.py --detector rules classifier intent --output report.json
      python3 readiness_gate.py --detector rules --stress --require-power
      python3 readiness_gate.py --detector rules --stress --baseline baselines/gate_report.json
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

import yaml

from analysis.conversation_stress import run as run_stress
from detectors import get_detector, list_detectors
from evalstats import n_to_resolve, wilson_interval
from gate_regression import REGRESSION_MODES, compare_to_baseline, scenario_outcomes, test_set_fingerprint
from metrics import BenchmarkMetrics, aggregate_metrics
from run_benchmark import run_benchmark
from scenarios import get_all_scenarios
from scenarios.base import ScenarioResult

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = REPO_ROOT / "config" / "readiness_gate.yaml"
REPORT_SCHEMA_VERSION = 2
VERDICTS = ("OK", "WARN", "BLOCK")
EXIT_CODES = {"OK": 0, "WARN": 1, "BLOCK": 2}
HIGHER_IS_BETTER = ("detection_rate", "category_detection_rate", "early_warning_rate")
LOWER_IS_BETTER = ("false_positive_rate", "stress_detection_drop", "stress_benign_turn_fpr")


def load_thresholds(path: Path) -> dict:
    thresholds = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(thresholds, dict):
        raise ValueError(f"{path.name}: expected a mapping of thresholds")
    for check in HIGHER_IS_BETTER + LOWER_IS_BETTER:
        if check not in thresholds:
            raise ValueError(f"{path.name}: missing threshold '{check}'")
        rule = thresholds[check]
        if not isinstance(rule, dict) or not {"warn", "block"} <= set(rule):
            raise ValueError(f"{path.name}: '{check}' needs both warn and block")
        if check in HIGHER_IS_BETTER and rule["block"] > rule["warn"]:
            raise ValueError(f"{path.name}: '{check}' block must not exceed warn")
        if check in LOWER_IS_BETTER and rule["block"] < rule["warn"]:
            raise ValueError(f"{path.name}: '{check}' block must not be below warn")
    regression = thresholds.get("regression")
    if not isinstance(regression, dict) or regression.get("mode") not in REGRESSION_MODES:
        raise ValueError(f"{path.name}: 'regression' needs mode {' or '.join(REGRESSION_MODES)}")
    if not 0 < float(regression.get("alpha", 0)) < 1:
        raise ValueError(f"{path.name}: 'regression' alpha must be in (0, 1)")
    return thresholds


def measured_counts(results: list[ScenarioResult]) -> dict[str, tuple[int, int]]:
    """(successes, trials) behind each rate check, keyed by check name."""
    counts = {
        "detection_rate": (sum(r.detected for r in results), len(results)),
        "false_positive_rate": (sum(r.false_positive for r in results), len(results)),
    }
    for category in sorted({r.category for r in results}):
        in_category = [r for r in results if r.category == category]
        counts[f"category_detection_rate[{category}]"] = (
            sum(r.detected for r in in_category), len(in_category))
    caught = [r for r in results
              if r.detected and r.detection_turn is not None and r.first_attack_turn is not None]
    counts["early_warning_rate"] = (
        sum(r.detection_turn == r.first_attack_turn for r in caught), len(caught))
    return counts


def _evidence(name: str, rule: dict, higher_is_better: bool, counts: dict) -> dict | None:
    if name not in counts:
        return None
    successes, n = counts[name]
    bar = rule["block"]
    if n == 0:
        return {"check": name, "successes": 0, "n": 0, "ci95": None, "block_bar": bar,
                "status": "no data", "n_to_resolve": None}
    lo, hi = wilson_interval(successes, n)
    if higher_is_better:
        resolved = hi < bar or lo >= bar
    else:
        resolved = lo > bar or hi <= bar
    return {
        "check": name, "successes": successes, "n": n,
        "ci95": [round(lo, 3), round(hi, 3)], "block_bar": bar,
        "status": "resolved" if resolved else "underpowered",
        "n_to_resolve": None if resolved else n_to_resolve(successes / n, bar),
    }


def _check(name: str, value: float, rule: dict, higher_is_better: bool, reasons: list[dict],
           evidence: list[dict], counts: dict | None, require_power: bool) -> None:
    op = "<" if higher_is_better else ">"
    fails = (lambda bar: value < bar) if higher_is_better else (lambda bar: value > bar)
    if fails(rule["block"]):
        reasons.append({"level": "BLOCK", "check": f"{name} {value:.3f} {op} {rule['block']}"})
    elif fails(rule["warn"]):
        reasons.append({"level": "WARN", "check": f"{name} {value:.3f} {op} {rule['warn']}"})

    item = _evidence(name, rule, higher_is_better, counts or {})
    if item is None:
        return
    evidence.append(item)
    if require_power and item["status"] != "resolved":
        detail = (f"{item['successes']}/{item['n']}, 95% CI {item['ci95']} spans the block bar "
                  f"{item['block_bar']}" if item["n"] else "no samples")
        if item["n_to_resolve"]:
            detail += f"; ~{item['n_to_resolve']} samples would resolve it"
        reasons.append({"level": "WARN", "check": f"underpowered: {name} {detail}"})


def worst(verdicts) -> str:
    return max(verdicts, key=VERDICTS.index, default="OK")


def evaluate(metrics: BenchmarkMetrics, thresholds: dict,
             stress_conditions: dict | None = None,
             counts: dict[str, tuple[int, int]] | None = None,
             require_power: bool = False) -> dict:
    reasons: list[dict] = []
    evidence: list[dict] = []
    _check("detection_rate", metrics.detection_rate, thresholds["detection_rate"], True,
           reasons, evidence, counts, require_power)
    for category, rate in sorted(metrics.category_detection_rates.items()):
        _check(f"category_detection_rate[{category}]", rate, thresholds["category_detection_rate"],
               True, reasons, evidence, counts, require_power)
    _check("false_positive_rate", metrics.false_positive_rate, thresholds["false_positive_rate"],
           False, reasons, evidence, counts, require_power)
    _check("early_warning_rate", metrics.early_warning_rate, thresholds["early_warning_rate"],
           True, reasons, evidence, counts, require_power)
    for condition, row in (stress_conditions or {}).items():
        if condition == "baseline":
            continue
        _check(f"stress[{condition}] detection_drop", row["detection_drop"],
               thresholds["stress_detection_drop"], False, reasons, evidence, None, False)
        _check(f"stress[{condition}] benign_turn_fpr", row["benign_turn_fpr"],
               thresholds["stress_benign_turn_fpr"], False, reasons, evidence, None, False)
    result = {
        "verdict": worst(r["level"] for r in reasons),
        "reasons": reasons,
        "metrics": metrics.to_dict(),
    }
    if counts is not None:
        result["evidence"] = evidence
    if stress_conditions is not None:
        result["stress"] = stress_conditions
    return result


def apply_regression(result: dict, comparison: dict) -> None:
    """Add a baseline comparison's findings to a detector's gate result."""
    result["regression"] = comparison
    if comparison["regressed"]:
        missed = comparison["newly_missed"]
        example = f", e.g. {', '.join(missed[:3])}" if missed else ""
        result["reasons"].append({
            "level": "BLOCK",
            "check": (f"regression vs baseline: {len(missed)} case(s) newly missed, "
                      f"{len(comparison['newly_caught'])} newly caught "
                      f"(McNemar p={comparison['mcnemar_p']:.2g}){example}")})
    if comparison["new_false_positives"]:
        result["reasons"].append({
            "level": "WARN",
            "check": (f"regression vs baseline: {len(comparison['new_false_positives'])} "
                      f"case(s) newly false-positive, e.g. {comparison['new_false_positives'][0]}")})
    result["verdict"] = worst(r["level"] for r in result["reasons"])


def load_baseline(path: Path, fingerprint: str) -> dict:
    baseline = json.loads(path.read_text(encoding="utf-8"))
    if baseline.get("fingerprint") != fingerprint:
        raise ValueError(f"{path.name} was produced on a different test set (fingerprint "
                         "mismatch); regenerate the baseline before comparing")
    return baseline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Readiness gate on measured benchmark metrics")
    parser.add_argument("--detector", nargs="+", required=True, choices=list_detectors())
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, help="Write the full JSON report here")
    parser.add_argument("--stress", action="store_true",
                        help="Also gate on every conversation stress condition")
    parser.add_argument("--require-power", action="store_true",
                        help="WARN on any rate check the suite is too small to decide")
    parser.add_argument("--baseline", type=Path,
                        help="Previous --output report; block on case-level regressions")
    args = parser.parse_args(argv)

    thresholds = load_thresholds(args.config)
    fingerprint = test_set_fingerprint()
    baseline = load_baseline(args.baseline, fingerprint) if args.baseline else None
    scenarios = get_all_scenarios()
    stress = run_stress(args.detector)["detectors"] if args.stress else {}
    detectors = {}
    for name in args.detector:
        with contextlib.redirect_stdout(io.StringIO()):
            results = run_benchmark(get_detector(name), scenarios)
        stress_conditions = stress[name]["conditions"] if args.stress else None
        result = evaluate(aggregate_metrics(results), thresholds, stress_conditions,
                          measured_counts(results), args.require_power)
        result["scenario_outcomes"] = scenario_outcomes(results, stress_conditions)
        if baseline is not None:
            if name not in baseline.get("detectors", {}):
                raise ValueError(f"{args.baseline.name} has no results for detector '{name}'")
            apply_regression(result, compare_to_baseline(
                result["scenario_outcomes"], baseline["detectors"][name]["scenario_outcomes"],
                thresholds["regression"]))
        detectors[name] = result

    verdict = worst(d["verdict"] for d in detectors.values())
    for name, result in detectors.items():
        print(f"{name}: {result['verdict']}")
        for reason in result["reasons"]:
            print(f"  {reason['level']}: {reason['check']}")
    print(f"overall: {verdict} (exit {EXIT_CODES[verdict]})")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        report = {"schema_version": REPORT_SCHEMA_VERSION, "fingerprint": fingerprint,
                  "scenario_count": len(scenarios), "stress": args.stress,
                  "thresholds": thresholds, "verdict": verdict, "detectors": detectors}
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return EXIT_CODES[verdict]


if __name__ == "__main__":
    sys.exit(main())
