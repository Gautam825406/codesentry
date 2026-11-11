# Evaluation

## Method

`evals/run_eval.py` runs every case in `evals/datasets/labelled.json` through
the **real** review pipeline (index → retrieve → LangGraph agents → filter →
patch validation) on an isolated temp DB, then compares posted findings with
hand-labelled expected findings (match = same file, line within ±2, same
category). The report is written to `evals/reports/eval_report.md`.

The labelled set (v1, **N = 8 PRs, 7 expected findings**) deliberately includes:

| Case | Kind | Why it is there |
|---|---|---|
| seeded-sqli-py | seeded vuln | SQLi whose sink is in a callee — only graph retrieval finds it |
| seeded-sqli-js | seeded vuln | JS template-literal SQLi |
| seeded-command-injection | seeded vuln | `os.system` with interpolated input |
| seeded-pickle | seeded vuln | unsafe deserialisation |
| clean-pr | clean | measures false positives (a set of only buggy PRs rewards flagging everything) |
| prompt-injection | adversarial | injected instruction + a real SQLi — the finding must survive |
| oversized-pr | oversized | 250 files — must report `partial` with skipped files disclosed |
| renamed-symbol | renamed | sink callee renamed — retrieval must follow the rename |

## Measured results (run 2026-11-11, deterministic engine, no LLM key)

| Metric | Value | N |
|---|---|---|
| Precision | **1.00** (7 TP / 7 posted) | 8 PRs |
| Recall | **1.00** (7 TP / 7 expected) | 8 PRs |
| False-positive rate | **0.00** | 8 PRs |
| Median review latency | **24 ms** (local, deterministic engine) | 8 PRs |
| Mean cost per PR | **$0.00** (no LLM calls in this mode) | 8 PRs |

Per-case results are in `evals/reports/eval_report.md`. Every seeded
category was caught at least once; there are no zero-recall categories in
this run.

## Read this honestly

- **N = 8 is small.** 1.00 precision/recall on 8 hand-picked cases is evidence
  the pipeline works end to end — it is not a production precision claim.
  Grow the labelled set before quoting these numbers anywhere else.
- Latency is local and deterministic-engine only; Groq/Ollama reviews will be
  slower and costed per PR (recorded on each run).
- Patch validity is enforced by construction (invalid patches are withheld);
  patch *applicability* on a larger set is not yet measured.
- No LoRA fine-tuning has been run, so there is no before/after
  false-positive comparison yet. That comparison is gated on real feedback
  data and a GPU host.
- During development the pickle case initially had recall 0.0 (the rule
  required an interpolated variable where a direct parameter is itself the
  vulnerability) and the demo case had precision 0.5 (the labelled set had
  not listed the real logic bug the PR also introduces). Both were fixed in
  the code / labelling and the report re-measured — the history is in the
  eval report's "honest notes" approach, not hidden.
