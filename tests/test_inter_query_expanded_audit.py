import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.inter_query_expanded_audit import run


def test_expanded_audit_uses_three_suites():
    report = run()
    assert report["suite_counts"] == {"original": 25, "metamorphic": 25, "adaptive": 25}
    assert report["combined_count"] == 75


def test_expanded_audit_preserves_classifier_context_gain():
    report = run()
    classifier = report["detectors"]["classifier"]["combined"]
    assert classifier["single_query"]["trace_recall"] == 0.52
    assert classifier["inter_query"]["trace_recall"] == 0.693
    assert classifier["paired_test"]["inter_only"] == 13
    assert classifier["paired_test"]["single_only"] == 0
