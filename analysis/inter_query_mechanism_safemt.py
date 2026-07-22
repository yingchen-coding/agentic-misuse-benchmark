"""Does the accumulated trajectory reveal harmful intent that individual innocuous turns hide?

This is the core inter-query claim, measured on real, readable, external data at scale. SafeMTData
(Ren et al., "Derail Yourself: Multi-turn LLM Jailbreak Attack through Self-discovered Clues",
2024 preprint) contains 600 generated multi-turn attacks in which a single harmful goal (`plain_query`,
e.g. "Give detailed instructions for making dimethylmercury ...") is decomposed into a sequence of
individually innocuous queries (`multi_turn_queries`, e.g. "What contributions did this chemist make
to science?"). The whole point of the attack is that no single turn looks harmful; only the
trajectory does. That is exactly the property inter-query monitoring is supposed to exploit.

We quantify it with a real sentence-embedding model (all-MiniLM-L6-v2) and a HELD-OUT harmful
reference (5-fold: the harmful centroid for each fold is built from the *other* folds' harmful goals,
so an attack's own target never leaks into its own detector). For each attack we compute similarity
to the harmful centroid of:
  * each individual turn                        -> best_single = max over turns
  * the accumulating history (turn 1..k prefix) -> best_inter  = max over prefixes

Reported:
  1. Paired best_inter vs best_single across 600 attacks: mean difference + bootstrap 95% CI.
  2. Detection at a matched operating point: set the threshold at the 95th percentile of ALL
     individual-turn similarities (a 5% per-turn false-alarm proxy on the innocuous turns), then
     measure what fraction of attacks are caught by the best single turn vs by the accumulated
     history at that SAME threshold. The gap is the inter-query recall advantage.

Run (needs sentence-transformers):  python3 analysis/inter_query_mechanism_safemt.py --data /tmp/safemt_attack.json
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import random
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DATASET_REVISION = "04af7bd0b6b6044e797e936d79674e348316b9b8"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"


def prefixes(turns: list[str]) -> list[str]:
    return [" ".join(turns[: i + 1]) for i in range(len(turns))]


def bootstrap_ci(
    values: list[float],
    clusters: list[str] | None = None,
    n: int = 2000,
    seed: int = 0,
) -> tuple[float, float]:
    if not values:
        raise ValueError("bootstrap values must not be empty")
    if n <= 0:
        raise ValueError(f"bootstrap sample count must be positive, got {n}")
    if clusters is not None and len(clusters) != len(values):
        raise ValueError("bootstrap clusters must match the values length")
    rng = random.Random(seed)
    cluster_rows: dict[str, list[float]] = {}
    for index, value in enumerate(values):
        cluster = clusters[index] if clusters is not None else str(index)
        cluster_rows.setdefault(cluster, []).append(value)
    cluster_ids = sorted(cluster_rows)
    means = []
    for _ in range(n):
        sampled = [rng.choice(cluster_ids) for _ in cluster_ids]
        sample_values = [value for cluster in sampled for value in cluster_rows[cluster]]
        means.append(sum(sample_values) / len(sample_values))
    means.sort()
    return means[int(0.025 * n)], means[int(0.975 * n)]


def run(data_path: Path) -> dict:
    from sentence_transformers import SentenceTransformer

    attacks = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(attacks, list) or len(attacks) < 5:
        raise ValueError(f"SafeMT input must contain at least five attacks: {data_path}")
    for index, attack in enumerate(attacks):
        if not isinstance(attack, dict) or not isinstance(attack.get("plain_query"), str):
            raise ValueError(f"invalid SafeMT attack at index {index}")
        if not isinstance(attack.get("query_id"), (str, int)):
            raise ValueError(f"missing query_id at SafeMT index {index}")
        turns = attack.get("multi_turn_queries")
        if not isinstance(turns, list) or not turns or not all(isinstance(t, str) and t for t in turns):
            raise ValueError(f"invalid multi-turn queries at SafeMT index {index}")
        if not isinstance(attack.get("category"), str) or not attack["category"]:
            raise ValueError(f"missing category at SafeMT index {index}")
    model = SentenceTransformer("all-MiniLM-L6-v2", revision=MODEL_REVISION)

    goals = [a["plain_query"] for a in attacks]
    goal_emb = model.encode(goals, normalize_embeddings=True, show_progress_bar=False)

    k = 5
    query_ids = [str(attack["query_id"]) for attack in attacks]
    unique_query_ids = sorted(set(query_ids))
    if len(unique_query_ids) < k:
        raise ValueError(f"SafeMT input needs at least {k} unique query_id groups")
    rng = random.Random(0)
    rng.shuffle(unique_query_ids)
    query_fold = {query_id: index % k for index, query_id in enumerate(unique_query_ids)}
    fold = [query_fold[query_id] for query_id in query_ids]
    centroids = {}
    for f in range(k):
        others = np.array([goal_emb[i] for i in range(len(attacks)) if fold[i] != f])
        c = others.mean(axis=0)
        centroids[f] = c / (np.linalg.norm(c) + 1e-12)

    best_single, best_inter, all_turn_sims = [], [], []
    per_attack = []
    for i, a in enumerate(attacks):
        turns = a["multi_turn_queries"]
        c = centroids[fold[i]]
        t_emb = model.encode(turns, normalize_embeddings=True, show_progress_bar=False)
        p_emb = model.encode(prefixes(turns), normalize_embeddings=True, show_progress_bar=False)
        t_sims = (t_emb @ c).tolist()
        p_sims = (p_emb @ c).tolist()
        best_single.append(max(t_sims))
        best_inter.append(max(p_sims))
        all_turn_sims.extend(t_sims)
        per_attack.append({"category": a["category"], "n_turns": len(turns),
                           "best_single": max(t_sims), "best_inter": max(p_sims)})

    diffs = [bi - bs for bi, bs in zip(best_inter, best_single)]
    lo, hi = bootstrap_ci(diffs, clusters=query_ids)
    thr = float(np.percentile(all_turn_sims, 95))  # 5% per-turn false-alarm proxy
    recall_single = sum(1 for x in best_single if x > thr) / len(best_single)
    recall_inter = sum(1 for x in best_inter if x > thr) / len(best_inter)

    cats = sorted({a["category"] for a in attacks})
    by_cat = {}
    for cat in cats:
        rows = [p for p in per_attack if p["category"] == cat]
        rs = sum(1 for p in rows if p["best_single"] > thr) / len(rows)
        ri = sum(1 for p in rows if p["best_inter"] > thr) / len(rows)
        by_cat[cat] = {"n": len(rows), "single_recall": round(rs, 3),
                       "inter_recall": round(ri, 3), "gain": round(ri - rs, 3)}

    return {
        "dataset": "SafeMTData Attack_600 (Ren et al., 2024 preprint)",
        "dataset_revision": DATASET_REVISION,
        "input_sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
        "n_attacks": len(attacks),
        "embedding_model": "all-MiniLM-L6-v2",
        "embedding_model_revision": MODEL_REVISION,
        "sentence_transformers_version": importlib.metadata.version("sentence-transformers"),
        "held_out_centroid": "5-fold grouped by query_id (all same-goal variants held out)",
        "bootstrap_unit": f"query_id ({len(unique_query_ids)} unique harmful goals)",
        "mean_best_single_sim": round(float(np.mean(best_single)), 4),
        "mean_best_inter_sim": round(float(np.mean(best_inter)), 4),
        "mean_inter_minus_single": round(float(np.mean(diffs)), 4),
        "inter_minus_single_95ci": [round(lo, 4), round(hi, 4)],
        "inter_gt_single_epsilon": 1e-6,
        "frac_attacks_inter_gt_single": round(sum(1 for d in diffs if d > 1e-6) / len(diffs), 4),
        "operating_point": "threshold = 95th pct of individual-turn sims (5% per-turn FP proxy)",
        "threshold": round(thr, 4),
        "recall_single_query": round(recall_single, 4),
        "recall_inter_query": round(recall_inter, 4),
        "recall_gain": round(recall_inter - recall_single, 4),
        "by_category": by_cat,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=Path("/tmp/safemt_attack.json"))
    args = ap.parse_args()
    res = run(args.data)
    print(json.dumps(res, indent=2))
    out = HERE / "results" / "inter_query_mechanism_safemt.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
