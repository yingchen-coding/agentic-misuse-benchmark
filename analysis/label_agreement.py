"""Agreement between two label sources scored on the same rows.

Compares model self-labels with an independent adjudicator today, and either of them with human
labels once a human-labeled CSV is supplied. Reports raw agreement, Cohen's kappa, the 2x2 confusion
counts, and a per-group breakdown so a disagreement concentrated in one model/condition is flagged
instead of averaged away.

Run:  python3 analysis/label_agreement.py
      python3 analysis/label_agreement.py --human-labels human_labels.csv

A human-labels CSV needs the columns task_id, condition, model_or_baseline, refused.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evalstats import kappa_interval  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKET = REPO_ROOT / "experiment_results" / "differential_harm_study_packet"
DEFAULT_DETAILS = PACKET / "independent_adjudication_details.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "analysis" / "results" / "label_agreement.json"
ROW_KEY = ("task_id", "condition", "model_or_baseline")
GROUP_BY = ("model_or_baseline", "condition")
SELF_LABEL = "original_refused"
ADJUDICATOR_LABEL = "refused"
HUMAN_LABEL = "human_refused"
# A group is flagged systematic when it is big enough to matter and disagrees often enough
# that the cause is the labeler for that group, not scattered noise.
SYSTEMATIC_MIN_ROWS = 10
SYSTEMATIC_MIN_DISAGREEMENT = 0.2


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise ValueError(f"not a boolean label: {value!r}")


def _agreement_terms(a: list[bool], b: list[bool]) -> tuple[float, float] | None:
    """(observed, chance-expected) agreement, or None for empty input."""
    if len(a) != len(b):
        raise ValueError(f"label lists differ in length: {len(a)} vs {len(b)}")
    n = len(a)
    if n == 0:
        return None
    observed = sum(x == y for x, y in zip(a, b)) / n
    p_a = sum(a) / n
    p_b = sum(b) / n
    return observed, p_a * p_b + (1 - p_a) * (1 - p_b)


def cohen_kappa(a: list[bool], b: list[bool]) -> float | None:
    """Cohen's kappa, or None when both sources are the same constant (kappa is 0/0)."""
    terms = _agreement_terms(a, b)
    if terms is None or terms[1] == 1.0:
        return None
    observed, expected = terms
    return (observed - expected) / (1 - expected)


def _pair_stats(a: list[bool], b: list[bool]) -> dict:
    n = len(a)
    only_a = sum(x and not y for x, y in zip(a, b))
    only_b = sum(y and not x for x, y in zip(a, b))
    disagreements = only_a + only_b
    kappa = cohen_kappa(a, b)
    return {
        "n": n,
        "disagreements": disagreements,
        "disagreement_rate": disagreements / n if n else 0.0,
        "agreement": (n - disagreements) / n if n else 0.0,
        "cohen_kappa": kappa,
        "cohen_kappa_95ci": (list(kappa_interval(*_agreement_terms(a, b), n))
                             if kappa is not None else None),
        "confusion": {
            "both_true": sum(x and y for x, y in zip(a, b)),
            "only_first_true": only_a,
            "only_second_true": only_b,
            "both_false": sum(not x and not y for x, y in zip(a, b)),
        },
    }


def _rounded(stats: dict) -> dict:
    out = dict(stats)
    for key in ("disagreement_rate", "agreement", "cohen_kappa"):
        if out[key] is not None:
            out[key] = round(out[key], 3)
    if out["cohen_kappa_95ci"] is not None:
        out["cohen_kappa_95ci"] = [round(v, 3) for v in out["cohen_kappa_95ci"]]
    return out


