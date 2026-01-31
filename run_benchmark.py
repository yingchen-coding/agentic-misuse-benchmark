#!/usr/bin/env python3
"""
Agentic Misuse Benchmark - Main Entry Point

Runs misuse detection scenarios against specified detectors
and generates evaluation metrics.

Usage:
    python run_benchmark.py --detector rules
    python run_benchmark.py --detector classifier --category prompt_injection
    python run_benchmark.py --compare rules,classifier
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from scenarios import (
    get_all_scenarios,
    get_scenarios_by_category,
    Scenario,
    ScenarioResult,
    MisuseCategory
)
from detectors import get_detector, list_detectors, BaseDetector
from metrics import (
    aggregate_metrics,
    compare_detectors,
    compute_policy_erosion,
    compute_intent_drift,
    BenchmarkMetrics
)


def run_scenario(
    scenario: Scenario,
    detector: BaseDetector
) -> ScenarioResult:
    """Run a single scenario through a detector."""
    # Run detector on trajectory
    results = detector.detect_trajectory(scenario.turns)

    # Extract per-turn detection decisions
    detections = [r.detected for r in results]
    scores = [r.confidence for r in results]

    # Determine if attack was detected
    # Attack detected = any attack turn was flagged
    attack_detected = False
    detection_turn = None
    for turn_idx in scenario.attack_turns:
        if turn_idx < len(detections) and detections[turn_idx]:
            attack_detected = True
            if detection_turn is None:
                detection_turn = turn_idx

    # Check for false positives (detection on non-attack turns)
    false_positive = False
    non_attack_turns = [i for i in range(len(scenario.turns)) if i not in scenario.attack_turns]
    for turn_idx in non_attack_turns:
        if turn_idx < len(detections) and detections[turn_idx]:
            false_positive = True
            break

    # Compute trajectory metrics
    erosion = compute_policy_erosion(scenario, detections)
    drift = compute_intent_drift(scenario, scores)

    return ScenarioResult(
        scenario_id=scenario.id,
        category=scenario.category.value,
        difficulty=scenario.difficulty.value,
        detected=attack_detected,
        detection_turn=detection_turn,
        false_positive=false_positive,
        policy_erosion_score=erosion,
        intent_drift_score=drift,
        detector_name=detector.name,
        raw_scores=scores
    )


def run_benchmark(
    detector: BaseDetector,
    scenarios: list[Scenario],
    verbose: bool = False
) -> list[ScenarioResult]:
    """Run full benchmark with specified detector."""
    results = []

    print(f"\n{'='*60}")
    print(f"Running benchmark: {detector.name}")
    print(f"Scenarios: {len(scenarios)}")
    print(f"{'='*60}\n")

    for i, scenario in enumerate(scenarios, 1):
        if verbose:
            print(f"[{i}/{len(scenarios)}] {scenario.id}: {scenario.category.value}")

        result = run_scenario(scenario, detector)
        results.append(result)

        if verbose:
            status = "DETECTED" if result.detected else "MISSED"
            fp = " (FP)" if result.false_positive else ""
            print(f"  Result: {status}{fp}")
            print(f"  Erosion: {result.policy_erosion_score:.2f}, Drift: {result.intent_drift_score:.2f}")

    return results


def save_results(
    results: list[ScenarioResult],
    output_path: Path
) -> None:
    """Save results to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'scenario_id', 'category', 'difficulty', 'detector_name',
            'detected', 'detection_turn', 'false_positive',
            'policy_erosion_score', 'intent_drift_score'
        ])
        writer.writeheader()
        for r in results:
            writer.writerow(r.to_dict())

    print(f"\nResults saved to: {output_path}")


