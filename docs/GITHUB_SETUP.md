# GitHub Setup

## 1. Create the GitHub App

1. GitHub → Settings → Developer settings → GitHub Apps → New GitHub App.
2. Name: `CodeSentry`. Homepage URL: your frontend URL.
3. Webhook URL: `https://<your-api>/webhooks/github`. Webhook secret: generate
   one and set it as `GITHUB_WEBHOOK_SECRET` (the receiver rejects unsigned
   webhooks — see `integrations/github.py::verify_signature`).
4. Permissions (least privilege):
   - Contents: **Read**
   - Pull requests: **Read and write** (comments)
   - Checks: **Write**
   - Metadata: **Read**
   - Do **not** request administration, secrets, or code-write permissions.
5. Subscribe to events: `installation`, `push`, `pull_request`,
   `pull_request_review_comment`.
6. Generate a private key; set `GITHUB_APP_ID` and `GITHUB_APP_PRIVATE_KEY`.
   (In v1 the API uses `GITHUB_TOKEN` — a fine-grained PAT with the same
   permissions — as the posting token; App installation-token exchange is the
   documented next step, see Limitations in README.)

## 2. GitHub OAuth (dashboard sign-in)

1. Same App (or a separate OAuth App): set the callback URL to
   `https://<your-api>/api/auth/github/callback`.
2. Set `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET`.
3. `GET /api/auth/github/login` returns the authorize URL; the callback
   exchanges the code for a token and creates/links the user.

## 3. Install the App

Install it on the repositories you want reviewed (selected repositories only).
On install, CodeSentry records the installation and indexes the repository;
on `push` it incrementally re-indexes changed files only.

## 4. Verify

- Open a PR on an installed repo. The webhook should return `{"status":"queued"}`.
- The check run `CodeSentry` goes `in_progress` → `success`/`failure`.
- A high-severity finding fails the check and blocks merge until fixed or
  dismissed by an authorised reviewer.

## Without GitHub (local demo)

`POST /api/demo/seed` seeds the sample repository and runs a real review of
PR #42 with no GitHub credentials at all. GitHub posting is then honestly
recorded as skipped in the run summary.
