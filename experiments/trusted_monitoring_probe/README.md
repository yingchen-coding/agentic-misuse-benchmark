# Trusted Monitoring Probe

Weak frozen model monitor over agent traces for the second-wave Anthropic paper slot:
monitor collusion / prompt laundering.

The prompt pack has two views:

- `raw`: original agent text
- `laundered`: the same text with dangerous surface forms normalized

The ground truth comes from the hidden provenance label and confirmation state in `tasks.jsonl`.
The model only sees tool, confirmation, and agent text.