def print_summary(metrics: BenchmarkMetrics, detector_name: str) -> None:
    """Print benchmark summary."""
    print(f"\n{'='*60}")
    print(f"SUMMARY: {detector_name}")
    print(f"{'='*60}")
    print(f"Total scenarios: {metrics.total_scenarios}")
    print(f"Detection rate:  {metrics.detection_rate*100:.1f}%")
    print(f"False positive:  {metrics.false_positive_rate*100:.1f}%")
    print(f"Avg erosion:     {metrics.avg_policy_erosion:.3f}")
    print(f"Avg drift:       {metrics.avg_intent_drift:.3f}")

    print(f"\nPer-category detection rates:")
    for cat, rate in metrics.category_detection_rates.items():
        print(f"  {cat}: {rate*100:.1f}%")


def print_comparison(comparison: dict[str, BenchmarkMetrics]) -> None:
    """Print detector comparison."""
    print(f"\n{'='*60}")
    print("DETECTOR COMPARISON")
    print(f"{'='*60}")

    # Header
    detectors = list(comparison.keys())
    print(f"{'Metric':<25}", end="")
    for d in detectors:
        print(f"{d:<15}", end="")
    print()
    print("-" * (25 + 15 * len(detectors)))

    # Rows
    print(f"{'Detection Rate':<25}", end="")
    for d in detectors:
        print(f"{comparison[d].detection_rate*100:.1f}%{'':<10}", end="")
    print()

    print(f"{'False Positive Rate':<25}", end="")
    for d in detectors:
        print(f"{comparison[d].false_positive_rate*100:.1f}%{'':<10}", end="")
    print()

    print(f"{'Avg Policy Erosion':<25}", end="")
    for d in detectors:
        print(f"{comparison[d].avg_policy_erosion:.3f}{'':<10}", end="")
    print()

    print(f"{'Avg Intent Drift':<25}", end="")
    for d in detectors:
        print(f"{comparison[d].avg_intent_drift:.3f}{'':<10}", end="")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Run agentic misuse detection benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--detector", "-d",
        choices=list_detectors(),
        help="Detector to evaluate"
    )
    parser.add_argument(
        "--compare",
        help="Compare multiple detectors (comma-separated)"
    )
    parser.add_argument(
        "--category", "-c",
        choices=[c.value for c in MisuseCategory],
        help="Filter scenarios by category"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("results/benchmark_results.csv"),
        help="Output file for results"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="List all available scenarios"
    )
    parser.add_argument(
        "--list-detectors",
        action="store_true",
        help="List all available detectors"
    )

    args = parser.parse_args()

    # Handle info commands
    if args.list_scenarios:
        scenarios = get_all_scenarios()
        print(f"Available scenarios ({len(scenarios)}):")
        for s in scenarios:
            print(f"  {s.id}: {s.category.value} ({s.difficulty.value})")
        return

    if args.list_detectors:
        print("Available detectors:")
        for name in list_detectors():
            detector = get_detector(name)
            print(f"  {name}: {detector.description}")
        return

    # Get scenarios
    if args.category:
        category = MisuseCategory(args.category)
        scenarios = get_scenarios_by_category(category)
    else:
        scenarios = get_all_scenarios()

    if not scenarios:
        print("No scenarios found.")
        return

    # Run benchmark
    if args.compare:
        # Multi-detector comparison
        detector_names = [d.strip() for d in args.compare.split(",")]
        all_results = {}

        for name in detector_names:
            detector = get_detector(name)
            results = run_benchmark(detector, scenarios, args.verbose)
            all_results[name] = results

        # Compute and print comparison
        comparison = compare_detectors({
            name: results for name, results in all_results.items()
        })
        print_comparison(comparison)

        # Save combined results
        for name, results in all_results.items():
            output = args.output.parent / f"{name}_{args.output.name}"
            save_results(results, output)

    elif args.detector:
        # Single detector
        detector = get_detector(args.detector)
        results = run_benchmark(detector, scenarios, args.verbose)

        # Compute and print metrics
        metrics = aggregate_metrics(results)
        print_summary(metrics, detector.name)

        # Save results
        save_results(results, args.output)

    else:
        parser.error("Either --detector or --compare required")


if __name__ == "__main__":
    main()
