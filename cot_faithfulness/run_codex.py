#!/usr/bin/env python3
"""Run the blind CoT-faithfulness prompt pack through Codex-backed models.

Each prompt is a new Codex invocation. This preserves the paired-task design: the model sees one
ordinary multiple-choice prompt at a time, never the answer key, the paired variant, or the
faithfulness-study framing. The reply is retained verbatim as the chain-of-thought field.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ANSWER_RE = re.compile(r"ANSWER:\s*([A-Da-d])", re.I)


def parse_answer(text: str) -> str:
    matches = ANSWER_RE.findall(text or "")
    return matches[-1].upper() if matches else ""


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    if not slug:
        raise ValueError("model name must contain an alphanumeric character")
    return slug


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", default="high", choices=["low", "medium", "high"])
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--logs-dir", type=Path, default=None)
    args = parser.parse_args(argv[1:])

    prompts = [
        json.loads(line)
        for line in (HERE / "prompts.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    model_slug = safe_slug(args.model)
    out_path = args.out or HERE / f"runs_{model_slug}.jsonl"
    logs_dir = args.logs_dir or HERE / f"logs_codex_{model_slug}"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as handle:
        for index, prompt in enumerate(prompts, start=1):
            command = [
                args.codex_bin,
                "exec",
                "-m",
                args.model,
                "-c",
                f'model_reasoning_effort="{args.effort}"',
                "-C",
                str(HERE.parent),
                "--skip-git-repo-check",
                "--ephemeral",
                "-",
            ]
            result = subprocess.run(
                command,
                input=prompt["prompt"],
                capture_output=True,
                text=True,
                check=False,
            )
            log_path = logs_dir / f"{index:02d}_{prompt['id']}_{prompt['condition']}.log"
            log_path.write_text(
                f"command: {' '.join(command)}\nexit_code: {result.returncode}\n\n"
                f"stderr:\n{result.stderr}\n",
                encoding="utf-8",
            )
            if result.returncode:
                print(f"{prompt['id']} {prompt['condition']}: Codex exited {result.returncode}", file=sys.stderr)
                return result.returncode
            reply = result.stdout
            answer = parse_answer(reply)
            if not answer:
                raise ValueError(f"model reply has no ANSWER line for {prompt['id']} {prompt['condition']}")
            row = {
                "id": prompt["id"],
                "condition": prompt["condition"],
                "answer": answer,
                "cot": reply,
            }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"{index:02d}/{len(prompts)} {prompt['id']} {prompt['condition']} -> {row['answer'] or '?'}")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
