"""Deeper audit for inter-query misuse defense.

This is an evidence companion to ``analysis/inter_query_defense.py``. It keeps the same
training-free setting but adds:

* paired single-query vs inter-query significance tests;
* bootstrap confidence intervals over scenario-level recall and query-level false-positive rate;
* per-family breakdowns;
* history-window ablations;
* benign-only hard-negative traces built from the benchmark's non-attack turns.

Run:
    python3 analysis/inter_query_deep_audit.py
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.inter_query_defense import (  # noqa: E402
    TraceOutcome,
    _evaluate,
    _inter_query_detections,
    _single_query_detections,
    _summarize,
)
from detectors import get_detector, list_detectors  # noqa: E402
from scenarios import get_all_scenarios  # noqa: E402
from scenarios.base import Scenario, Turn  # noqa: E402


RESULTS_DIR = Path("results")
JSON_OUT = RESULTS_DIR / "inter_query_deep_audit.json"
MD_OUT = RESULTS_DIR / "inter_query_deep_audit.md"


@dataclass(frozen=True)
class PairedTest:
    single_only: int
    inter_only: int
    both: int
    neither: int
    exact_p_inter_better: float


def _binom_cdf(k: int, n: int, p: float = 0.5) -> float:
    return sum(math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(k + 1))


def _paired_test(single: list[TraceOutcome], inter: list[TraceOutcome]) -> PairedTest:
    single_by_id = {o.scenario_id: o for o in single}
    inter_by_id = {o.scenario_id: o for o in inter}
    single_only = inter_only = both = neither = 0
    for scenario_id, s in single_by_id.items():
        i = inter_by_id[scenario_id]
        if s.caught and i.caught:
            both += 1
        elif s.caught and not i.caught:
            single_only += 1
        elif i.caught and not s.caught:
            inter_only += 1
        else:
            neither += 1
    discordant = single_only + inter_only
    p_value = _binom_cdf(single_only, discordant) if discordant else 1.0
    return PairedTest(single_only, inter_only, both, neither, round(p_value, 6))


def _bootstrap_ci(outcomes: list[TraceOutcome], samples: int = 5000, seed: int = 17) -> dict:
    rng = random.Random(seed)
    recall_values: list[float] = []
    fpr_values: list[float] = []
    if not outcomes:
        return {"trace_recall": [0.0, 0.0], "query_fpr": [0.0, 0.0]}

    for _ in range(samples):
        draw = [rng.choice(outcomes) for _ in outcomes]
        summary = _summarize(draw)
        recall_values.append(summary["trace_recall"])
        fpr_values.append(summary["query_fpr"])

    def interval(values: list[float]) -> list[float]:
        values = sorted(values)
        lo = values[int(0.025 * (len(values) - 1))]
        hi = values[int(0.975 * (len(values) - 1))]
        return [round(lo, 3), round(hi, 3)]

    return {"trace_recall": interval(recall_values), "query_fpr": interval(fpr_values)}


def _by_category(outcomes: list[TraceOutcome]) -> dict:
    grouped: dict[str, list[TraceOutcome]] = defaultdict(list)
    for outcome in outcomes:
        grouped[outcome.category].append(outcome)
    return {category: _summarize(items) for category, items in sorted(grouped.items())}


def _windowed_detections(detector, scenario: Scenario, history_turns: int | None) -> list[bool]:
    detections: list[bool] = []
    history: list[Turn] = []
    for turn in scenario.turns:
        if history_turns is None:
            visible_history = history
        elif history_turns <= 0:
            visible_history = []
        else:
            visible_history = history[-history_turns:]
        detections.append(detector.detect_turn(turn, visible_history).detected)
        history.append(turn)
    return detections


def _history_window_ablation(detector_name: str, scenarios: list[Scenario]) -> dict:
    detector = get_detector(detector_name)
    windows: list[tuple[str, int | None]] = [("0", 0), ("1", 1), ("2", 2), ("3", 3), ("full", None)]
    report: dict = {}
    for label, window in windows:
        outcomes = [_evaluate(detector, s, _windowed_detections(detector, s, window)) for s in scenarios]
        report[label] = _summarize(outcomes)
    return report


def _benign_only_scenarios(scenarios: list[Scenario]) -> list[Scenario]:
    benign: list[Scenario] = []
    for scenario in scenarios:
        turns = [Turn(t.role, t.content, is_attack=False, metadata=dict(t.metadata)) for t in scenario.turns if not t.is_attack]
        if not any(t.role == "user" for t in turns):
            continue
        benign.append(
            Scenario(
                id=f"{scenario.id}::benign_only",
                category=scenario.category,
                difficulty=scenario.difficulty,
                user_goal=scenario.user_goal,
                latent_misuse_goal="none",
                turns=turns,
                expected_failure_pattern="hard negative: no attack turns retained",
                tags=[*scenario.tags, "hard_negative"],
            )
        )
    return benign


def _benign_trace_fpr(detector_name: str, scenarios: list[Scenario]) -> dict:
    detector = get_detector(detector_name)
    benign = _benign_only_scenarios(scenarios)
    mode_totals: dict[str, dict[str, int]] = {
        "single_query": {"flags": 0, "turns": 0, "traces_flagged": 0},
        "inter_query": {"flags": 0, "turns": 0, "traces_flagged": 0},
    }
    for scenario in benign:
        for mode, detections in (
            ("single_query", _single_query_detections(detector, scenario)),
            ("inter_query", _inter_query_detections(detector, scenario)),
        ):
            user_indices = [i for i, turn in enumerate(scenario.turns) if turn.role == "user"]
            flags = sum(1 for i in user_indices if detections[i])
            mode_totals[mode]["flags"] += flags
            mode_totals[mode]["turns"] += len(user_indices)
            mode_totals[mode]["traces_flagged"] += 1 if flags else 0

    return {
        mode: {
            "query_fpr": round(v["flags"] / v["turns"], 3) if v["turns"] else 0.0,
            "trace_flag_rate": round(v["traces_flagged"] / len(benign), 3) if benign else 0.0,
            "flags": v["flags"],
            "turns": v["turns"],
            "traces": len(benign),
        }
        for mode, v in mode_totals.items()
    }


def run() -> dict:
    scenarios = [s for s in get_all_scenarios() if s.attack_turns]
    report: dict = {"scenario_count": len(scenarios), "detectors": {}}
    for name in list_detectors():
        detector = get_detector(name)
        single = [_evaluate(detector, s, _single_query_detections(detector, s)) for s in scenarios]
        inter = [_evaluate(detector, s, _inter_query_detections(detector, s)) for s in scenarios]
        report["detectors"][name] = {
            "single_query": _summarize(single),
            "inter_query": _summarize(inter),
            "single_query_ci": _bootstrap_ci(single),
            "inter_query_ci": _bootstrap_ci(inter),
            "paired_test": asdict(_paired_test(single, inter)),
            "per_category": {
                "single_query": _by_category(single),
                "inter_query": _by_category(inter),
            },
            "history_window_ablation": _history_window_ablation(name, scenarios),
            "benign_only_hard_negatives": _benign_trace_fpr(name, scenarios),
        }
    return report


def _write_markdown(report: dict) -> None:
    lines = [
        "# Inter-Query Deep Audit",
        "",
        f"Scenarios: {report['scenario_count']} vulnerable traces.",
        "",
        "## Headline",
        "",
        "| Detector | Single recall | Inter recall | Recall CI (inter) | Query FPR (inter) | Inter-only wins | Single-only wins | p(inter better) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for detector, data in report["detectors"].items():
        paired = data["paired_test"]
        lines.append(
            f"| {detector} | {data['single_query']['trace_recall']:.3f} | "
            f"{data['inter_query']['trace_recall']:.3f} | "
            f"{data['inter_query_ci']['trace_recall']} | "
            f"{data['inter_query']['query_fpr']:.3f} | "
            f"{paired['inter_only']} | {paired['single_only']} | "
            f"{paired['exact_p_inter_better']:.6f} |"
        )

    lines += ["", "## History Window Ablation", ""]
    for detector, data in report["detectors"].items():
        lines += [
            f"### {detector}",
            "",
            "| Visible history turns | Trace recall | Query FPR | Mean lead |",
            "|---:|---:|---:|---:|",
        ]
        for window, metrics in data["history_window_ablation"].items():
            lines.append(
                f"| {window} | {metrics['trace_recall']:.3f} | "
                f"{metrics['query_fpr']:.3f} | {metrics['avg_lead_turns']:.2f} |"
            )
        lines.append("")

    lines += ["## Benign-Only Hard Negatives", ""]
    lines += [
        "| Detector | Mode | Query FPR | Trace flag rate | Flags / turns |",
        "|---|---|---:|---:|---:|",
    ]
    for detector, data in report["detectors"].items():
        for mode, metrics in data["benign_only_hard_negatives"].items():
            lines.append(
                f"| {detector} | {mode} | {metrics['query_fpr']:.3f} | "
                f"{metrics['trace_flag_rate']:.3f} | {metrics['flags']} / {metrics['turns']} |"
            )

    lines += [
        "",
        "## Interpretation",
        "",
        "The classifier result is the strongest evidence: the same detector gains recall when it can see "
        "cross-turn context, while query-level false positives stay flat in the headline comparison. "
        "The rules detector is a negative control: it barely changes because it is surface-pattern "
        "driven and not designed to use trajectory state. The intent tracker is a mechanism probe: "
        "it is mostly useless with no history and only becomes meaningful as visible history grows.",
        "",
        "The hard-negative section is deliberately conservative: it strips attack turns and asks whether "
        "the detector flags the remaining benign-looking context. This is not a deployment FPR estimate, "
        "but it is a better stress test than counting only isolated benign turns inside vulnerable traces.",
    ]
    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print JSON to stdout")
    args = parser.parse_args()
    RESULTS_DIR.mkdir(exist_ok=True)
    report = run()
    JSON_OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown(report)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Wrote {JSON_OUT} and {MD_OUT}")


if __name__ == "__main__":
    main()
