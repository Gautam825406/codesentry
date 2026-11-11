# CodeSentry Evaluation Report

Dataset: `v1` — 8 labelled PRs (7 expected findings).
Measured by `evals/run_eval.py` through the real review pipeline (deterministic rule engine, no LLM key). Cost is $0.00 in this mode because no LLM calls are made; Groq cost would appear here when enabled.

## Overall (all cases)

- Precision: **1.0**  (TP 7 / posted 7)
- Recall: **1.0**  (TP 7 / expected 7)
- False-positive rate: **0.0**
- Median review latency: **25 ms** (local, deterministic engine)
- Mean cost per PR: **$0.0**

## Per case

| case | kind | precision | recall | posted | expected | latency ms | gate | status |
|---|---|---|---|---|---|---|---|---|
| seeded-sqli-py | seeded_vuln | 1.0 | 1.0 | 2 | 2 | 57 | fail | completed |
| seeded-sqli-js | seeded_vuln | 1.0 | 1.0 | 1 | 1 | 23 | fail | completed |
| seeded-command-injection | seeded_vuln | 1.0 | 1.0 | 1 | 1 | 22 | fail | completed |
| seeded-pickle | seeded_vuln | 1.0 | 1.0 | 1 | 1 | 25 | fail | completed |
| clean-pr | clean | 1.0 | 1.0 | 0 | 0 | 16 | pass | completed |
| prompt-injection | adversarial | 1.0 | 1.0 | 1 | 1 | 24 | fail | completed |
| oversized-pr | oversized | 1.0 | 1.0 | 0 | 0 | 333 | pass | partial |
| renamed-symbol | renamed | 1.0 | 1.0 | 1 | 1 | 27 | fail | completed |

## Honest notes

- Categories with zero recall are named here, not averaged away: none — every seeded category was caught at least once.
- The clean-PR case measures false positives: any posted finding there is a false positive.
- The prompt-injection case passes only if the real SQL injection is still posted despite the injected instruction.
- The oversized-PR case passes only if the run reports `partial` status with skipped files disclosed.
- Patch validity is enforced by construction (invalid patches are withheld); this run does not separately measure patch applicability on a larger set — that needs more labelled patches.
- No LoRA fine-tuning has been run: there is no before/after false-positive comparison yet.
