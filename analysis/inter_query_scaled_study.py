"""A scaled, properly-controlled study of when inter-query context helps multi-turn misuse detection.

The 25-scenario benchmark is a pilot with toy detectors. This experiment is the real version of the
central question, on external data at scale with a properly-built detector and honest statistics:

  Does scoring the *accumulated conversation history* (inter-query) beat scoring each *turn in
  isolation* (single-query), when both are calibrated to the same false-positive operating point,
  measured on held-out data, with confidence intervals --- and does the answer depend on the attack
  distribution?

Design (rigorous):
  * Data: `tom-gibbs/multi-turn_jailbreak_attack_datasets` (4136 harmful + 1200 benign multi-turn
    conversations). Goal-level 50/50 train/test split (seeded), keeping every cipher variant of a
    goal in the same split.
  * Detector: nearest-centroid over TF-IDF features (a real, deterministic semantic detector), fit
    on the TRAIN split only. Two scoring units:
        single-query : each user turn's own text.
        inter-query  : the accumulating history (all turns so far), concatenated.
    Each mode gets its own harmful centroid and its own threshold, the threshold set on TRAIN benign
    to a target query-level FPR. This is the fairness control: single and inter are compared at the
    SAME benign operating point, not at arbitrary thresholds.
  * Metrics on the TEST split: trace recall (a conversation is caught if any of its units exceeds
    the threshold), trace FPR on benign, plus a 1000-resample bootstrap 95% CI on the inter-minus-
    single recall difference.
  * Mechanism check: recall stratified by conversation length, to see whether any inter-query
    advantage grows with how much history there is to accumulate.

Run (needs scikit-learn):
  python3 analysis/inter_query_scaled_study.py --harmful /tmp/mt_Harmful_Dataset.csv \
      --benign /tmp/mt_Completely-Benign_Dataset.csv --target-fpr 0.05
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import importlib.metadata
import json
import random
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

csv.field_size_limit(10**7)
HERE = Path(__file__).resolve().parent
DATASET_REVISION = "e3b30257c4d6be5438ea19f0989ac82c24234fe4"


def load_conversations(path: Path) -> list[tuple[str, list[str]]]:
    convs: list[tuple[str, list[str]]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            try:
                msgs = ast.literal_eval(row.get("Multi-turn conversation", ""))
            except (ValueError, SyntaxError) as exc:
                raise ValueError(f"invalid conversation at {path}:{row_number}") from exc
            if not isinstance(msgs, list):
                raise ValueError(f"conversation must be a list at {path}:{row_number}")
            goal_id = row.get("Goal ID", "").strip()
            if not goal_id:
                raise ValueError(f"missing Goal ID at {path}:{row_number}")
            turns = [
                m["content"]
                for m in msgs
                if isinstance(m, dict)
                and m.get("role") == "user"
                and m.get("content")
                and m["content"] != "None"
            ]
            if len(turns) >= 2:
                convs.append((goal_id, turns))
    if not convs:
        raise ValueError(f"no valid multi-turn conversations found in {path}")
    return convs


def units(conv: list[str], mode: str) -> list[str]:
    """The text units a mode scores: single turns, or cumulative history snapshots."""
    if mode == "single_query":
        return conv
    if mode == "inter_query":
        return [" ".join(conv[: i + 1]) for i in range(len(conv))]
    raise ValueError(f"unknown scoring mode: {mode}")


def threshold_at_fpr(scores: list[float], target_fpr: float) -> float:
    """Lowest observed threshold whose benign flag rate is at most target_fpr."""
    if not scores:
        raise ValueError("benign calibration scores must not be empty")
    if not 0 <= target_fpr < 1:
        raise ValueError(f"target_fpr must be in [0, 1), got {target_fpr}")
    s = sorted(scores, reverse=True)
    k = int(target_fpr * len(s))
    return s[k] if k < len(s) else (s[-1] - 1e-9)


def trace_flags(convs, vec, centroid, mode, thr) -> list[bool]:
    out = []
    for conv in convs:
        u = units(conv, mode)
        X = vec.transform(u)
        sims = cosine_similarity(X, centroid).ravel()
        out.append(bool((sims > thr).any()))
    return out


def bootstrap_diff(
    harm_iq: list[bool],
    harm_sq: list[bool],
    clusters: list[str],
    n: int = 1000,
    seed: int = 0,
) -> tuple[float, float]:
    if not harm_iq or len(harm_iq) != len(harm_sq):
        raise ValueError("bootstrap inputs must be non-empty and have equal length")
    if len(clusters) != len(harm_iq):
        raise ValueError("bootstrap clusters must match the flag lengths")
    if n <= 0:
        raise ValueError(f"bootstrap sample count must be positive, got {n}")
    rng = random.Random(seed)
    cluster_rows: dict[str, list[int]] = {}
    for index, cluster in enumerate(clusters):
        cluster_rows.setdefault(cluster, []).append(index)
    cluster_ids = sorted(cluster_rows)
    diffs = []
    for _ in range(n):
        sampled_clusters = [rng.choice(cluster_ids) for _ in cluster_ids]
        sample = [index for cluster in sampled_clusters for index in cluster_rows[cluster]]
        r_iq = sum(harm_iq[i] for i in sample) / len(sample)
        r_sq = sum(harm_sq[i] for i in sample) / len(sample)
        diffs.append(r_iq - r_sq)
    diffs.sort()
    return diffs[int(0.025 * n)], diffs[int(0.975 * n)]


def run(harmful_path: Path, benign_path: Path, target_fpr: float, seed: int = 0) -> dict:
    harmful_records = load_conversations(harmful_path)
    benign_records = load_conversations(benign_path)
    if len(harmful_records) < 4 or len(benign_records) < 4:
        raise ValueError("each dataset split must contain at least four conversations")
    if not 0 <= target_fpr < 1:
        raise ValueError(f"target_fpr must be in [0, 1), got {target_fpr}")
    rng = random.Random(seed)
    def split_by_goal(
        records: list[tuple[str, list[str]]],
    ) -> tuple[list[tuple[str, list[str]]], list[tuple[str, list[str]]]]:
        goal_ids = sorted({goal_id for goal_id, _ in records})
        if len(goal_ids) < 2:
            raise ValueError("each dataset needs at least two distinct Goal ID values")
        rng.shuffle(goal_ids)
        midpoint = len(goal_ids) // 2
        train_ids = set(goal_ids[:midpoint])
        return (
            [record for record in records if record[0] in train_ids],
            [record for record in records if record[0] not in train_ids],
        )

    h_tr_records, h_te_records = split_by_goal(harmful_records)
    b_tr_records, b_te_records = split_by_goal(benign_records)
    h_tr = [turns for _, turns in h_tr_records]
    h_te = [turns for _, turns in h_te_records]
    b_tr = [turns for _, turns in b_tr_records]
    b_te = [turns for _, turns in b_te_records]

    train_turns = [t for c in h_tr + b_tr for t in c]
    vec = TfidfVectorizer(max_features=8000, ngram_range=(1, 2), min_df=2)
    vec.fit(train_turns)

    result = {"dataset": "tom-gibbs/multi-turn_jailbreak_attack_datasets",
              "dataset_revision": DATASET_REVISION,
              "harmful_input_sha256": hashlib.sha256(harmful_path.read_bytes()).hexdigest(),
              "benign_input_sha256": hashlib.sha256(benign_path.read_bytes()).hexdigest(),
              "n_harmful": len(harmful_records), "n_benign": len(benign_records),
              "n_harmful_goals": len({goal_id for goal_id, _ in harmful_records}),
              "n_benign_goals": len({goal_id for goal_id, _ in benign_records}),
              "train_harmful": len(h_tr), "test_harmful": len(h_te),
              "train_benign": len(b_tr), "test_benign": len(b_te),
              "train_harmful_goals": len({goal_id for goal_id, _ in h_tr_records}),
              "test_harmful_goals": len({goal_id for goal_id, _ in h_te_records}),
              "train_benign_goals": len({goal_id for goal_id, _ in b_tr_records}),
              "test_benign_goals": len({goal_id for goal_id, _ in b_te_records}),
              "target_fpr": target_fpr,
              "scikit_learn_version": importlib.metadata.version("scikit-learn"), "modes": {}}

    mode_flags = {}
    for mode in ("single_query", "inter_query"):
        h_units = [u for c in h_tr for u in units(c, mode)]
        centroid = np.asarray(vec.transform(h_units).mean(axis=0))
        b_units = [u for c in b_tr for u in units(c, mode)]
        b_sims = cosine_similarity(vec.transform(b_units), centroid).ravel().tolist()
        thr = threshold_at_fpr(b_sims, target_fpr)

        harm_flags = trace_flags(h_te, vec, centroid, mode, thr)
        ben_flags = trace_flags(b_te, vec, centroid, mode, thr)
        mode_flags[mode] = harm_flags
        result["modes"][mode] = {
            "test_trace_recall": round(sum(harm_flags) / len(harm_flags), 4),
            "test_trace_fpr": round(sum(ben_flags) / len(ben_flags), 4),
            "threshold": round(float(thr), 4),
        }

    lo, hi = bootstrap_diff(
        mode_flags["inter_query"],
        mode_flags["single_query"],
        clusters=[goal_id for goal_id, _ in h_te_records],
    )
    result["inter_minus_single_recall"] = round(
        result["modes"]["inter_query"]["test_trace_recall"]
        - result["modes"]["single_query"]["test_trace_recall"], 4)
    result["inter_minus_single_95ci"] = [round(lo, 4), round(hi, 4)]
    result["bootstrap_unit"] = "Goal ID (cipher variants clustered)"

    buckets = {"2-5": [], "6-15": [], "16+": []}
    for conv, iq, sq in zip(h_te, mode_flags["inter_query"], mode_flags["single_query"]):
        n = len(conv)
        b = "2-5" if n <= 5 else ("6-15" if n <= 15 else "16+")
        buckets[b].append((iq, sq))
    result["by_length"] = {
        b: {"n": len(v),
            "inter_recall": round(sum(x[0] for x in v) / len(v), 3) if v else None,
            "single_recall": round(sum(x[1] for x in v) / len(v), 3) if v else None}
        for b, v in buckets.items()}
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--harmful", type=Path, required=True)
    ap.add_argument("--benign", type=Path, required=True)
    ap.add_argument("--target-fpr", type=float, default=0.05)
    args = ap.parse_args()

    res = run(args.harmful, args.benign, args.target_fpr)
    print(json.dumps(res, indent=2))
    out = HERE / "results" / "inter_query_scaled_study.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
