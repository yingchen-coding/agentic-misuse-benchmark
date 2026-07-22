"""Generic runner: feed the blind prompt pack to a chat model, save answers in the scoring schema.

Model-agnostic by design. Point it at any OpenAI-compatible endpoint (set OPENAI_API_KEY, and
OPENAI_BASE_URL if using a proxy). It reads cot_faithfulness/prompts.jsonl, sends each prompt, parses
the required `ANSWER: <letter>` line, and writes cot_faithfulness/runs_<model>.jsonl with the full
reply as `cot`. No answer key is ever sent to the model.

Run:  OPENAI_API_KEY=... python3 cot_faithfulness/run_openai.py --model gpt-4o-mini
      OPENAI_API_KEY=... python3 cot_faithfulness/run_openai.py --model gpt-4o

Then score every model together:
      python3 cot_faithfulness/score.py cot_faithfulness/runs_*.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--out", default=None, help="defaults to runs_<model>.jsonl")
    args = ap.parse_args(argv[1:])

    try:
        from openai import OpenAI  # imported here so score.py has no API dependency
    except ImportError:
        raise RuntimeError("run_openai.py requires the optional 'openai' package")
    client = OpenAI()

    prompts = [
        json.loads(x)
        for x in (HERE / "prompts.jsonl").read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    out_path = Path(args.out) if args.out else HERE / f"runs_{safe_slug(args.model)}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for p in prompts:
            resp = client.chat.completions.create(
                model=args.model,
                temperature=args.temperature,
                messages=[{"role": "user", "content": p["prompt"]}],
            )
            reply = resp.choices[0].message.content or ""
            answer = parse_answer(reply)
            if not answer:
                raise ValueError(f"model reply has no ANSWER line for {p['id']} {p['condition']}")
            row = {"id": p["id"], "condition": p["condition"],
                   "answer": answer, "cot": reply}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"{p['id']:4s} {p['condition']:7s} -> {row['answer'] or '?'}")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
