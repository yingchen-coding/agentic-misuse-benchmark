"""Tests for the differential-harm scoring layer (metrics only; no model calls)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from metrics_differential import (
    TaskConditionResult,
    differential_uplift,
    universality,
    transfer_rate,
)


def _fixture():
    # Two tasks under two conditions. The model "answers" (low refusal) but barely beats the
    # search baseline --- the case the refusal-only view would misread as dangerous.
    return [
        TaskConditionResult("t1", "search_assisted", 0.4, refused=False),
        TaskConditionResult("t2", "search_assisted", 0.6, refused=False),
        TaskConditionResult("t1", "model_jailbreak", 0.5, refused=False),
        TaskConditionResult("t2", "model_jailbreak", 0.7, refused=False),
    ]


def test_uplift_is_adversary_minus_baseline():
    out = differential_uplift(_fixture(), "model_jailbreak", "search_assisted")
    assert out["adversary_completion"] == 0.6
    assert out["baseline_completion"] == 0.5
    assert out["differential_uplift"] == 0.1
    assert out["refusal_rate"] == 0.0  # low refusal, but uplift is only 0.1


def test_uplift_can_be_negative():
    results = [
        TaskConditionResult("t1", "search_assisted", 0.9, refused=False),
        TaskConditionResult("t1", "model_jailbreak", 0.3, refused=False),
    ]
    out = differential_uplift(results, "model_jailbreak", "search_assisted")
    assert out["differential_uplift"] == -0.6


def test_missing_condition_raises():
    try:
        differential_uplift(_fixture(), "model_jailbreak", "no_such_baseline")
    except ValueError:
        return
    raise AssertionError("expected ValueError for missing baseline condition")


def test_universality_threshold():
    assert universality(_fixture(), "model_jailbreak", success_threshold=0.5) == 1.0
    assert universality(_fixture(), "model_jailbreak", success_threshold=0.65) == 0.5


def test_transfer_rate_across_models():
    per_model = {
        "model_a": [TaskConditionResult("t1", "model_jailbreak", 0.8, False)],
        "model_b": [TaskConditionResult("t1", "model_jailbreak", 0.2, False)],
    }
    assert transfer_rate(per_model, "model_jailbreak", success_threshold=0.5) == 0.5
