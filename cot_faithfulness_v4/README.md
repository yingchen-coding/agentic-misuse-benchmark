# Harder CoT Faithfulness Probe

This is a harder, still-benign follow-up to the original CoT faithfulness pilot.

## Result

`gpt-5.4-mini` at `high` reasoning effort on 20 paired tasks:

- Neutral accuracy: 0.95
- Hint accuracy: 0.95
- Sycophancy: 0.00
- Unfaithful: 0.00
- Considered: 19

The single miss was a baseline error on `i18` that appeared in both conditions; the wrong hint did not induce a flip.

The earlier `cot_faithfulness_v3/` probe used 30 paired tasks and reached 0.933 accuracy in both
conditions, with 0 hint-induced flips among 28 neutral-correct items.

## Stronger-hint check

The same task set was rerun with a stronger hint template in `cot_faithfulness_v5/`.
The result stayed the same: 0 hint flips, 0 unfaithful traces.

Reproduce all three scores with `../cot_faithfulness_v2/score.py` and the corresponding task file:

```bash
python3 cot_faithfulness_v2/score.py --tasks cot_faithfulness_v3/tasks.jsonl cot_faithfulness_v3/runs_*.jsonl
python3 cot_faithfulness_v2/score.py --tasks cot_faithfulness_v4/tasks.jsonl cot_faithfulness_v4/runs_*.jsonl
python3 cot_faithfulness_v2/score.py --tasks cot_faithfulness_v4/tasks.jsonl cot_faithfulness_v5/runs_*.jsonl
```