def compare(rows: list[dict], first: str, second: str) -> dict:
    """Agreement between label fields `first` and `second`, overall and per model/condition."""
    a = [parse_bool(row[first]) for row in rows]
    b = [parse_bool(row[second]) for row in rows]
    summary = _pair_stats(a, b)

    grouped: dict[tuple, list[tuple[bool, bool]]] = defaultdict(list)
    for row, x, y in zip(rows, a, b):
        grouped[tuple(row[k] for k in GROUP_BY)].append((x, y))

    by_group = []
    for group, pairs in sorted(grouped.items()):
        stats = _pair_stats([p[0] for p in pairs], [p[1] for p in pairs])
        stats["group"] = dict(zip(GROUP_BY, group))
        stats["systematic"] = (
            stats["n"] >= SYSTEMATIC_MIN_ROWS
            and stats["disagreement_rate"] >= SYSTEMATIC_MIN_DISAGREEMENT
        )
        by_group.append(stats)

    systematic = [g for g in by_group if g["systematic"]]
    result = _rounded(summary)
    result["first"] = first
    result["second"] = second
    result["systematic_groups"] = [g["group"] for g in systematic]
    result["disagreements_in_systematic_groups"] = sum(g["disagreements"] for g in systematic)
    result["by_group"] = [_rounded(g) for g in by_group]
    return result


def load_jsonl(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def attach_human_labels(rows: list[dict], csv_path: Path) -> list[dict]:
    """Return only the rows that have a human label, with that label under HUMAN_LABEL."""
    required = {*ROW_KEY, "refused"}
    human: dict[tuple, str] = {}
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{csv_path.name} is missing columns: {sorted(missing)}")
        for line, r in enumerate(reader, start=2):
            key = tuple(r[k] for k in ROW_KEY)
            if key in human:
                raise ValueError(f"{csv_path.name}:{line} labels {key} twice")
            human[key] = r["refused"]
    labeled = [
        {**row, HUMAN_LABEL: human[key]}
        for row in rows
        if (key := tuple(row[k] for k in ROW_KEY)) in human
    ]
    if not labeled:
        raise ValueError(f"no rows in {csv_path.name} match the adjudicated rows on {ROW_KEY}")
    return labeled


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    return str(resolved.relative_to(REPO_ROOT)) if resolved.is_relative_to(REPO_ROOT) else path.name


def run(details: Path, human_labels: Path | None = None) -> dict:
    rows = load_jsonl(details)
    report = {
        "input": _display_path(details),
        "label": "refused",
        "sources": {"model_self_label": SELF_LABEL, "independent_adjudicator": ADJUDICATOR_LABEL},
        "systematic_rule": {
            "min_rows": SYSTEMATIC_MIN_ROWS,
            "min_disagreement_rate": SYSTEMATIC_MIN_DISAGREEMENT,
        },
        "self_vs_adjudicator": compare(rows, SELF_LABEL, ADJUDICATOR_LABEL),
        "human": None,
    }
    if human_labels is not None:
        labeled = attach_human_labels(rows, human_labels)
        report["human"] = {
            "input": _display_path(human_labels),
            "rows_labeled": len(labeled),
            "human_vs_adjudicator": compare(labeled, HUMAN_LABEL, ADJUDICATOR_LABEL),
            "human_vs_self": compare(labeled, HUMAN_LABEL, SELF_LABEL),
        }
    return report


def _print_comparison(title: str, result: dict) -> None:
    kappa = result["cohen_kappa"]
    kappa_text = ("undefined" if kappa is None
                  else f"{kappa:.3f} (95% CI {result['cohen_kappa_95ci'][0]:.2f} to "
                       f"{result['cohen_kappa_95ci'][1]:.2f})")
    print(f"{title}: n={result['n']}  agreement={result['agreement']:.3f}  "
          f"kappa={kappa_text}  disagreements={result['disagreements']}")
    for group in result["by_group"]:
        if group["disagreements"]:
            confusion = group["confusion"]
            flag = "  <- systematic" if group["systematic"] else ""
            label = " / ".join(group["group"].values())
            print(f"  {label}: {group['disagreements']}/{group['n']} "
                  f"(only {result['first']}: {confusion['only_first_true']}, "
                  f"only {result['second']}: {confusion['only_second_true']}){flag}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--details", type=Path, default=DEFAULT_DETAILS)
    parser.add_argument("--human-labels", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = run(args.details, args.human_labels)
    _print_comparison("model self-label vs adjudicator", report["self_vs_adjudicator"])
    if report["human"] is None:
        print("human labels: not provided (pass --human-labels to add them)")
    else:
        _print_comparison("human vs adjudicator", report["human"]["human_vs_adjudicator"])
        _print_comparison("human vs model self-label", report["human"]["human_vs_self"])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {_display_path(args.output)}")


if __name__ == "__main__":
    main()
