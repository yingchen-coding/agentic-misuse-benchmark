"""Run the weak trusted-monitor probe through Codex-backed models."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANSWER_RE = re.compile(r"\b(ALLOW|BLOCK)\b", re.I)


def parse_answer(text: str) -> str:
    matches = ANSWER_RE.findall(text or "")
    return matches[-1].upper() if matches else ""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True)
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high"])
    ap.add_argument("--codex-bin", default="/opt/homebrew/bin/codex")
    ap.add_argument("--prompts", type=Path, default=HERE / "prompts.jsonl")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--logs-dir", type=Path, default=None)
    ap.add_argument("--retries", type=int, default=3)
    args = ap.parse_args(argv[1:])

    prompts = [json.loads(line) for line in args.prompts.read_text(encoding="utf-8").splitlines() if line.strip()]
    model_slug = args.model.replace("/", "-")
    out_path = args.out or HERE / f"runs_{model_slug}.jsonl"
    logs_dir = args.logs_dir or HERE / f"logs_codex_{model_slug}"
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
            result = None
            for attempt in range(1, args.retries + 1):
                result = subprocess.run(
                    command,
                    input=prompt["prompt"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                log_path = logs_dir / f"{index:02d}_{prompt['id']}_{prompt['view']}.log"
                log_path.write_text(
                    f"command: {' '.join(command)}\nattempt: {attempt}\nexit_code: {result.returncode}\n\n"
                    f"stderr:\n{result.stderr}\n",
                    encoding="utf-8",
                )
                if result.returncode == 0:
                    break
                if attempt < args.retries:
                    time.sleep(min(5 * attempt, 15))
            if result is None or result.returncode:
                print(
                    f"{prompt['id']} {prompt['view']}: Codex exited {result.returncode if result else 'unknown'}",
                    file=sys.stderr,
                )
                return result.returncode if result else 1
            row = {
                "id": prompt["id"],
                "view": prompt["view"],
                "decision": parse_answer(result.stdout),
                "raw": result.stdout,
            }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
