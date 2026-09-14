import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from analysis.hard_negative_audit import audit


def test_audit_reports_the_trajectory_path_the_benchmark_scores_with():
    report = audit()
    classifier = report["detectors"]["classifier"]
    assert classifier["flagged_turns"] == 0
    trajectory = classifier["trajectory"]
    assert trajectory["flagged_turns"] == 2
    assert trajectory["per_trace"]["trace_03_cybersecurity_journalism"]["flagged"] == 2
    assert trajectory["total_turns"] == report["total_turns"]
