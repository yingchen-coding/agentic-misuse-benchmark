"""External validation on AdvBench --- a real, third-party harmful-behavior benchmark.

The most common reviewer objection to this repo is that its 25 scenarios are self-authored. This
script answers it directly: it runs the SAME bundled detectors (rules, classifier, intent) against
AdvBench (Zou et al., 2023, "Universal and Transferable Adversarial Attacks on Aligned Language
Models" --- the GCG paper), 520 harmful instructions that this project did not write. AdvBench
items are single-turn harmful *goals* ("Write a script that can exploit ...", "Develop
a strategy for hacking into a government database ..."), so this measures the detectors' single-turn
recall on real external attack prompts, alongside their false-positive rate on a matched set of
benign instructions.

AdvBench has no benign split, so for FPR we compare it with benign turns from this repo's 25
scenarios (ground-truth is_attack == False) plus the four long benign hard-negative conversations.

Data: fetched from https://github.com/llm-attacks/llm-attacks (advbench/harmful_behaviors.csv).
Run:  python3 analysis/external_advbench_validation.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from detectors import get_detector, list_detectors  # noqa: E402
from scenarios import get_all_scenarios  # noqa: E402
from scenarios.base import Turn  # noqa: E402

HERE = Path(__file__).resolve().parent
DATASET_REVISION = "098262edf85f807224e70ecd87b9d83716bf6b73"


def load_advbench(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    goals = [row["goal"].strip() for row in rows if row.get("goal", "").strip()]
    if not goals:
        raise ValueError(f"no AdvBench goals found in {path}")
    return goals


def load_benign_turns() -> list[str]:
    """Benign instructions: the benign user turns from the 25 scenarios + hard-negative traces."""
    benign: list[str] = []
    for s in get_all_scenarios():
        for t in s.turns:
            if not t.is_attack and t.role == "user":
                benign.append(t.content)
    hn = HERE / "hard_negatives"
    if hn.exists():
        for f in sorted(hn.glob("trace_*.json")):
            for r in json.loads(f.read_text(encoding="utf-8")):
                if r.get("speaker") == "user":
                    benign.append(r["content"])
    return benign


def score(detector, texts: list[str]) -> int:
    """How many of these single-turn texts the detector flags (empty history)."""
    if not texts:
        raise ValueError("texts to score must not be empty")
    flagged = 0
    for text in texts:
        turn = Turn(role="user", content=text, is_attack=True)
        if detector.detect_turn(turn, []).detected:
            flagged += 1
    return flagged


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--advbench",
        type=Path,
        default=HERE / "external_data" / "advbench_harmful_behaviors.csv",
    )
    args = ap.parse_args()

    attacks = load_advbench(args.advbench)
    benign = load_benign_turns()
    if not benign:
        raise ValueError("no benign comparison instructions found")
    print(f"AdvBench harmful goals: {len(attacks)}   benign instructions: {len(benign)}\n")

    report = {"dataset": "AdvBench (Zou et al. 2023)", "dataset_revision": DATASET_REVISION,
              "input_sha256": hashlib.sha256(args.advbench.read_bytes()).hexdigest(),
              "n_attacks": len(attacks),
              "n_benign": len(benign), "detectors": {}}
    for name in list_detectors():
        det = get_detector(name)
        tp = score(det, attacks)
        fp = score(det, benign)
        recall = tp / len(attacks)
        fpr = fp / len(benign)
        report["detectors"][name] = {"recall": round(recall, 3), "fpr": round(fpr, 3),
                                     "caught": tp, "false_positives": fp}
        print(f"{name:12s} external recall {recall:.3f} ({tp}/{len(attacks)})   "
              f"benign FPR {fpr:.3f} ({fp}/{len(benign)})")

    out = HERE / "results" / "external_advbench_validation.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
