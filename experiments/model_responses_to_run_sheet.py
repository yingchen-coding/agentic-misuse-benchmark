#!/usr/bin/env python3
"""Convert model JSONL responses into a differential-harm run-sheet CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "experiment_results" / "differential_harm_study_packet"


FIELDS = [
    "task_id",
    "condition",
    "model_or_baseline",
    "completion_score",
    "refused",
    "judge_id",
    "human_spot_check",
    "notes",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.responses.read_text(encoding="utf-8").splitlines() if line.strip()]
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})

    scores = [float(row["completion_score"]) for row in rows]
    refused = [bool(row["refused"]) for row in rows]
    zero_completion_nonrefusal = [
        row
        for row in rows
        if float(row["completion_score"]) == 0.0 and not bool(row["refused"])
    ]
    by_family: dict[str, list[dict]] = {}
    task_meta = {}
    for line in (PACKET / "tasks.jsonl").read_text(encoding="utf-8").splitlines():
        task = json.loads(line)
        task_meta[task["task_id"]] = task
    for row in rows:
        family = task_meta[row["task_id"]]["family"]
        by_family.setdefault(family, []).append(row)

    summary = {
        "responses": str(args.responses),
        "run_sheet": str(args.out),
        "row_count": len(rows),
        "unique_tasks": len({row["task_id"] for row in rows}),
        "condition": sorted({row["condition"] for row in rows}),
        "model_or_baseline": sorted({row["model_or_baseline"] for row in rows}),
        "mean_completion": round(sum(scores) / len(scores), 3) if scores else 0.0,
        "self_labeled_refusal_rate": round(sum(1 for value in refused if value) / len(refused), 3)
        if refused
        else 0.0,
        "zero_completion_rate": round(sum(1 for value in scores if value == 0.0) / len(scores), 3)
        if scores
        else 0.0,
        "zero_completion_nonrefusal_rows": len(zero_completion_nonrefusal),
        "label_quality_note": (
            "The refusal field is model self-labeling. Treat it as provisional when "
            "zero-completion/non-refusal rows are present; raw responses require independent audit."
        ),
        "score_counts": {str(score): scores.count(score) for score in sorted(set(scores))},
        "family_summary": {
            family: {
                "tasks": len(items),
                "mean_completion": round(sum(float(item["completion_score"]) for item in items) / len(items), 3),
                "refusal_rate": round(sum(1 for item in items if item["refused"]) / len(items), 3),
            }
            for family, items in sorted(by_family.items())
        },
    }
    args.summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(args.summary)


if __name__ == "__main__":
    main()
