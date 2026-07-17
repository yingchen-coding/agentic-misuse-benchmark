"""Inter-query vs single-query defense audit.

Anthropic's *Recommendations for Technical AI Safety Research Directions* (2025) asks for
adaptive defenses that "monitor sets of queries, rather than individual ones." This audit
quantifies exactly that gap on the benchmark's own multi-turn scenarios, with NO model retraining
--- it only changes how much conversational context each detector is allowed to see:

  single-query : each turn scored in isolation (history hidden). This is the deployed reality of
                 a stateless per-message safety classifier.
  inter-query  : each turn scored with the accumulating prior turns as context (the detector's
                 native trajectory mode).

For every detector we report, over the vulnerable scenarios:

  trace recall       : fraction of attacks caught at all (any attack turn flagged)
  query-level FPR    : fraction of benign turns flagged (investigator noise)
  detection latency  : turns between first catch and the terminal attack turn --- higher is
                       earlier warning, so a session monitor that fires before the payload turn
                       is strictly more useful than one that only fires on the payload itself

The claim is deliberately narrow: giving a monitor cross-turn context, with no other change,
recovers attacks that per-query screening structurally cannot see, and does so earlier.

Run:  python3 analysis/inter_query_defense.py
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from detectors import get_detector, list_detectors
from scenarios import get_all_scenarios
from scenarios.base import Scenario


@dataclass
class TraceOutcome:
    scenario_id: str
    category: str
    caught: bool
    first_catch_turn: int | None
    terminal_attack_turn: int | None
    lead_turns: int | None  # terminal - first_catch; >0 means fired before the payload
    benign_flags: int
    benign_total: int


def _single_query_detections(detector, scenario: Scenario) -> list[bool]:
    """Score every turn with NO history --- the stateless per-message setting."""
    return [detector.detect_turn(turn, []).detected for turn in scenario.turns]


def _inter_query_detections(detector, scenario: Scenario) -> list[bool]:
    """Score every turn with the accumulating conversation as context."""
    return [r.detected for r in detector.detect_trajectory(scenario.turns)]


def _evaluate(detector, scenario: Scenario, detections: list[bool]) -> TraceOutcome:
    attack_turns = scenario.attack_turns
    caught_turns = [i for i in attack_turns if i < len(detections) and detections[i]]
    first_catch = min(caught_turns) if caught_turns else None
    terminal = max(attack_turns) if attack_turns else None
    lead = (terminal - first_catch) if (first_catch is not None and terminal is not None) else None

    benign_turns = [i for i in range(len(scenario.turns)) if i not in attack_turns]
    benign_flags = sum(1 for i in benign_turns if i < len(detections) and detections[i])

    return TraceOutcome(
        scenario_id=scenario.id,
        category=scenario.category.value,
        caught=bool(caught_turns),
        first_catch_turn=first_catch,
        terminal_attack_turn=terminal,
        lead_turns=lead,
        benign_flags=benign_flags,
        benign_total=len(benign_turns),
    )


def _summarize(outcomes: list[TraceOutcome]) -> dict:
    n = len(outcomes)
    caught = [o for o in outcomes if o.caught]
    benign_flags = sum(o.benign_flags for o in outcomes)
    benign_total = sum(o.benign_total for o in outcomes)
    leads = [o.lead_turns for o in caught if o.lead_turns is not None]
    early = [x for x in leads if x > 0]
    return {
        "trace_recall": round(len(caught) / n, 3) if n else 0.0,
        "query_fpr": round(benign_flags / benign_total, 3) if benign_total else 0.0,
        "avg_lead_turns": round(sum(leads) / len(leads), 2) if leads else 0.0,
        "share_early_warning": round(len(early) / len(caught), 3) if caught else 0.0,
        "caught": len(caught),
        "total": n,
    }


def run(as_json: bool = False) -> dict:
    scenarios = [s for s in get_all_scenarios() if s.attack_turns]
    report: dict = {"scenario_count": len(scenarios), "detectors": {}}

    for name in list_detectors():
        detector = get_detector(name)
        single = [_evaluate(detector, s, _single_query_detections(detector, s)) for s in scenarios]
        inter = [_evaluate(detector, s, _inter_query_detections(detector, s)) for s in scenarios]
        report["detectors"][name] = {
            "single_query": _summarize(single),
            "inter_query": _summarize(inter),
        }

    if as_json:
        print(json.dumps(report, indent=2))
        return report

    print(f"Inter-query vs single-query defense audit ({report['scenario_count']} vulnerable "
          f"scenarios)\n")
    header = (f"{'detector':12s} {'mode':13s} {'recall':>7s} {'query-FPR':>10s} "
              f"{'lead(turns)':>12s} {'early-warn':>11s}")
    print(header)
    print("-" * len(header))
    for name, modes in report["detectors"].items():
        for mode_key, label in (("single_query", "single-query"), ("inter_query", "inter-query")):
            m = modes[mode_key]
            print(f"{name:12s} {label:13s} {m['trace_recall']:7.2f} {m['query_fpr']:10.2f} "
                  f"{m['avg_lead_turns']:12.2f} {m['share_early_warning']:11.2f}")
        print()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()
    run(as_json=args.json)
