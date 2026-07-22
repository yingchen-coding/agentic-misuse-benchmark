# External datasets (not authored by this project)

- `advbench_harmful_behaviors.csv` — AdvBench, 520 harmful behaviors.
  Source: Zou, Wang, Kolter, Fredrikson, "Universal and Transferable Adversarial Attacks on
  Aligned Language Models" (2023). https://github.com/llm-attacks/llm-attacks
  Used by `analysis/external_advbench_validation.py` for external-distribution validation.
  Source revision: `098262edf85f807224e70ecd87b9d83716bf6b73`.

- `tom-gibbs/multi-turn_jailbreak_attack_datasets` (HuggingFace) — real multi-turn cipher-style
  jailbreak conversations, Harmful (4136) + Completely-Benign (1200) splits. Not vendored here (large);
  fetch from HF. Used by `analysis/external_multiturn_validation.py` (sampled 400/400) for
  external multi-turn validation of the inter-query claim.
  Source revision: `e3b30257c4d6be5438ea19f0989ac82c24234fe4`.

- `SafeMTData` (HuggingFace `SafeMTData/SafeMTData`, Attack_600) — Ren et al., "Derail Yourself:
  Multi-turn LLM Jailbreak Attack through Self-discovered Clues" (2024 preprint). 600 multi-turn
  attacks decomposing one harmful goal into innocuous turns. Not vendored (fetch from HF). Used by
  `analysis/inter_query_mechanism_safemt.py` (embedding aggregation study, all-MiniLM-L6-v2).
  Source revision: `04af7bd0b6b6044e797e936d79674e348316b9b8`.

## AdvBench license notice

MIT License

Copyright (c) 2023 Andy Zou

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT
OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
