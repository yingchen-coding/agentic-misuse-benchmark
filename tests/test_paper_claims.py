"""Regression lock on the numbers the inter-query-defense manuscript cites.

A paper claim that silently drifts is a credibility bug. These tests pin every headline figure the
manuscript reports to the value its own script produces, so any change to the detectors, scenarios,
or audit code that would move a cited number fails CI instead of quietly invalidating the paper.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.inter_query_defense import run as run_inter_query
from analysis.semantic_detector_audit import run as run_semantic


def test_inter_query_headline_numbers():
    r = run_inter_query(as_json=False)["detectors"]

    # rules: identical in both modes (the negative control that proves the effect is context, not
    # a scoring artifact).
    assert r["rules"]["single_query"]["trace_recall"] == 1.00
    assert r["rules"]["inter_query"]["trace_recall"] == 1.00
    assert r["rules"]["single_query"]["avg_lead_turns"] == r["rules"]["inter_query"]["avg_lead_turns"]

    # classifier: the +20-point recall gain at unchanged query FPR.
    c = r["classifier"]
    assert c["single_query"]["trace_recall"] == 0.64
    assert c["inter_query"]["trace_recall"] == 0.84
    assert c["single_query"]["query_fpr"] == 0.022
    assert c["inter_query"]["query_fpr"] == 0.022

    # intent tracker: 0 per-query, recovers with history, fires early.
    it = r["intent"]
    assert it["single_query"]["trace_recall"] == 0.00
    assert it["inter_query"]["trace_recall"] == 0.24
    assert it["inter_query"]["avg_lead_turns"] == 1.17


def test_semantic_detector_replicates_the_gain():
    r = run_semantic(as_json=False)
    # The inter-query recall gain replicates on an independent, stronger detector class.
    assert r["single_query"]["trace_recall"] == 0.68
    assert r["inter_query"]["trace_recall"] == 0.84
    # Gain is real, not "flag everything": FPR rises only modestly with context.
    assert r["inter_query"]["query_fpr"] - r["single_query"]["query_fpr"] <= 0.10
