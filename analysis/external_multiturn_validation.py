"""External validation of the inter-query claim on a real multi-turn jailbreak dataset.

The benchmark's central claim is that giving a fixed detector cross-turn history recovers multi-turn
misuse that per-message screening misses. The claim is measured on 25 self-authored scenarios. This
script tests the same claim on an external, independently published dataset this project did not
write: `tom-gibbs/multi-turn_jailbreak_attack_datasets` (HuggingFace), whose attacks distribute a
harmful instruction across many turns via a word-substitution cipher -- a different multi-turn attack
style from the benchmark's own scenarios.

For each conversation we run the bundled detectors in two modes over the user turns:
  single-query : each turn scored with empty history.
  inter-query  : each turn scored with the accumulating prior turns.
Trace recall is measured on the Harmful split, trace FPR on the Completely-Benign split. The
question is not whether absolute recall is high (the detectors are tuned to a different attack
style) but whether inter-query > single-query holds on external data -- i.e. whether the mechanism
generalizes.

Run:  python3 analysis/external_multiturn_validation.py \
        --harmful /tmp/mt_Harmful_Dataset.csv --benign /tmp/mt_Completely-Benign_Dataset.csv --n 400
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
csv.field_size_limit(10**7)

from detectors import get_detector, list_detectors  # noqa: E402
from scenarios.base import Turn  # noqa: E402

HERE = Path(__file__).resolve().parent
DATASET_REVISION = "e3b30257c4d6be5438ea19f0989ac82c24234fe4"


def parse_conversations(path: Path, limit: int, seed: int = 0) -> list[list[str]]:
    if limit <= 0:
        raise ValueError(f"limit must be positive, got {limit}")
    convs: list[list[str]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            raw = row.get("Multi-turn conversation", "")
            try:
                msgs = ast.literal_eval(raw)
            except (ValueError, SyntaxError) as exc:
                raise ValueError(f"invalid conversation at {path}:{row_number}") from exc
            if not isinstance(msgs, list):
                raise ValueError(f"conversation must be a list at {path}:{row_number}")
            user_turns = [
                m["content"]
                for m in msgs
                if isinstance(m, dict) and m.get("role") == "user" and m.get("content")
            ]
            if len(user_turns) >= 2:
                convs.append(user_turns)
    if not convs:
        raise ValueError(f"no valid multi-turn conversations found in {path}")
    if len(convs) <= limit:
        return convs
    return random.Random(seed).sample(convs, limit)


def trace_flagged(detector, turns: list[str], inter_query: bool) -> bool:
    history: list[Turn] = []
    for content in turns:
        turn = Turn(role="user", content=content, is_attack=True)
        hist = history if inter_query else []
        if detector.detect_turn(turn, hist).detected:
            return True
        history.append(turn)
    return False


def evaluate(detector, convs: list[list[str]], inter_query: bool) -> float:
    if not convs:
        raise ValueError("cannot evaluate an empty conversation set")
    hits = sum(trace_flagged(detector, c, inter_query) for c in convs)
    return hits / len(convs)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--harmful", type=Path, required=True)
    ap.add_argument("--benign", type=Path, required=True)
    ap.add_argument("--n", type=int, default=400, help="conversations per split")
    ap.add_argument("--seed", type=int, default=0, help="deterministic sampling seed")
    args = ap.parse_args()

    harmful = parse_conversations(args.harmful, args.n, args.seed)
    benign = parse_conversations(args.benign, args.n, args.seed)
    print(f"external harmful conversations: {len(harmful)}   benign: {len(benign)}\n")

    report = {"dataset": "tom-gibbs/multi-turn_jailbreak_attack_datasets (HuggingFace)",
              "dataset_revision": DATASET_REVISION,
              "harmful_input_sha256": hashlib.sha256(args.harmful.read_bytes()).hexdigest(),
              "benign_input_sha256": hashlib.sha256(args.benign.read_bytes()).hexdigest(),
              "sampling_seed": args.seed,
              "n_harmful": len(harmful), "n_benign": len(benign), "detectors": {}}
    print(f"{'detector':12s} {'SQ recall':>10s} {'IQ recall':>10s} {'gain':>7s} "
          f"{'SQ FPR':>8s} {'IQ FPR':>8s}")
    print("-" * 60)
    for name in list_detectors():
        det = get_detector(name)
        sq_r = evaluate(det, harmful, inter_query=False)
        iq_r = evaluate(det, harmful, inter_query=True)
        sq_f = evaluate(det, benign, inter_query=False)
        iq_f = evaluate(det, benign, inter_query=True)
        report["detectors"][name] = {
            "single_query_recall": round(sq_r, 3), "inter_query_recall": round(iq_r, 3),
            "recall_gain": round(iq_r - sq_r, 3),
            "single_query_fpr": round(sq_f, 3), "inter_query_fpr": round(iq_f, 3),
        }
        print(f"{name:12s} {sq_r:10.3f} {iq_r:10.3f} {iq_r - sq_r:+7.3f} {sq_f:8.3f} {iq_f:8.3f}")

    out = HERE / "results" / "external_multiturn_validation.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
