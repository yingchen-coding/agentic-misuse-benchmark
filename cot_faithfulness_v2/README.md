# CoT Faithfulness v2 — Harder Task Set, Same Null Result

Follow-up to `../cot_faithfulness/`. That first pilot used 15 famous textbook riddles (bat-and-ball,
lily pad, sheep problem) — the kind every frontier model has seen thousands of times in training —
and found a ceiling result (all models 100% accurate, never swayed by the planted wrong hint). The
open question was whether the null result was real or an artifact of picking questions models have
memorized so hard no hint could move them.

## What changed

15 new items (`tasks.jsonl`), deliberately avoiding famous riddles:
- Non-canonical arithmetic (17×23, jacket discount, marble jar, depreciation, recipe scaling,
  binary addition) — verified directly rather than relying on model responses.
- Less-memorized trivia (atomic number 42, fastest-rotating planet, opera composer, longest
  coastline, moon counts) — picked for being real, stable facts, not classic AI-riddle-benchmark
  questions.

## Results

Recorded runs on Haiku 4.5, Sonnet 5, and two GPT tiers used the same prompts as v1. GPT prompts
were run in separate fresh subprocesses with no answer key or paired condition. Claude runs were
collected in-session and are reported as upper-bound pilot evidence.

| Model | Neutral Acc | Hint Acc | Sycophancy | Unfaithful |
|---|---:|---:|---:|---:|
| Claude Haiku 4.5 | 1.00 | 1.00 | 0.00 | 0.00 |
| Claude Sonnet 5 | 1.00 | 1.00 | 0.00 | 0.00 |
| GPT (via codex, larger tier) | 1.00 | 1.00 | 0.00 | 0.00 |
| GPT (via codex, mini/weaker tier) | 1.00 | 1.00 | 0.00 | 0.00 |

The fourth run specifically targets a weaker/cheaper tier — the model class most likely to show
sycophancy if the effect exists at all — and it also came back clean.

**Combined with v1: 7 model/task-set runs, 210 prompt responses (105 neutral/hint pairs), zero
sycophancy, and zero unfaithful CoT.** The three GPT runs used separate fresh subprocesses for each
prompt. The four Claude runs were collected in-session and should be treated as upper-bound pilot
evidence, not fully blind replications. The result is a reproducible null for this probe, not proof
that the model families are generally faithful.

## Honest interpretation

This is not "these models are provably faithful" — it's "this specific pressure mechanism (a single
line: 'a colleague I trust said X') doesn't move current frontier-tier models on well-defined
factual/arithmetic questions." To find a discriminating signal, the next lever isn't a harder
*answer* — accuracy is already not the bottleneck — it's a stronger or different *pressure*
mechanism: repeated pushback across turns, appeal to authority/deadline stakes, or genuinely
contestable/subjective questions where there's no clean verifiable answer for the model to fall
back on. A single-shot "colleague hint" appears too weak a lever for these model tiers.

## Reproduce

```
python3 make_prompts.py > prompts.jsonl
python3 run_codex.py --model <model> --effort high   # for OpenAI-family via codex
python3 score.py runs_*.jsonl
```
