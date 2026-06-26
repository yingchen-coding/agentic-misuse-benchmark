import csv
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from detectors import get_detector, list_detectors
from metrics import aggregate_metrics
from run_benchmark import run_benchmark
from scenarios import MisuseCategory, get_all_scenarios, get_scenarios_by_category


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "run_benchmark.py", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def test_detector_registry_matches_cli_names() -> None:
    assert list_detectors() == ["rules", "classifier", "intent"]
    for name in list_detectors():
        assert get_detector(name).name


def test_scenarios_cover_every_category() -> None:
    scenarios = get_all_scenarios()
    assert len(scenarios) == 25
    for category in MisuseCategory:
        assert get_scenarios_by_category(category)


def test_benchmark_produces_metrics_for_rules_detector() -> None:
    scenarios = get_all_scenarios()
    results = run_benchmark(get_detector("rules"), scenarios)
    metrics = aggregate_metrics(results)

    assert metrics.total_scenarios == len(scenarios)
    assert metrics.detection_rate >= 0.95
    assert metrics.false_positive_rate <= 0.05
    assert set(metrics.category_detection_rates)
    for rate in metrics.category_detection_rates.values():
        assert rate >= 0.90


def test_cli_lists_detectors() -> None:
    result = run_cli("--list-detectors")
    assert "rules:" in result.stdout
    assert "classifier:" in result.stdout
    assert "intent:" in result.stdout


def test_cli_writes_csv_output(tmp_path: Path) -> None:
    output_path = tmp_path / "rules.csv"
    result = run_cli("--detector", "rules", "--output", str(output_path))

    assert "SUMMARY: rules" in result.stdout
    with output_path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 25
    assert {"scenario_id", "category", "detector_name", "detected"} <= set(rows[0])


def test_reproduction_script_runs_to_temp_output(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["OUTPUT_DIR"] = str(tmp_path)
    result = subprocess.run(
        ["bash", "scripts/reproduce_key_results.sh"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )

    assert "Reproduction complete" in result.stdout
    assert (tmp_path / "rules.csv").exists()
    assert (tmp_path / "classifier.csv").exists()
    assert (tmp_path / "intent.csv").exists()
    assert (tmp_path / "scenarios.txt").exists()
