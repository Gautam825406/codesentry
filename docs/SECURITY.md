# Security

## What is implemented

- **Webhook verification:** HMAC SHA-256 over the raw body; unsigned or
  wrongly-signed deliveries are rejected with 401. Delivery IDs are deduplicated.
- **Auth:** JWT (PyJWT, HS256) with expiry; passwords hashed with PBKDF2-HMAC-SHA256
  (200k iterations, per-user salt). GitHub OAuth uses the standard code flow
  with a random `state` value.
- **Authorization:** repository reads/writes check ownership or admin role
  (`can_access_repo` / `can_admin_repo`); demo repos are readable by any
  signed-in user. Dismissing a finding requires reviewer/admin/owner and is
  written to the audit log.
- **No IDOR:** finding/PR/repo lookups are scoped through the repository
  authorization check; a user cannot read another user's non-demo repository.
- **Secrets:** all credentials come from environment variables; `.env` is
  git-ignored; the CI workflow greps for common secret patterns. Found secrets
  are stored **masked only** (first 3 chars + `***`) and never reproduced in
  comments or the dashboard.
- **Prompt injection:** repository code/comments are untrusted data. They are
  passed to the LLM inside a quoted data block with an explicit instruction
  hierarchy; injection markers are stripped and logged; model output must still
  validate against `FindingDraft` and pass citation verification.
- **Cross-repo leakage:** retrieval, findings, feedback and training queries
  are all scoped by `repo_id` in the query itself; prompts are built only from
  the repository under review.
- **Input validation:** Pydantic everywhere; unified-diff parsing is bounded;
  oversized PRs are reviewed in priority order with skipped files disclosed.
- **SSRF:** repository contents are fetched only from `api.github.com` for a
  connected repository at its recorded head SHA.
- **Audit:** installs, settings changes, feedback/dismissals, purges and
  adapter promotions are append-only audit events.

## Known gaps (honest)

- The dev JWT secret default (`dev-only-change-me`) is insecure if deployed
  unchanged — set `CODESENTRY_JWT_SECRET`. The app does not yet refuse to boot
  in production without one.
- GitHub posting uses a PAT (`GITHUB_TOKEN`) in v1; App installation-token
  exchange (short-lived, per-installation) is the documented hardening step.
- Stored GitHub credentials are not encrypted at rest in v1 (only env vars
  are used; no tokens are persisted in the DB).
- Rate limiting is not yet implemented on the API (documented roadmap).
- Taint analysis is heuristic (source → sink hints), not a verified data-flow
  proof — the product never claims complete security coverage.
