"""
Visualization tools for trajectory-level misuse analysis.

Generates plots showing:
- Policy erosion curves across turns
- Detection heatmaps by category and difficulty
- Detector comparison charts
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Optional

from scenarios.base import Scenario, ScenarioResult
from detectors.base import DetectionResult


def plot_erosion_curve(
    scenarios: list[Scenario],
    results_by_scenario: dict[str, list[DetectionResult]],
    output_path: Optional[Path] = None,
    title: str = "Policy Erosion Over Trajectory"
) -> None:
    """
    Plot policy erosion curves showing how detection confidence changes over turns.

    X-axis: Turn number
    Y-axis: Detection confidence (0-1)
    Each line: One scenario
    """
    plt.figure(figsize=(12, 6))

    colors = plt.cm.viridis(np.linspace(0, 0.9, len(scenarios)))

    for idx, scenario in enumerate(scenarios):
        if scenario.id not in results_by_scenario:
            continue

        results = results_by_scenario[scenario.id]
        turns = list(range(1, len(results) + 1))
        confidences = [r.confidence for r in results]

        # Mark attack turns
        attack_starts = min(scenario.attack_turns) + 1 if scenario.attack_turns else None

        plt.plot(turns, confidences,
                 color=colors[idx],
                 linewidth=2,
                 marker='o',
                 label=f"{scenario.id}")

        # Add vertical line at attack start
        if attack_starts:
            plt.axvline(x=attack_starts, color=colors[idx],
                       linestyle='--', alpha=0.3)

    plt.xlabel('Turn Number', fontsize=12)
    plt.ylabel('Detection Confidence', fontsize=12)
    plt.title(title, fontsize=14, fontweight='bold')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(True, alpha=0.3)
    plt.ylim(-0.05, 1.05)

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Saved: {output_path}")
    else:
        plt.show()

    plt.close()


def plot_detection_heatmap(
    results: list[ScenarioResult],
    output_path: Optional[Path] = None,
    title: str = "Detection Results by Scenario"
) -> None:
    """
    Plot heatmap showing detection success/failure across scenarios.

    Rows: Scenarios
    Columns: Metrics (detected, false_positive, erosion, drift)
    """
    if not results:
        print("No results to plot")
        return

    # Prepare data
    scenario_ids = [r.scenario_id for r in results]
    metrics = ['Detected', 'False Positive', 'Policy Erosion', 'Intent Drift']

    data = np.array([
        [r.detected, r.false_positive, r.policy_erosion_score, r.intent_drift_score]
        for r in results
    ])

    fig, ax = plt.subplots(figsize=(10, max(6, len(results) * 0.4)))

    # Create heatmap
    im = ax.imshow(data, cmap='RdYlGn_r', aspect='auto', vmin=0, vmax=1)

    # Labels
    ax.set_xticks(range(len(metrics)))
    ax.set_xticklabels(metrics, fontsize=10)
    ax.set_yticks(range(len(scenario_ids)))
    ax.set_yticklabels(scenario_ids, fontsize=9)

    # Add text annotations
    for i in range(len(scenario_ids)):
        for j in range(len(metrics)):
            val = data[i, j]
            text_color = 'white' if val > 0.5 else 'black'
            if j < 2:  # Boolean values
                text = '✓' if val else '✗'
            else:  # Float values
                text = f'{val:.2f}'
            ax.text(j, i, text, ha='center', va='center',
                   color=text_color, fontsize=9)

    plt.colorbar(im, ax=ax, shrink=0.8)
    plt.title(title, fontsize=14, fontweight='bold')
    plt.xlabel('Metric', fontsize=12)
    plt.ylabel('Scenario', fontsize=12)

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Saved: {output_path}")
    else:
        plt.show()

    plt.close()


def plot_category_comparison(
    results: list[ScenarioResult],
    output_path: Optional[Path] = None,
    title: str = "Detection Rate by Category"
) -> None:
    """
    Bar chart comparing detection rates across misuse categories.
    """
    if not results:
        print("No results to plot")
        return

    # Group by category
    categories = {}
    for r in results:
        if r.category not in categories:
            categories[r.category] = {'detected': 0, 'total': 0, 'erosion': [], 'drift': []}
        categories[r.category]['total'] += 1
        if r.detected:
            categories[r.category]['detected'] += 1
        categories[r.category]['erosion'].append(r.policy_erosion_score)
        categories[r.category]['drift'].append(r.intent_drift_score)

    # Calculate rates
    cat_names = list(categories.keys())
    detection_rates = [categories[c]['detected'] / categories[c]['total'] for c in cat_names]
    avg_erosion = [np.mean(categories[c]['erosion']) for c in cat_names]
    avg_drift = [np.mean(categories[c]['drift']) for c in cat_names]

    x = np.arange(len(cat_names))
    width = 0.25

    fig, ax = plt.subplots(figsize=(12, 6))

    bars1 = ax.bar(x - width, detection_rates, width, label='Detection Rate', color='#2ecc71')
    bars2 = ax.bar(x, avg_erosion, width, label='Avg Policy Erosion', color='#e74c3c')
    bars3 = ax.bar(x + width, avg_drift, width, label='Avg Intent Drift', color='#3498db')

    ax.set_xlabel('Category', fontsize=12)
    ax.set_ylabel('Rate / Score', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([c.replace('_', '\n') for c in cat_names], fontsize=10)
    ax.legend()
    ax.set_ylim(0, 1.1)

    # Add value labels
    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.2f}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3), textcoords="offset points",
                       ha='center', va='bottom', fontsize=8)

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Saved: {output_path}")
    else:
        plt.show()

    plt.close()


def plot_trajectory_drift(
    scenario: Scenario,
    detection_results: list[DetectionResult],
    output_path: Optional[Path] = None
) -> None:
    """
    Detailed trajectory plot for a single scenario showing:
    - Confidence over turns
    - Attack turn markers
    - Cumulative drift
    """
    turns = list(range(1, len(detection_results) + 1))
    confidences = [r.confidence for r in detection_results]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    # Top: Confidence over turns
    ax1.plot(turns, confidences, 'b-o', linewidth=2, markersize=8)
    ax1.fill_between(turns, confidences, alpha=0.3)

    # Mark attack turns
    for turn_idx in scenario.attack_turns:
        if turn_idx < len(turns):
            ax1.axvline(x=turn_idx + 1, color='red', linestyle='--', alpha=0.5)
            ax1.scatter([turn_idx + 1], [confidences[turn_idx]],
                       color='red', s=100, zorder=5, marker='X')

    ax1.set_ylabel('Detection Confidence', fontsize=11)
    ax1.set_title(f'{scenario.id}: {scenario.category.value}', fontsize=12, fontweight='bold')
    ax1.set_ylim(-0.05, 1.05)
    ax1.grid(True, alpha=0.3)
    ax1.legend(['Confidence', 'Attack Turn'], loc='upper left')

    # Bottom: Cumulative drift
    cumulative = np.cumsum(confidences) / np.arange(1, len(confidences) + 1)
    ax2.plot(turns, cumulative, 'g-s', linewidth=2, markersize=6)
    ax2.fill_between(turns, cumulative, alpha=0.3, color='green')

    ax2.set_xlabel('Turn Number', fontsize=11)
    ax2.set_ylabel('Cumulative Avg Confidence', fontsize=11)
    ax2.set_ylim(-0.05, 1.05)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Saved: {output_path}")
    else:
        plt.show()

    plt.close()


def generate_report(
    results: list[ScenarioResult],
    output_dir: Path,
    detector_name: str = "detector"
) -> None:
    """
    Generate complete visual report with all plots.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Detection heatmap
    plot_detection_heatmap(
        results,
        output_dir / f"{detector_name}_heatmap.png",
        f"Detection Results: {detector_name}"
    )

    # Category comparison
    plot_category_comparison(
        results,
        output_dir / f"{detector_name}_categories.png",
        f"Category Comparison: {detector_name}"
    )

    print(f"\nReport generated in: {output_dir}")
