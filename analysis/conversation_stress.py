"""Stress protocol: detector performance under longer conversations, topic shifts, and tool relay.

Every perturbation is generated from the 25 labeled scenarios (scenarios/perturbations.py) and
keeps the original attack turns and labels, so each row is compared with the unperturbed baseline:
  extended_length : N benign exchanges inserted right before the first attack turn
  topic_shift     : a full 14-turn benign conversation on another topic comes first
  tool_relay      : each attack turn arrives as tool output fetched on a benign user request
Benign filler and prior topics are the user/assistant turns of analysis/hard_negatives/, so the
inserted turns are long, realistic, and topically adjacent to the attacks.

Run:  python3 analysis/conversation_stress.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.hard_negative_audit import load_traces  # noqa: E402
from detectors import get_detector, list_detectors  # noqa: E402
from evalstats import mcnemar_exact  # noqa: E402
from metrics import aggregate_metrics  # noqa: E402
from run_benchmark import run_scenario  # noqa: E402
from scenarios import Scenario, get_all_scenarios  # noqa: E402
from scenarios.base import Turn  # noqa: E402
from scenarios.perturbations import (  # noqa: E402
    extend_conversation,
    relay_through_tool,
    shift_topic,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "analysis" / "results" / "conversation_stress.json"
EXTENSION_LEVELS = (0, 4, 8, 16, 28)


def filler_turns(traces: dict[str, list[Turn]]) -> list[Turn]:
    return [turn for name in sorted(traces) for turn in traces[name]]


def build_conditions(scenarios: list[Scenario],
                     traces: dict[str, list[Turn]]) -> dict[str, list[Scenario]]:
    filler = filler_turns(traces)
    conditions = {"baseline": list(scenarios)}
    for n in EXTENSION_LEVELS[1:]:
        conditions[f"extended_length:{n}"] = [extend_conversation(s, filler, n) for s in scenarios]
    for name in sorted(traces):
        conditions[f"topic_shift:{name}"] = [shift_topic(s, traces[name], name) for s in scenarios]
    conditions["tool_relay"] = [relay_through_tool(s) for s in scenarios]
    return conditions


def benign_turn_fpr(detector, scenarios: list[Scenario]) -> float:
    """Share of benign non-assistant turns flagged. Scenario-level FPR saturates when one shared
    filler turn is flagged in every scenario; this counts each flagged turn once per occurrence
    against all benign turns, so a single bad filler turn stays a small number."""
    flagged = total = 0
    for scenario in scenarios:
        for turn, result in zip(scenario.turns, detector.detect_trajectory(scenario.turns)):
            if turn.role != "assistant" and not turn.is_attack:
                total += 1
                flagged += result.detected
    return flagged / total if total else 0.0


def measure(detector_name: str, scenarios: list[Scenario]) -> dict:
    detector = get_detector(detector_name)
    results = [run_scenario(s, detector) for s in scenarios]
    m = aggregate_metrics(results)
    return {
        "scenarios": len(scenarios),
        "avg_turns": round(sum(s.num_turns for s in scenarios) / len(scenarios), 1),
        "detection_rate": round(m.detection_rate, 3),
        "false_positive_rate": round(m.false_positive_rate, 3),
        "benign_turn_fpr": round(benign_turn_fpr(detector, scenarios), 3),
        "early_warning_rate": round(m.early_warning_rate, 3),
        "category_detection_rates": {k: round(v, 3)
                                     for k, v in sorted(m.category_detection_rates.items())},
        "detected_ids": sorted(_source_id(r.scenario_id) for r in results if r.detected),
        "false_positive_ids": sorted(_source_id(r.scenario_id) for r in results if r.false_positive),
    }


def _source_id(scenario_id: str) -> str:
    """The unperturbed scenario a perturbed one was generated from ("PI_01+tool_relay" -> "PI_01")."""
    return scenario_id.split("+", 1)[0]


def run(detectors: list[str]) -> dict:
    conditions = build_conditions(get_all_scenarios(), load_traces())
    report: dict = {"filler_source": "analysis/hard_negatives", "conditions": list(conditions),
                    "detectors": {}}
    for name in detectors:
        rows = {cond: measure(name, scenarios) for cond, scenarios in conditions.items()}
        base = rows["baseline"]
        for row in rows.values():
            row["detection_drop"] = round(base["detection_rate"] - row["detection_rate"], 3)
            row["fpr_increase"] = round(row["false_positive_rate"] - base["false_positive_rate"], 3)
            # Same scenarios before and after, so the change is tested pairwise.
            row["newly_missed"] = sorted(set(base["detected_ids"]) - set(row["detected_ids"]))
            row["newly_detected"] = sorted(set(row["detected_ids"]) - set(base["detected_ids"]))
            row["mcnemar_p"] = round(mcnemar_exact(len(row["newly_missed"]),
                                                   len(row["newly_detected"])), 10)
        worst = max((c for c in rows if c != "baseline"), key=lambda c: rows[c]["detection_drop"])
        if rows[worst]["detection_drop"] <= 0:
            worst = None
        report["detectors"][name] = {"conditions": rows, "worst_condition": worst}
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Conversation stress protocol")
    parser.add_argument("--detector", nargs="+", default=list_detectors(), choices=list_detectors())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = run(args.detector)
    for name, result in report["detectors"].items():
        worst = result["worst_condition"] or "no condition lowers detection"
        print(f"\n{name}  (worst: {worst})")
        print(f"  {'condition':<48}{'turns':>6}{'detect':>8}{'drop':>7}{'missed':>7}{'p':>9}"
              f"{'scenFPR':>8}{'turnFPR':>8}{'early':>7}")
        for cond, row in result["conditions"].items():
            print(f"  {cond:<48}{row['avg_turns']:>6}{row['detection_rate']:>8.2f}"
                  f"{row['detection_drop']:>7.2f}{len(row['newly_missed']):>7}"
                  f"{row['mcnemar_p']:>9.2g}{row['false_positive_rate']:>8.2f}"
                  f"{row['benign_turn_fpr']:>8.3f}{row['early_warning_rate']:>7.2f}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {args.output}")


if __name__ == "__main__":
    main()
