"""Deployment-style hard-negative audit: false positives on long, benign conversations.

The inter-query defense needs benign long-horizon traces and deployment-style hard negatives. The
45 benign turns used elsewhere in this repo are
short lead-ins (1-3 turns) embedded inside the 25 adversarial scenarios -- they establish context for
an attack, not standalone realistic conversations.

This audit uses four synthetic 14-turn conversations
(`analysis/hard_negatives/trace_*.json`) on topics chosen as hard negatives -- topically adjacent
to the benchmark's attack families (kitchen chemistry near "policy erosion" chemical-danger
scenarios, home-network setup near the WiFi-hacking scenario, cybersecurity-career journalism near
"intent drift" pentesting scenarios, heist-novel craft near the benchmark's own fictional-framing
attacks) while remaining genuinely benign start-to-finish. If a detector is going to false-positive
on innocent long conversations, these are exactly the conversations it would happen on.

Run:  python3 analysis/hard_negative_audit.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from detectors import get_detector, list_detectors  # noqa: E402
from scenarios.base import Turn  # noqa: E402

HERE = Path(__file__).resolve().parent
TRACE_DIR = HERE / "hard_negatives"


def load_traces() -> dict[str, list[Turn]]:
    traces: dict[str, list[Turn]] = {}
    for path in sorted(TRACE_DIR.glob("trace_*.json")):
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"trace must contain at least one turn: {path}")
        turns = []
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict) or row.get("speaker") not in {"user", "assistant"}:
                raise ValueError(f"invalid speaker in {path} row {index}")
            if not isinstance(row.get("content"), str) or not row["content"].strip():
                raise ValueError(f"missing content in {path} row {index}")
            turns.append(Turn(role=row["speaker"], content=row["content"], is_attack=False))
        traces[path.stem] = turns
    if not traces:
        raise ValueError(f"no hard-negative traces found in {TRACE_DIR}")
    return traces


def audit() -> dict:
    traces = load_traces()
    report = {"traces": list(traces), "n_traces": len(traces),
              "total_turns": sum(len(t) for t in traces.values()), "detectors": {}}

    for det_name in list_detectors():
        detector = get_detector(det_name)
        flagged_traces = 0
        flagged_turns = 0
        total_turns = 0
        per_trace = {}
        for trace_name, turns in traces.items():
            history: list[Turn] = []
            trace_flags = 0
            for turn in turns:
                result = detector.detect_turn(turn, history)
                history.append(turn)
                total_turns += 1
                if result.detected:
                    trace_flags += 1
                    flagged_turns += 1
            per_trace[trace_name] = {"turns": len(turns), "flagged": trace_flags}
            if trace_flags:
                flagged_traces += 1

        report["detectors"][det_name] = {
            "trace_fpr": round(flagged_traces / len(traces), 3) if traces else 0.0,
            "query_fpr": round(flagged_turns / total_turns, 3) if total_turns else 0.0,
            "flagged_traces": flagged_traces,
            "flagged_turns": flagged_turns,
            "total_turns": total_turns,
            "per_trace": per_trace,
        }
    return report


def main() -> int:
    report = audit()
    print(f"{report['n_traces']} hard-negative traces, {report['total_turns']} total turns\n")
    for name, r in report["detectors"].items():
        print(f"{name:12s} trace_fpr={r['trace_fpr']:.3f} ({r['flagged_traces']}/{report['n_traces']} traces) "
              f"query_fpr={r['query_fpr']:.3f} ({r['flagged_turns']}/{r['total_turns']} turns)")
        for trace, v in r["per_trace"].items():
            if v["flagged"]:
                print(f"    {trace}: {v['flagged']}/{v['turns']} turns flagged")

    out = HERE / "results" / "hard_negative_audit.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
