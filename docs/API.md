# API

Base URL: `http://localhost:8000`. Interactive docs: `/docs` (OpenAPI).
Auth: Bearer JWT from `POST /api/auth/login` (or GitHub OAuth). All
repository-scoped endpoints enforce ownership: demo repos are readable by any
signed-in user; other repos only by their owner or an admin.

## Health / metrics

| Method | Path | Description |
|---|---|---|
| GET | `/health` | liveness + parser/LLM/embedding providers actually in use |
| GET | `/metrics` | counts of repos, findings, reviews, feedback, webhooks |

## Auth

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register` | email + password (min 8 chars) |
| POST | `/api/auth/login` | returns JWT |
| GET | `/api/auth/me` | current user |
| GET | `/api/auth/github/login` | GitHub OAuth authorize URL (needs `GITHUB_CLIENT_ID`) |
| GET | `/api/auth/github/callback` | exchanges code, creates/links user |

## Repositories

| Method | Path | Description |
|---|---|---|
| GET | `/api/repos` | visible repositories |
| POST | `/api/repos` | connect a repository `{full_name}` |
| GET | `/api/repos/{id}` | repo + symbol count + settings |
| GET/PATCH | `/api/repos/{id}/settings` | languages, paths, threshold, gate, model, budgets, training opt-in (PATCH: admin only) |
| POST | `/api/repos/{id}/reindex` | full re-index (admin; body = optional `{path: source}` file map) |
| POST | `/api/repos/{id}/purge?confirm=true` | delete index + embeddings, verified |
| GET | `/api/repos/{id}/quality` | metrics from persisted data only (precision is `null` until feedback exists) |

## Pull requests & reviews

| Method | Path | Description |
|---|---|---|
| GET | `/api/repos/{id}/prs` | PRs with latest run status/gate (paginated) |
| GET | `/api/repos/{id}/prs/{number}` | PR + runs + findings (incl. suppressed with reasons) + coverage |
| POST | `/api/repos/{id}/prs/{number}/review` | trigger a review (admin; body may carry `diff_text` + `file_contents`) |

## Findings & feedback

| Method | Path | Description |
|---|---|---|
| GET | `/api/findings?severity=&cwe=&category=&repo_id=&pr_number=&agent=&state=` | filtered list |
| GET | `/api/findings/{id}` | finding + feedback history |
| POST | `/api/findings/{id}/feedback` | `{verdict, reason}` — `accept` / `fixed` / `reject_wrong` / `reject_not_worth_fixing` / `ignore`. Dismissal requires reviewer/admin/owner and is audited. |

## Webhooks, agents, training, audit

| Method | Path | Description |
|---|---|---|
| POST | `/webhooks/github` | HMAC SHA-256 verified, delivery-id deduped, async enqueue |
| GET | `/api/security` | Security Center aggregates (CWE findings only) |
| GET | `/api/agents` | agent status, parser, embedding + LLM providers |
| GET/POST | `/api/training/datasets` | list / build from feedback |
| GET | `/api/training/adapters` | list adapters |
| POST | `/api/training/datasets/{id}/train` | start LoRA job (GPU-gated, honest status) |
| POST | `/api/training/adapters/{id}/promote` / `rollback` | gate-checked promotion |
| GET | `/api/audit` | audit events |
| POST | `/api/demo/seed` | seed demo repo + PR #42 + real review (no GitHub needed) |

## Errors

Consistent shape: `{"detail": "<message>"}` with the HTTP status code.
Common: `401` missing/invalid token or webhook signature, `403` not authorised
for the repository, `404` not found, `409` indexing paused, `501` GitHub OAuth
not configured.
