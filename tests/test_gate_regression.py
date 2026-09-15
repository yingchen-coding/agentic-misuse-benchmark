import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import gate_regression
import readiness_gate
from detectors.rules import RuleBasedDetector
from gate_regression import compare_to_baseline, test_set_fingerprint

EXACT = {"mode": "exact", "alpha": 0.05}
SIGNIFICANCE = {"mode": "significance", "alpha": 0.05}


def _outcomes(detected, false_positive=()):
    keys = sorted(set(detected) | set(false_positive) | {"baseline/X"})
    return {k: {"detected": k in detected, "false_positive": k in false_positive} for k in keys}


def test_fingerprint_is_stable_and_changes_with_the_test_set(monkeypatch):
    first = test_set_fingerprint()
    assert first == test_set_fingerprint()

    original = gate_regression.get_all_scenarios

    def edited():
        scenarios = original()
        turns = list(scenarios[0].turns)
        turns[0] = replace(turns[0], content=turns[0].content + " (edited)")
        return [replace(scenarios[0], turns=turns)] + scenarios[1:]

    monkeypatch.setattr(gate_regression, "get_all_scenarios", edited)
    assert test_set_fingerprint() != first


def test_exact_mode_blocks_on_any_newly_missed_case_even_if_others_improved():
    baseline = _outcomes({"a/1", "a/2"})
    current = _outcomes({"a/2", "a/3", "baseline/X"})
    current.setdefault("a/1", {"detected": False, "false_positive": False})
    baseline.setdefault("a/3", {"detected": False, "false_positive": False})
    result = compare_to_baseline(current, baseline, EXACT)
    assert result["newly_missed"] == ["a/1"]
    assert result["newly_caught"] == ["a/3", "baseline/X"]
    assert result["regressed"] is True


def test_significance_mode_ignores_a_single_flip_but_catches_a_large_one():
    keys = [f"c/{i}" for i in range(30)]
    baseline = {k: {"detected": True, "false_positive": False} for k in keys}
    one_flip = dict(baseline, **{"c/0": {"detected": False, "false_positive": False}})
    assert compare_to_baseline(one_flip, baseline, SIGNIFICANCE)["regressed"] is False

    many = {k: {"detected": i >= 10, "false_positive": False} for i, k in enumerate(keys)}
    result = compare_to_baseline(many, baseline, SIGNIFICANCE)
    assert result["regressed"] is True and result["mcnemar_p"] < 0.01


def test_new_false_positives_are_reported():
    baseline = _outcomes({"a/1"})
    current = _outcomes({"a/1"}, false_positive={"a/1"})
    assert compare_to_baseline(current, baseline, EXACT)["new_false_positives"] == ["a/1"]


def test_baseline_missing_cases_fails_loudly():
    with pytest.raises(ValueError, match="same --stress setting"):
        compare_to_baseline(_outcomes({"stress/1"}), _outcomes(set()), EXACT)


def _gate_report(tmp_path, *extra):
    report = tmp_path / "baseline.json"
    code = readiness_gate.main(["--detector", "rules", "--stress", "--output", str(report), *extra])
    return code, report


def test_unchanged_detector_passes_against_its_own_baseline(tmp_path):
    code, report = _gate_report(tmp_path)
    assert code == 0
    assert readiness_gate.main(["--detector", "rules", "--stress", "--baseline", str(report)]) == 0


def test_reverting_the_tool_output_fix_is_blocked_as_a_regression(tmp_path, monkeypatch, capsys):
    _, report = _gate_report(tmp_path)
    monkeypatch.setattr(RuleBasedDetector, "SCREENED_ROLES", frozenset({"user"}))

    code = readiness_gate.main(["--detector", "rules", "--stress", "--baseline", str(report),
                                "--output", str(tmp_path / "current.json")])

    assert code == 2
    assert "regression vs baseline: 25 case(s) newly missed" in capsys.readouterr().out
    regression = json.loads((tmp_path / "current.json").read_text())["detectors"]["rules"]["regression"]
    assert all(k.startswith("tool_relay/") for k in regression["newly_missed"])
    assert regression["mcnemar_p"] < 1e-6


def test_a_baseline_from_a_different_test_set_is_refused(tmp_path):
    _, report = _gate_report(tmp_path)
    data = json.loads(report.read_text())
    data["fingerprint"] = "0" * 64
    report.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="different test set"):
        readiness_gate.main(["--detector", "rules", "--baseline", str(report)])


def test_a_baseline_without_the_detector_is_refused(tmp_path):
    _, report = _gate_report(tmp_path)
    with pytest.raises(ValueError, match="no results for detector 'classifier'"):
        readiness_gate.main(["--detector", "classifier", "--stress", "--baseline", str(report)])
