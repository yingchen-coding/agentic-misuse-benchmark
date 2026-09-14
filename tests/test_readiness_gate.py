import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from metrics import BenchmarkMetrics
from readiness_gate import DEFAULT_CONFIG, evaluate, load_thresholds

THRESHOLDS = load_thresholds(DEFAULT_CONFIG)


def _metrics(detection=1.0, fpr=0.0, categories=None, early=1.0):
    return BenchmarkMetrics(
        total_scenarios=25, detection_rate=detection, false_positive_rate=fpr,
        avg_policy_erosion=0.0, avg_intent_drift=0.0, early_warning_rate=early,
        category_detection_rates=categories or {"policy_erosion": 1.0},
        category_false_positives={},
    )


def _gate(*args):
    return subprocess.run([sys.executable, "readiness_gate.py", *args], cwd=REPO_ROOT,
                          text=True, capture_output=True)


def test_all_checks_passing_is_ok():
    result = evaluate(_metrics(), THRESHOLDS)
    assert result["verdict"] == "OK" and result["reasons"] == []


def test_detection_between_block_and_warn_is_warn():
    assert evaluate(_metrics(detection=0.85), THRESHOLDS)["verdict"] == "WARN"


def test_one_weak_category_blocks_even_with_strong_overall_detection():
    metrics = _metrics(detection=0.95, categories={"prompt_injection": 1.0, "policy_erosion": 0.5})
    result = evaluate(metrics, THRESHOLDS)
    assert result["verdict"] == "BLOCK"
    blocks = [r["check"] for r in result["reasons"] if r["level"] == "BLOCK"]
    assert blocks == ["category_detection_rate[policy_erosion] 0.500 < 0.6"]


def test_false_positive_rate_is_an_upper_bound():
    assert evaluate(_metrics(fpr=0.04), THRESHOLDS)["verdict"] == "WARN"
    assert evaluate(_metrics(fpr=0.06), THRESHOLDS)["verdict"] == "BLOCK"


def test_config_missing_a_check_fails_loudly(tmp_path):
    path = tmp_path / "gate.yaml"
    path.write_text("detection_rate: {warn: 0.9, block: 0.8}\n")
    with pytest.raises(ValueError, match="missing threshold"):
        load_thresholds(path)


def test_config_with_inverted_thresholds_fails_loudly(tmp_path):
    path = tmp_path / "gate.yaml"
    path.write_text(DEFAULT_CONFIG.read_text().replace("block: 0.80", "block: 0.95"))
    with pytest.raises(ValueError, match="block must not exceed warn"):
        load_thresholds(path)


def test_cli_rules_detector_passes_the_gate():
    result = _gate("--detector", "rules")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "overall: OK" in result.stdout


def test_cli_classifier_is_blocked_by_its_policy_erosion_category():
    result = _gate("--detector", "classifier")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "BLOCK: category_detection_rate[policy_erosion]" in result.stdout
