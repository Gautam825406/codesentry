# CodeSentry

**Agentic secure code review + codebase RAG.** CodeSentry indexes a repository
by its structure — tree-sitter AST symbols and a call graph, not raw text —
reviews pull-request diffs with full codebase context, and posts only
evidence-cited, confidence-filtered findings: security issues mapped to CWE
and OWASP, logic bugs, and a suggested fix as a patch — then learns from every
accepted and rejected comment.

> Built for an AI Engineer / Generative AI Engineer portfolio. Designed to
> demonstrate AST-aware retrieval, multi-agent review, secure tool use,
> evaluation against labelled pull requests, and LoRA fine-tuning from human
> feedback — not a generic chatbot pointed at code.

## The demo in one paragraph

Open PR #42 on the sample shop API. `get_order` interpolates caller-supplied
`order_id` into SQL and hands it to `run_query` — whose body, in a different
file, executes it. The diff never shows the sink. CodeSentry retrieves the
callee through the call graph and posts a **CWE-89 SQL injection (high,
confidence 0.94)** with a validated parameterised patch — and the CI check
**fails**, blocking merge. That is the product's core claim, and it is
reproducible with one command (below).

## Features

- **AST-aware indexing** — tree-sitter (Python, JavaScript, TypeScript) into
  functions/methods/classes with signatures, docstrings, imports and calls;
  incremental re-indexing by content hash; call graph with unresolved edges
  tracked, never invented.
- **Graph-first retrieval** — changed symbol → callers → callees → tests →
  vector-similar, inside a per-symbol token budget, with dropped context logged.
- **LangGraph multi-agent review** — security, logic and style agents returning
  Pydantic-validated findings; deterministic rule engine works with **no LLM
  key**; Groq (hosted) and Ollama (local) are optional.
- **Citation enforcement** — no finding is posted without a verified file/line
  and quoted evidence; security findings need a valid CWE id; low-confidence
  and duplicate findings are suppressed and logged with a reason.
- **Patch suggestions** — GitHub suggestion format, validated by parsing the
  patched file (`compile()` for Python); invalid patches are withheld.
- **Scanners** — secret scanning (masked values only) and OSV dependency
  scanning (real API; honest "unavailable" when unreachable).
- **CI merge gating** — GitHub check runs; critical/high block merge until
  fixed or dismissed by an authorised reviewer (dismissals are audited).
- **Human feedback loop** — accept / fixed / reject-wrong / reject-not-worth-
  fixing / ignore, driving the quality dashboard and a versioned LoRA dataset
  (training opt-in, off by default; promotion gated on held-out evaluation).
- **Quality dashboard** — precision, false-positive rate, findings by CWE /
  agent / severity, latency and cost — all computed from persisted data.

## Architecture

```mermaid
flowchart LR
    GH[GitHub App] --> WH[Webhook receiver\nHMAC verify + dedup]
    WH --> Q[Redis + Celery\n(or thread fallback)]
    Q --> IDX[Indexer\ntree-sitter symbols + call graph]
    IDX --> DB[(PostgreSQL\nSQLite fallback)]
    Q --> REV[Review pipeline]
    REV --> RET[Graph-first retrieval]
    RET --> LG[LangGraph\nsecurity / logic / style]
    LG --> FLT[Filter\ncitation, confidence, CWE, dedup]
    FLT --> PT[Patch validation]
    PT --> GH2[GitHub comments\n+ check run gate]
    FLT --> FEED[Human feedback]
    FEED --> DS[Versioned dataset]
    DS --> LORA[LoRA train / evaluate\npromote / rollback]
```

## Quick start

```bash
git clone <repo> && cd codesentry
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
cd frontend && npm install && npm run dev   # http://localhost:5173
```

**One-command demo (no GitHub, no keys):**

```bash
python scripts/demo_review.py
# or: curl -X POST http://localhost:8000/api/demo/seed
```

**Docker Compose (full stack — api, worker, redis, postgres+pgvector, frontend):**

```bash
docker compose up --build
```

## Evaluation (measured, not asserted)

Run: `python evals/run_eval.py` → `evals/reports/eval_report.md`.
Labelled set v1: **N = 8 PRs, 7 expected findings** (seeded vulns, clean PR,
prompt-injection PR, oversized PR, renamed-symbol PR).

| Metric | Measured value |
|---|---|
| Precision | **1.00** (7 TP / 7 posted) |
| Recall | **1.00** (7 TP / 7 expected) |
| False-positive rate | **0.00** |
| Median review latency | **24 ms** (local, deterministic engine) |
| Mean cost per PR | **$0.00** (no LLM calls in this mode) |

Read this honestly: N = 8 is small. 1.00 on 8 hand-picked cases proves the
pipeline works end to end; it is not a production precision claim. Grow the
labelled set before quoting these numbers anywhere else. Full discussion in
`docs/EVALUATION.md`.

## Tests

```bash
python -m pytest tests/ -q        # 35 tests: unit + integration + eval
```

## Environment variables

See `.env.example`. The only ones that matter for the demo are none — the
deterministic engine runs with no keys. For production set at minimum
`CODESENTRY_JWT_SECRET` (long random value — the dev default is insecure),
`GITHUB_WEBHOOK_SECRET`, and `DATABASE_URL` (Postgres). `GROQ_API_KEY` is
optional.

## What it will not do

- No auto-merge and no auto-apply of patches. Humans decide.
- No claim of complete security coverage. Absence of a finding is not proof
  of safety.
- Taint analysis in v1 is heuristic hints, not a verified data-flow proof.
- Python and JavaScript/TypeScript only in v1.
- No training on private code without explicit admin opt-in (default off).
- GitHub posting uses a PAT (`GITHUB_TOKEN`) in v1; App installation-token
  exchange is the documented hardening step.
- Embeddings are deterministic hash vectors by default (not semantic);
  sentence-transformers is optional, pgvector is the documented scale path.

## Limitations (found while building)

- Docker Compose was **not** executed in the build environment (Docker is not
  installed there); the compose file was validated for YAML syntax only.
- LoRA training has not run: no GPU in the build environment, and no feedback
  dataset exists yet. The dataset builder, orchestration, evaluation gate and
  promote/rollback are implemented and honest about their state.
- OSV scanning needs network access; when unreachable it reports
  `unavailable`, never guesses.
- The worker uses Celery+Redis when configured and an in-process thread queue
  otherwise; the thread fallback is what the demo uses.

## Roadmap

- App installation-token exchange (replace PAT); per-installation rate limits.
- sentence-transformers embeddings by default + pgvector retrieval.
- Larger labelled set (historical bug-fixing PRs) and per-CWE recall table.
- Qdrant migration path for large symbol counts; worker sharding by repository.
- Rate limiting on the API; encrypted storage for GitHub credentials.

## Docs

`docs/ARCHITECTURE.md` · `docs/DATABASE.md` · `docs/API.md` ·
`docs/GITHUB_SETUP.md` · `docs/DEPLOYMENT.md` · `docs/SECURITY.md` ·
`docs/EVALUATION.md` · `docs/AI_AGENTS.md` · `docs/CONTRIBUTING.md`
