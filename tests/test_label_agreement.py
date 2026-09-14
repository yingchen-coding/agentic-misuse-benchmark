import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from analysis.label_agreement import (
    DEFAULT_DETAILS,
    attach_human_labels,
    cohen_kappa,
    compare,
    parse_bool,
    run,
)


def test_kappa_is_one_for_perfect_agreement():
    labels = [True, False, True, False]
    assert cohen_kappa(labels, labels) == 1.0


def test_kappa_is_zero_when_agreement_equals_chance():
    assert cohen_kappa([True, True, False, False], [True, False, True, False]) == 0.0


def test_kappa_is_undefined_when_both_sources_are_the_same_constant():
    assert cohen_kappa([True, True], [True, True]) is None


def test_kappa_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        cohen_kappa([True], [True, False])


def test_parse_bool_fails_loudly_on_unknown_label():
    assert parse_bool("true") is True and parse_bool(False) is False
    with pytest.raises(ValueError):
        parse_bool("maybe")


def _row(task, model, condition, first, second):
    return {"task_id": task, "model_or_baseline": model, "condition": condition,
            "a": first, "b": second}


def test_disagreement_concentrated_in_one_group_is_flagged_systematic():
    rows = [_row(f"t{i}", "m1", "clean", True, True) for i in range(10)]
    rows += [_row(f"u{i}", "m2", "noisy", True, i % 2 == 0) for i in range(10)]
    result = compare(rows, "a", "b")
    assert result["disagreements"] == 5
    assert result["systematic_groups"] == [{"model_or_baseline": "m2", "condition": "noisy"}]
    assert result["disagreements_in_systematic_groups"] == 5


def test_small_group_is_not_flagged_even_if_it_disagrees():
    rows = [_row("t1", "m1", "tiny", True, False), _row("t2", "m1", "tiny", False, True)]
    assert compare(rows, "a", "b")["systematic_groups"] == []


def test_human_labels_join_on_task_condition_and_model(tmp_path):
    rows = [
        {"task_id": "t1", "condition": "c", "model_or_baseline": "m", "refused": "true"},
        {"task_id": "t2", "condition": "c", "model_or_baseline": "m", "refused": "false"},
    ]
    csv_path = tmp_path / "human.csv"
    csv_path.write_text("task_id,condition,model_or_baseline,refused\nt1,c,m,false\n")
    labeled = attach_human_labels(rows, csv_path)
    assert [r["task_id"] for r in labeled] == ["t1"]
    assert labeled[0]["human_refused"] == "false"


def test_human_labels_with_no_matching_rows_fail_loudly(tmp_path):
    csv_path = tmp_path / "human.csv"
    csv_path.write_text("task_id,condition,model_or_baseline,refused\nzzz,c,m,true\n")
    with pytest.raises(ValueError):
        attach_human_labels([{"task_id": "t1", "condition": "c", "model_or_baseline": "m"}],
                            csv_path)


def test_human_labels_with_a_duplicate_row_fail_loudly(tmp_path):
    csv_path = tmp_path / "human.csv"
    csv_path.write_text("task_id,condition,model_or_baseline,refused\nt1,c,m,true\nt1,c,m,false\n")
    with pytest.raises(ValueError, match="twice"):
        attach_human_labels([{"task_id": "t1", "condition": "c", "model_or_baseline": "m"}],
                            csv_path)


def test_human_labels_missing_a_column_fail_loudly(tmp_path):
    csv_path = tmp_path / "human.csv"
    csv_path.write_text("task_id,condition,refused\nt1,c,true\n")
    with pytest.raises(ValueError, match="model_or_baseline"):
        attach_human_labels([{"task_id": "t1", "condition": "c", "model_or_baseline": "m"}],
                            csv_path)


def test_recorded_pilot_reproduces_its_disagreement_count():
    report = run(DEFAULT_DETAILS)
    result = report["self_vs_adjudicator"]
    assert result["n"] == 240
    assert result["disagreements"] == 52
    assert report["human"] is None
