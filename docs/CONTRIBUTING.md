# Contributing

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
python -m pytest tests/ -q
python evals/run_eval.py
```

## Rules

- Every finding must carry verifiable evidence. Never post an uncited finding.
- Security findings need a valid CWE id from `agents/schemas.py::CWE`.
- Patches must parse (validated with `compile()` for Python) and stay inside
  the finding's lines, or be withheld.
- Dashboard metrics must come from persisted data. Never hardcode a number.
- Add a labelled eval case (in `evals/datasets/labelled.json`) when you add a
  new finding rule — including a clean case that must stay silent.
- No secrets in code, tests, or fixtures. Run the CI secret grep locally.
- Keep the deterministic engine working with no keys: the demo and the eval
  must pass with `LLM_PROVIDER=deterministic`.
- If you change the parser or the graph, run the full suite + the eval and
  update `evals/reports/eval_report.md` with the re-measured numbers.
