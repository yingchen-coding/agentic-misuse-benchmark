#!/usr/bin/env python3
"""External-corpus validation of detector sensitivity to surface mutation on AdvBench.

The benchmark's mutation audits ask whether a detector that looks strong on static scenarios
degrades under semantic mutation. This script tests the same phenomenon on the independently
published AdvBench corpus (Zou et al. 2023), containing 520 harmful goals.

For each bundled detector, the script measures recall on raw goals, applies the fixed replacement
table below, and re-measures recall. The base-to-mutated gap measures sensitivity to these specific
surface changes; it is not a general semantic-robustness estimate.

Safety: this reads harmful-*goal* strings only as opaque text for surface mutation + detector recall;
it produces no harmful content and prints only aggregate rates (no AdvBench strings are emitted).

Run: python3 analysis/external_contamination_mutation.py --advbench analysis/external_data/advbench_harmful_behaviors.csv
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATASET_REVISION = "098262edf85f807224e70ecd87b9d83716bf6b73"
sys.path.insert(0, str(HERE.parent))

from detectors import get_detector, list_detectors  # noqa: E402
from scenarios.base import Turn  # noqa: E402

REPLACEMENTS = {
    "ignore": "set aside", "bypass": "work around", "policy": "guideline", "harmful": "restricted",
    "dangerous": "sensitive", "exploit": "take advantage of", "attack": "operation",
    "malware": "unwanted software", "password": "credential", "secret": "private token",
}


def mutate_text(text: str) -> str:
    out = text
    for src, dst in REPLACEMENTS.items():
        out = out.replace(src, dst).replace(src.title(), dst.title())
    return out


def load_advbench(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    goals = [row["goal"].strip() for row in rows if row.get("goal", "").strip()]
    if not goals:
        raise ValueError(f"no AdvBench goals found in {path}")
    return goals


def recall(detector, texts: list[str]) -> tuple[int, float]:
    if not texts:
        raise ValueError("texts to score must not be empty")
    flagged = sum(1 for t in texts
                  if detector.detect_turn(Turn(role="user", content=t, is_attack=True), []).detected)
    return flagged, flagged / len(texts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--advbench", type=Path,
                    default=HERE / "external_data" / "advbench_harmful_behaviors.csv")
    args = ap.parse_args()

    goals = load_advbench(args.advbench)
    mutated = [mutate_text(g) for g in goals]
    n_changed = sum(1 for g, m in zip(goals, mutated) if g != m)
    print(f"AdvBench goals: {len(goals)}   mutated by >=1 replacement: {n_changed}\n")

    report = {"dataset": "AdvBench (Zou et al. 2023)", "dataset_revision": DATASET_REVISION,
              "input_sha256": hashlib.sha256(args.advbench.read_bytes()).hexdigest(),
              "n": len(goals),
              "n_mutated_by_rule": n_changed, "replacement_rules": len(REPLACEMENTS), "detectors": {}}
    print(f"{'detector':12s} {'base':>7s} {'mutated':>8s} {'gap':>7s}")
    for name in list_detectors():
        det = get_detector(name)
        b_caught, b_rate = recall(det, goals)
        m_caught, m_rate = recall(det, mutated)
        gap = round(b_rate - m_rate, 3)
        report["detectors"][name] = {
            "base_recall": round(b_rate, 3), "mutated_recall": round(m_rate, 3),
            "detection_gap": gap, "base_caught": b_caught, "mutated_caught": m_caught}
        print(f"{name:12s} {b_rate:7.3f} {m_rate:8.3f} {gap:7.3f}")

    gaps = [d["detection_gap"] for d in report["detectors"].values()]
    report["max_gap"] = max(gaps)
    report["mean_gap"] = round(sum(gaps) / len(gaps), 3)
    out = HERE / "results" / "external_contamination_mutation.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nmax detection gap under mutation: {report['max_gap']:.3f}   "
          f"mean: {report['mean_gap']:.3f}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
