# Database

PostgreSQL is the system of record; SQLite is the local fallback
(`DATABASE_URL`, default `sqlite:///./codesentry.db`). Alembic migrations live
in `database/migrations/versions/` (`0001` initial schema, `0002` pgvector).

## Tables

| Table | Purpose |
|---|---|
| `users` | email, PBKDF2 password hash + salt, role (`user`/`reviewer`/`admin`), GitHub login |
| `installations` | GitHub App installation id + account |
| `repositories` | full_name (unique), owner, branch, languages, head SHA, index status, demo flag |
| `repo_settings` | languages, include/exclude paths, confidence threshold, severity policy, gate, model, budgets, `training_opt_in` (default **false**), index pause |
| `indexed_files` | repo + path (unique), language, content hash, head SHA, generated flag |
| `symbols` | repo, file, qualified name, kind, language, path, line range, signature, docstring, body, content hash, commit SHA, embedding (JSON list, dim 128) |
| `call_edges` | caller/callee symbol ids + names, file, line, `resolved` flag (unresolved edges are kept and labelled) |
| `pull_requests` | repo + number (unique), title, author, base/head SHA, state, size band, diff |
| `review_runs` | PR, status, model/adapter/prompt versions, timings, tokens, cost, latency, coverage JSON, gate result, summary |
| `findings` | run, repo, PR, source agent/scanner, category, severity, title, description, file, lines, evidence, CWE id/title, OWASP ref, confidence, patch + patch_valid, provenance, state (`posted`/`suppressed`/`fixed`/`dismissed`/`superseded`), suppressed reason |
| `feedback_events` | finding, actor, verdict, reason, timestamp (append-only) |
| `scan_results` | PR, kind (secret/dependency), package/type, advisory id, severity, detail |
| `dataset_versions` | version, train/val/held-out counts, source, metrics |
| `lora_adapters` | dataset version, base model, status, metrics, promoted flag |
| `audit_events` | actor, action, repo, payload, timestamp |
| `webhook_deliveries` | delivery id (unique), event, repo, payload, status |

## Notes

- **Embeddings:** stored as a JSON array on `symbols.embedding` in v1. On
  Postgres, migration `0002` adds `embedding_vector vector(128)` (pgvector)
  with an IVFFlat index — the scale path; the app still reads the JSON column
  until retrieval is switched over (documented, not hidden).
- **Repository isolation:** every repository-dependent query filters by
  `repo_id` and is additionally authorised in the API layer (`can_access_repo`).
- **Purge:** `POST /api/repos/{id}/purge?confirm=true` deletes symbols, files
  and call edges, then re-queries to verify zero remain (response includes
  `verified: true`).
- **Timestamps** are UTC on all rows; findings carry model/adapter/prompt
  versions so any historical decision can be explained.
