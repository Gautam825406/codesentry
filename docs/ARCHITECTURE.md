# Architecture

## System shape

CodeSentry is a modular monolith API plus asynchronous workers — the simplest
shape that survives a 200-file PR, a provider outage, and a redelivered webhook.

```mermaid
flowchart LR
    GH[GitHub App] --> WH[Webhook receiver\nHMAC verify + dedup]
    WH --> Q[Redis + Celery\n(or thread fallback)]
    Q --> IDX[Indexer\ntree-sitter symbols + call graph]
    IDX --> DB[(PostgreSQL\nSQLite fallback)]
    Q --> REV[Review pipeline]
    REV --> RET[Graph-first retrieval\ncallers, callees, tests, vectors]
    RET --> LG[LangGraph\nsecurity / logic / style]
    LG --> FLT[Filter\ncitation, confidence, CWE, dedup]
    FLT --> PT[Patch validation]
    PT --> GH2[GitHub comments\n+ check run gate]
    FLT --> FEED[Human feedback]
    FEED --> DS[Versioned dataset]
    DS --> LORA[LoRA train / evaluate\npromote / rollback]
```

## Data flow (one review)

1. Webhook arrives: signature verified (HMAC SHA-256), delivery ID deduplicated,
   job enqueued, `200` returned in milliseconds. Nothing expensive runs here.
2. Worker fetches the diff, incrementally indexes changed files (content hash),
   maps hunks to symbols.
3. For each changed symbol, context is assembled graph-first (changed symbol →
   callers → callees → tests → vector-similar) inside a per-symbol token budget;
   included and dropped pieces are recorded.
4. LangGraph fans out to three agents; each returns Pydantic-validated findings.
5. The filter enforces the finding contract; scanners (secrets, OSV) merge in
   with their own provenance.
6. Findings are persisted, the CI gate is computed, and (when a token is
   configured) a review + check run are posted to GitHub.

## Key decisions

- **Symbols, not text chunks.** Tree-sitter parses Python/JS/TS into functions,
  methods and classes. Embeddings are computed per symbol. If tree-sitter is
  unavailable the stdlib `ast` (Python) / regex (JS/TS) fallback is used and
  `GET /health` reports which parser is actually running.
- **Embeddings are hash-based by default** (dim 128, deterministic). They are
  NOT semantic embeddings and are never presented as such. Set
  `EMBEDDING_PROVIDER=sentence-transformers` to use all-MiniLM-L6-v2 when
  installed. pgvector is the documented scale path (migration `0002`).
- **Deterministic rule engine by default.** The three agents run a real,
  tested rule engine with no LLM key. Groq (`GROQ_API_KEY`) or Ollama
  (`OLLAMA_HOST`) add LLM findings on top; model output is still validated
  against the finding schema and citation-checked.
- **Repository scoping is enforced in queries**, not filtered afterwards:
  retrieval, findings and feedback are all `WHERE repo_id = ?`.
- **Repository code is untrusted data.** Prompts quote it inside a data block;
  injection markers are stripped and logged; a suppression request inside code
  is an evaluation case, never an instruction.

## Module map (PRD §15)

| Path | Contents |
|---|---|
| `apps/api` | FastAPI app, auth, all endpoints |
| `apps/worker` | Celery app/tasks + thread-fallback queue |
| `indexer/` | tree-sitter parsing, symbol extraction, call graph, embeddings, incremental indexing, diff parsing |
| `agents/` | LangGraph graph, 3 agents, finding schema, filter, patches, LLM bridge |
| `retrieval/` | graph-first context builder, vector retriever |
| `scanners/` | secret scanner, OSV dependency scanner |
| `training/` | feedback → dataset builder, LoRA orchestration, evaluation metrics |
| `database/` | SQLAlchemy models, session, Alembic migrations |
| `evals/` | labelled dataset, runner, reports |
| `fixtures/` | sample repository used by the demo + evals |
| `frontend/` | Vite + React + TypeScript + Tailwind |
| `infra/` | Dockerfiles, nginx config, CI |
