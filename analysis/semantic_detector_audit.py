"""Does the inter-query advantage survive a stronger, semantic detector?

The bundled detectors (rules, keyword classifier, intent tracker) are deliberately simple, so a
skeptic can argue the single-query-vs-inter-query gap is an artifact of weak detectors. This audit
answers that with a standard-NLP detector that is stronger than the hand-written baselines and still
fully deterministic and local (TF-IDF nearest-centroid, no LLM, no network, no training of any
language model):

  representation : TF-IDF over turn text.
  attack model   : cosine similarity to the centroid of KNOWN attack-turn vectors, built
                   leave-one-scenario-out so a scenario is never scored using its own attack turns
                   (no memorization of the test case).
  single-query   : score each turn from its own text alone.
  inter-query    : score each turn from the accumulated conversation-so-far text.
  threshold      : chosen once on the pooled score distribution (Youden's J on attack vs benign
                   turns), the same threshold applied to both modes so the comparison is fair.

If inter-query still beats single-query here, the effect is a property of the task (cross-turn
signal), not of the weakness of the bundled detectors.

Run:  python3 analysis/semantic_detector_audit.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scenarios import get_all_scenarios


def _cos(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    an = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
    bn = b / (np.linalg.norm(b) + 1e-9)
    return an @ bn


def _threshold(scores: np.ndarray, labels: np.ndarray) -> float:
    """Youden's J optimal threshold over the pooled attack/benign turn scores."""
    best_t, best_j = 0.5, -1.0
    for t in np.sort(scores):
        pred = scores >= t
        tp = np.sum(pred & (labels == 1))
        fn = np.sum(~pred & (labels == 1))
        fp = np.sum(pred & (labels == 0))
        tn = np.sum(~pred & (labels == 0))
        tpr = tp / (tp + fn) if (tp + fn) else 0.0
        fpr = fp / (fp + tn) if (fp + tn) else 0.0
        j = tpr - fpr
        if j > best_j:
            best_j, best_t = j, float(t)
    return best_t


def run(as_json: bool = False) -> dict:
    scenarios = [s for s in get_all_scenarios() if s.attack_turns]
    # Build a global vocabulary over every turn (both modes) so vectors are comparable.
    corpus = []
    for s in scenarios:
        acc = ""
        for turn in s.turns:
            corpus.append(turn.content)
            acc = (acc + " " + turn.content).strip()
            corpus.append(acc)
    vec = TfidfVectorizer(min_df=1, ngram_range=(1, 2)).fit(corpus)

    # Pre-vectorize per scenario in both modes, with attack labels.
    per = []
    for s in scenarios:
        single_txt, inter_txt, labels, acc = [], [], [], ""
        for i, turn in enumerate(s.turns):
            acc = (acc + " " + turn.content).strip()
            single_txt.append(turn.content)
            inter_txt.append(acc)
            labels.append(1 if i in s.attack_turns else 0)
        per.append({
            "scenario": s,
            "single": vec.transform(single_txt).toarray(),
            "inter": vec.transform(inter_txt).toarray(),
            "labels": np.array(labels),
        })

    def score_mode(key: str) -> dict:
        # Leave-one-scenario-out attack centroid, then pooled Youden threshold, then metrics.
        all_scores, all_labels = [], []
        per_scores = []
        for idx, p in enumerate(per):
            others = np.vstack([
                per[j]["single"][per[j]["labels"] == 1]  # centroid from single-turn attack text
                for j in range(len(per)) if j != idx and (per[j]["labels"] == 1).any()
            ])
            centroid = others.mean(axis=0)
            sc = _cos(p[key], centroid)
            per_scores.append(sc)
            all_scores.append(sc)
            all_labels.append(p["labels"])
        thr = _threshold(np.concatenate(all_scores), np.concatenate(all_labels))

        caught = benign_flags = benign_total = early = 0
        lead_sum = 0
        n = len(per)
        for p, sc in zip(per, per_scores):
            s = p["scenario"]
            pred = sc >= thr
            atk = s.attack_turns
            hit = [i for i in atk if pred[i]]
            if hit:
                caught += 1
                lead = max(atk) - min(hit)
                lead_sum += lead
                if lead > 0:
                    early += 1
            benign_idx = [i for i in range(len(s.turns)) if i not in atk]
            benign_flags += int(np.sum(pred[benign_idx]))
            benign_total += len(benign_idx)
        return {
            "threshold": round(thr, 3),
            "trace_recall": round(caught / n, 3),
            "query_fpr": round(benign_flags / benign_total, 3) if benign_total else 0.0,
            "avg_lead_turns": round(lead_sum / caught, 2) if caught else 0.0,
            "share_early_warning": round(early / caught, 3) if caught else 0.0,
            "caught": caught, "total": n,
        }

    report = {
        "detector": "tfidf_nearest_centroid_LOSO",
        "scenario_count": len(scenarios),
        "single_query": score_mode("single"),
        "inter_query": score_mode("inter"),
    }
    if as_json:
        print(json.dumps(report, indent=2))
        return report
    print(f"Semantic detector (TF-IDF nearest-centroid, leave-one-scenario-out) — "
          f"{report['scenario_count']} vulnerable scenarios\n")
    hdr = f"{'mode':13s} {'recall':>7s} {'query-FPR':>10s} {'lead':>7s} {'early-warn':>11s}"
    print(hdr)
    print("-" * len(hdr))
    for k, lbl in (("single_query", "single-query"), ("inter_query", "inter-query")):
        m = report[k]
        print(f"{lbl:13s} {m['trace_recall']:7.2f} {m['query_fpr']:10.2f} "
              f"{m['avg_lead_turns']:7.2f} {m['share_early_warning']:11.2f}")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    run(as_json=ap.parse_args().json)
