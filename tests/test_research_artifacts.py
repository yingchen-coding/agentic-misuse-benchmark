import json
from pathlib import Path

import pytest

from analysis.external_multiturn_validation import evaluate, parse_conversations
from analysis.inter_query_mechanism_safemt import bootstrap_ci
from cot_faithfulness.run_codex import safe_slug
from cot_faithfulness.score import _load_tasks, score_model
from cot_faithfulness_v2.score import load_tasks, score_model as score_model_v2


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_cot_scores_reject_duplicate_conditions(tmp_path: Path) -> None:
    tasks = _load_tasks()
    qid = next(iter(tasks))
    path = tmp_path / "duplicate.jsonl"
    write_jsonl(
        path,
        [
            {"id": qid, "condition": "neutral", "answer": "A"},
            {"id": qid, "condition": "neutral", "answer": "A"},
        ],
    )

    with pytest.raises(ValueError, match="duplicate task condition"):
        score_model(path, tasks)


def test_cot_scores_reject_incomplete_runs(tmp_path: Path) -> None:
    tasks_path = tmp_path / "tasks.jsonl"
    write_jsonl(
        tasks_path,
        [
            {
                "id": "q1",
                "choices": {"A": "right", "B": "wrong"},
                "correct": "A",
                "wrong_hint": "B",
            }
        ],
    )
    tasks = load_tasks(tasks_path)
    run_path = tmp_path / "run.jsonl"
    write_jsonl(run_path, [{"id": "q1", "condition": "neutral", "answer": "A"}])

    with pytest.raises(ValueError, match="missing task conditions"):
        score_model_v2(run_path, tasks)


def test_external_parser_rejects_malformed_conversations(tmp_path: Path) -> None:
    path = tmp_path / "malformed.csv"
    path.write_text("Multi-turn conversation\nnot-a-list\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid conversation"):
        parse_conversations(path, 1)


def test_empty_evaluations_fail_loud() -> None:
    with pytest.raises(ValueError, match="empty conversation"):
        evaluate(object(), [], inter_query=False)
    with pytest.raises(ValueError, match="must not be empty"):
        bootstrap_ci([])
    with pytest.raises(ValueError, match="clusters must match"):
        bootstrap_ci([1.0], clusters=[])


def test_model_slug_cannot_escape_output_directory() -> None:
    assert safe_slug("org/model") == "org-model"
    assert safe_slug("../../model") == "model"
    with pytest.raises(ValueError, match="model name"):
        safe_slug("../")
