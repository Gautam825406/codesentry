# GitHub App setup — production checklist (live deployment)

This is the exact checklist for the live CodeSentry deployment. It replaces
the generic notes in `docs/GITHUB_SETUP.md` for anything production.

**Live URLs**

| Piece | URL |
|---|---|
| Frontend | https://codesentry-one.vercel.app/ |
| Backend API | https://codesentry-backend-hl76.onrender.com |
| Webhook endpoint | **https://codesentry-backend-hl76.onrender.com/webhooks/github** |
| GitHub repo | https://github.com/Gautam825406/codesentry |

**What changed (branch `fix/production-github-indexing`)**

- Repository names are normalized to lowercase `owner/repo` on connect, so
  `https://github.com/Gautam825406/querypilot` and
  `https://github.com/Gautam825406/querypilot.git` can no longer create two
  rows. The repo list additionally collapses any legacy duplicate rows.
- Full re-index now **fetches the repo from GitHub** (tarball API) when no
  explicit file map is supplied. Public repos need no token at all; private
  repos use `GITHUB_TOKEN` or a GitHub App installation token. A failed
  fetch returns HTTP 502 and marks the repo `failed` — it is never again
  silently recorded as `indexed` with 0 symbols.
- The demo repo is unaffected: re-indexing `demo/shop-api` still uses the
  bundled fixture files, no GitHub credentials needed.

## 1. Render environment variables

Render dashboard → service `codesentry-backend` → Environment. Set these
**before** deploying the branch (a redeploy is triggered automatically on
push to `main`). Values marked `sync: false` in `render.yaml` must be set in
the dashboard; they are never committed.

| Variable | Required? | Value / notes |
|---|---|---|
| `CODESENTRY_JWT_SECRET` | Yes — already set | Long random value (already generated on Render; do not change it — existing login tokens would break). |
| `PYTHON_VERSION` | Yes — already set | `3.12.0` |
| `GITHUB_WEBHOOK_SECRET` | Yes, for webhooks | Generate a random secret (e.g. `openssl rand -hex 32`). **Must match the secret entered in the GitHub App webhook settings exactly.** Without it, every webhook is rejected with 401. |
| `GITHUB_TOKEN` | Recommended (PAT fallback) | Fine-grained PAT, see §3. Enables private-repo indexing and PR posting without the App. If unset, public repos still index; private repos fail with a clear 502. |
| `GITHUB_APP_ID` | Yes, for the App path | Numeric App ID from the App's settings page (see §2). |
| `GITHUB_APP_PRIVATE_KEY` | Yes, for the App path | The App's `.pem` private key, pasted in full including `-----BEGIN RSA PRIVATE KEY-----` / `-----END RSA PRIVATE KEY-----` lines. Render keeps the newlines; if a tooling step flattens them to literal `\n`, the code converts them back. |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | Optional | Only for "Sign in with GitHub" on the dashboard. Not needed for indexing or webhooks. |
| `GROQ_API_KEY` | Optional | Only for LLM-polished findings; the deterministic rule engine is the default. |
| `DATABASE_URL` / `REDIS_URL` | Optional | Postgres / Redis. Unset = SQLite on ephemeral disk + in-process thread queue (current live setup). |

## 2. Create the GitHub App

GitHub → Settings → Developer settings → GitHub Apps → **New GitHub App**.

1. **Name:** `CodeSentry`. **Homepage URL:**
   `https://codesentry-one.vercel.app/`
2. **Webhook URL:**
   `https://codesentry-backend-hl76.onrender.com/webhooks/github`
   (active, JSON, `application/vnd.github+json` is set by the app).
3. **Webhook secret:** the same value as `GITHUB_WEBHOOK_SECRET` above.
4. **Permissions** (least privilege — do not request more):
   - Contents: **Read** (fetch repo files, PR diffs)
   - Pull requests: **Read and write** (post review comments)
   - Checks: **Write** (CodeSentry check run / merge gate)
   - Metadata: **Read** (required by GitHub for every App)
5. **Subscribe to events:** `pull_request`, `push`, `installation`,
   `pull_request_review_comment`.
