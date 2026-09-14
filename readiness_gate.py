#!/usr/bin/env python3
"""Readiness gate on measured benchmark metrics.

Runs each requested detector on the labeled scenarios, checks the measured metrics against
config/readiness_gate.yaml, and exits with the worst verdict so CI can act on it:
    0 = OK, 1 = WARN, 2 = BLOCK

With --stress it also runs analysis/conversation_stress.py and checks every stress condition
(longer conversations, topic shifts, tool relay) for detection drop and benign-turn false positives.

Run:  python3 readiness_gate.py --detector rules
      python3 readiness_gate.py --detector rules classifier intent --output report.json
      python3 readiness_gate.py --detector rules --stress
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
from metrics import BenchmarkMetrics, aggregate_metrics
from run_benchmark import run_benchmark
from scenarios import get_all_scenarios

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = REPO_ROOT / "config" / "readiness_gate.yaml"
VERDICTS = ("OK", "WARN", "BLOCK")
EXIT_CODES = {"OK": 0, "WARN": 1, "BLOCK": 2}
HIGHER_IS_BETTER = ("detection_rate", "category_detection_rate", "early_warning_rate")
LOWER_IS_BETTER = ("false_positive_rate", "stress_detection_drop", "stress_benign_turn_fpr")


def load_thresholds(path: Path) -> dict:
    thresholds = yaml.safe_load(path.read_text(encoding="utf-8"))
    for check in HIGHER_IS_BETTER + LOWER_IS_BETTER:
        if check not in thresholds:
            raise ValueError(f"{path.name}: missing threshold '{check}'")
        rule = thresholds[check]
        if not {"warn", "block"} <= set(rule):
            raise ValueError(f"{path.name}: '{check}' needs both warn and block")
        if check in HIGHER_IS_BETTER and rule["block"] > rule["warn"]:
            raise ValueError(f"{path.name}: '{check}' block must not exceed warn")
        if check in LOWER_IS_BETTER and rule["block"] < rule["warn"]:
            raise ValueError(f"{path.name}: '{check}' block must not be below warn")
    return thresholds


def _at_least(name: str, value: float, rule: dict, reasons: list[dict]) -> None:
    if value < rule["block"]:
        reasons.append({"level": "BLOCK", "check": f"{name} {value:.3f} < {rule['block']}"})
    elif value < rule["warn"]:
        reasons.append({"level": "WARN", "check": f"{name} {value:.3f} < {rule['warn']}"})


def _at_most(name: str, value: float, rule: dict, reasons: list[dict]) -> None:
    if value > rule["block"]:
        reasons.append({"level": "BLOCK", "check": f"{name} {value:.3f} > {rule['block']}"})
    elif value > rule["warn"]:
        reasons.append({"level": "WARN", "check": f"{name} {value:.3f} > {rule['warn']}"})


def worst(verdicts) -> str:
    return max(verdicts, key=VERDICTS.index, default="OK")


def evaluate(metrics: BenchmarkMetrics, thresholds: dict,
             stress_conditions: dict | None = None) -> dict:
    reasons: list[dict] = []
    _at_least("detection_rate", metrics.detection_rate, thresholds["detection_rate"], reasons)
    for category, rate in sorted(metrics.category_detection_rates.items()):
        _at_least(f"category_detection_rate[{category}]", rate,
                  thresholds["category_detection_rate"], reasons)
    _at_most("false_positive_rate", metrics.false_positive_rate,
             thresholds["false_positive_rate"], reasons)
    _at_least("early_warning_rate", metrics.early_warning_rate,
              thresholds["early_warning_rate"], reasons)
    for condition, row in (stress_conditions or {}).items():
        if condition == "baseline":
            continue
        _at_most(f"stress[{condition}] detection_drop", row["detection_drop"],
                 thresholds["stress_detection_drop"], reasons)
        _at_most(f"stress[{condition}] benign_turn_fpr", row["benign_turn_fpr"],
                 thresholds["stress_benign_turn_fpr"], reasons)
    result = {
        "verdict": worst(r["level"] for r in reasons),
        "reasons": reasons,
        "metrics": metrics.to_dict(),
    }
    if stress_conditions is not None:
        result["stress"] = stress_conditions
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Readiness gate on measured benchmark metrics")
    parser.add_argument("--detector", nargs="+", required=True, choices=list_detectors())
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, help="Write the full JSON report here")
    parser.add_argument("--stress", action="store_true",
                        help="Also gate on every conversation stress condition")
    args = parser.parse_args(argv)

    thresholds = load_thresholds(args.config)
    scenarios = get_all_scenarios()
    stress = run_stress(args.detector)["detectors"] if args.stress else {}
    detectors = {}
    for name in args.detector:
        with contextlib.redirect_stdout(io.StringIO()):
            results = run_benchmark(get_detector(name), scenarios)
        stress_conditions = stress[name]["conditions"] if args.stress else None
        detectors[name] = evaluate(aggregate_metrics(results), thresholds, stress_conditions)

    verdict = worst(d["verdict"] for d in detectors.values())
    for name, result in detectors.items():
        print(f"{name}: {result['verdict']}")
        for reason in result["reasons"]:
            print(f"  {reason['level']}: {reason['check']}")
    print(f"overall: {verdict} (exit {EXIT_CODES[verdict]})")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        report = {"scenario_count": len(scenarios), "thresholds": thresholds,
                  "verdict": verdict, "detectors": detectors}
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return EXIT_CODES[verdict]


if __name__ == "__main__":
    sys.exit(main())
