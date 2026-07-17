import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.inter_query_deep_audit import run


def test_deep_audit_contains_expected_sections():
    report = run()
    assert report["scenario_count"] == 25
    classifier = report["detectors"]["classifier"]
    assert classifier["single_query"]["trace_recall"] == 0.64
    assert classifier["inter_query"]["trace_recall"] == 0.84
    assert classifier["paired_test"]["inter_only"] == 5
    assert classifier["paired_test"]["single_only"] == 0
    assert "benign_only_hard_negatives" in classifier


def test_deep_audit_history_window_ablation_is_monotone_for_classifier():
    report = run()
    ablation = report["detectors"]["classifier"]["history_window_ablation"]
    assert ablation["0"]["trace_recall"] == 0.64
    assert ablation["2"]["trace_recall"] >= ablation["0"]["trace_recall"]
    assert ablation["full"]["query_fpr"] == ablation["0"]["query_fpr"]