6. **Create the App**, then on its settings page:
   - Copy the **App ID** → `GITHUB_APP_ID`.
   - Generate a **private key** (downloads a `.pem`) → paste into
     `GITHUB_APP_PRIVATE_KEY`.
7. **Install the App** (Install App → choose account `Gautam825406` →
   **Only select repositories**): select `codesentry` and `querypilot`
   (add more later from the same page). Installing on "All repositories"
   is not recommended.

## 3. PAT fallback (optional but recommended)

If the App is not installed on a repository, CodeSentry falls back to
`GITHUB_TOKEN`. Create a **fine-grained PAT**
(Settings → Developer settings → Personal access tokens → Fine-grained
tokens) for user `Gautam825406`, repository access "Only select
repositories" (`codesentry`, `querypilot`), permissions:

- Contents: **Read**
- Pull requests: **Read and write**
- Checks: **Read and write**

Set it as `GITHUB_TOKEN` on Render. The token is used for (in order):
repo fetching, PR diff fetching, review posting, check runs. It is never
logged and never returned by any API.

## 4. Verify end to end (in the browser, on the live site)

1. Open https://codesentry-one.vercel.app/ → **Run demo review** and
   confirm PR #42 still shows HIGH SQL injection (CWE-89), gate fail.
   (The demo does not need GitHub.)
2. **Repositories** → connect `Gautam825406/codesentry` (already connected
   live; if it shows twice, the list now collapses it to one row).
3. Open the repo → **Full re-index**. Expect a toast like
   `Re-indexed: <N> symbols (tree-sitter)` with **N > 0**, and the header
   `index: indexed · <N> symbols`. If it fails, the toast carries the real
   reason (e.g. "not found or not accessible" = private repo without a
   token; "rate limit" = set `GITHUB_TOKEN`).
4. Open a test PR on `Gautam825406/codesentry` (or push a small change).
   The webhook delivery should return `{"status": "queued"}` and a
   `CodeSentry` check run should appear on the PR as `in_progress`, then
   `success`/`failure` with the review summary.
5. **Findings** → open a finding → leave feedback (accept / reject_wrong)
   and confirm the finding state changes.

## 5. Known gaps (not fixed by this branch)

- **Push auto re-index is not wired yet.** The webhook records `push`
  deliveries but returns `{"status": "queued", "note": "push indexing is
  queued via reindex"}` without actually re-indexing — use **Full
  re-index** after a push, or re-run it from the repo page.
- **`installation` webhook events are ignored.** No installation row is
  needed for the current flow: installation tokens are resolved on demand
  via `GET /repos/{owner}/{repo}/installation`, so installing the App is
  enough.
- **Legacy duplicate rows stay in the live database.** The two
  `querypilot` rows in the live (ephemeral SQLite) database are collapsed
  in the UI by this fix, but the rows themselves are only removed when the
  Render disk is reset (redeploy) or by a manual purge. New duplicates
  cannot be created.
- **Redeploy wipes the live database.** The live backend uses SQLite on
  Render's ephemeral disk, so a redeploy resets all data (repos, demo
  seed, findings). After deploying, re-run **Run demo review** on the site
  to restore the demo, and re-connect real repos. Moving to Postgres
  (`DATABASE_URL`) is the durable fix — see `docs/DEPLOYMENT.md`.

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Webhook deliveries return 401 | `GITHUB_WEBHOOK_SECRET` on Render ≠ secret in the App settings. Fix the mismatch; deliveries are rejected, never accepted unsigned. |
| Re-index 502 "not found or not accessible" | Private repo and no token, or App not installed on it. Set `GITHUB_TOKEN` or install the App on the repo. |
| Re-index 502 "rate limit" | Unauthenticated GitHub API (60 req/hr) exhausted. Set `GITHUB_TOKEN`. |
| Re-index 502 "tarball exceeds 50 MB" | Repo too large for one fetch. Narrow indexed paths in repo settings or split the repo. |
| Re-index 0 symbols on a real repo | Should no longer happen: fetch failures are 502s. If seen, the repo genuinely has no Python/JS/TS files at the default branch. |
| PR review never starts | Check the webhook delivery status in the App settings → Recent Deliveries, and that the repo is connected in CodeSentry (webhooks for unconnected repos are ignored). |
