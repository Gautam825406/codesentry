"""GitHub integration: webhook signature verification, REST client,
review comments, check runs, and repository fetching.

Fetching (used by re-index): a public repository is fetched without any
credentials via the tarball API; a token (``GITHUB_TOKEN`` PAT, or a GitHub
App installation token when the App is configured) raises the rate limit
and unlocks private repositories. No token configured -> the client raises,
and callers record that posting was skipped (never a fake 'posted' state).
Least-privilege App permissions: contents read, pull requests read/write,
checks write, metadata read.
"""
from __future__ import annotations
import hashlib, hmac, io, tarfile, time
import httpx
from settings import settings

API = "https://api.github.com"

# Safety caps for the free-tier backend: a repo bigger than this is not
# fetched in one re-index (the error tells the user to shrink scope).
MAX_TARBALL_BYTES = 50 * 1024 * 1024   # 50 MB download
MAX_FILES = 2000                        # indexable files kept
MAX_FILE_BYTES = 1024 * 1024            # 1 MB per file


class RepoFetchError(RuntimeError):
    """Fetching a repository from GitHub failed (not found / private /
    rate-limited / too large). The message is user-facing."""


def _auth_headers(token: str | None) -> dict:
    headers = {"Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _app_jwt() -> str:
    """Short-lived GitHub App JWT (RS256, 10 min) for App API calls."""
    import jwt
    key = settings.GITHUB_APP_PRIVATE_KEY or ""
    if "\\n" in key and "\n" not in key:
        key = key.replace("\\n", "\n")
    now = int(time.time())
    return jwt.encode({"iat": now - 60, "exp": now + 600,
                       "iss": settings.GITHUB_APP_ID},
                      key, algorithm="RS256")


def get_installation_token_for_repo(full_name: str, transport=None) -> str:
    """Exchange App credentials for an installation token scoped to the
    installation that covers ``full_name``. Raises RepoFetchError if the
    App is not configured or not installed on the repository."""
    if not settings.GITHUB_APP_ID or not settings.GITHUB_APP_PRIVATE_KEY:
        raise RepoFetchError("GitHub App is not configured "
                             "(set GITHUB_APP_ID / GITHUB_APP_PRIVATE_KEY)")
    headers = {"Authorization": f"Bearer {_app_jwt()}",
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    with httpx.Client(transport=transport, timeout=15) as c:
        r = c.get(f"{API}/repos/{full_name}/installation", headers=headers)
        if r.status_code == 404:
            raise RepoFetchError(
                f"GitHub App is not installed on {full_name} — install it "
                "from the App's settings page (selected repositories only), "
                "or set GITHUB_TOKEN for a PAT instead")
        r.raise_for_status()
        installation_id = r.json()["id"]
        r = c.post(f"{API}/app/installations/{installation_id}/access_tokens",
                   headers=headers)
        r.raise_for_status()
        return r.json()["token"]


def _resolve_token(full_name: str, token: str | None, transport=None) -> str | None:
    """Token order: explicit argument -> GITHUB_TOKEN PAT -> App
    installation token -> None (public repos only, 60 req/hr)."""
    if token:
        return token
    if settings.GITHUB_TOKEN:
        return settings.GITHUB_TOKEN
    if settings.GITHUB_APP_ID and settings.GITHUB_APP_PRIVATE_KEY:
        try:
            return get_installation_token_for_repo(full_name, transport=transport)
        except RepoFetchError:
            # App configured but not installed on this repo: fall through to
            # unauthenticated access (works for public repos).
            return None
    return None


def get_default_branch(full_name: str, token: str | None = None,
                       transport=None) -> str:
    """Default branch of a repo (raises RepoFetchError if the repo is not
    reachable with the available credentials)."""
    with httpx.Client(transport=transport, timeout=15) as c:
        r = c.get(f"{API}/repos/{full_name}", headers=_auth_headers(token))
    if r.status_code == 404:
        raise RepoFetchError(
            f"Repository {full_name} not found or not accessible — for a "
            "private repository set GITHUB_TOKEN or install the GitHub App")
    if r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0":
        raise RepoFetchError("GitHub API rate limit reached — set GITHUB_TOKEN "
                             "to raise the limit, or try again later")
    r.raise_for_status()
    return r.json().get("default_branch") or "main"


def _head_sha(full_name: str, ref: str, token: str | None,
              transport=None) -> str:
    """HEAD commit sha of ``ref`` (best effort — returns "" instead of
    failing the fetch; the codeload redirect URL does not carry it)."""
    try:
        with httpx.Client(transport=transport, timeout=15) as c:
            r = c.get(f"{API}/repos/{full_name}/commits/{ref}",
                      headers=_auth_headers(token))
        if r.status_code == 200:
            return r.json().get("sha") or ""
    except Exception:
        pass
    return ""


def fetch_repo_files(full_name: str, ref: str | None = None,
                     token: str | None = None, transport=None
                     ) -> tuple[dict[str, str], str]:
    """Fetch a repository's indexable files from GitHub.

    Downloads the branch tarball (``GET /repos/{owner}/{repo}/tarball/{ref}``)
    and returns ``({path: source}, head_sha)`` with only Python/JS/TS files
    (the languages the indexer understands). Public repos need no token;
    private repos need a token (PAT or App installation token, resolved by
    ``_resolve_token``). Raises ``RepoFetchError`` with a user-facing reason
    instead of returning an empty map — callers must never silently record
    an empty index as a successful re-index.
    """
    from indexer.parsers import language_for_path
    token = _resolve_token(full_name, token, transport=transport)
    ref = ref or get_default_branch(full_name, token, transport=transport)
    head_sha = _head_sha(full_name, ref, token, transport=transport)
    headers = _auth_headers(token)
    with httpx.Client(transport=transport, timeout=60, follow_redirects=True) as c:
        with c.stream("GET", f"{API}/repos/{full_name}/tarball/{ref}",
                      headers=headers) as r:
            if r.status_code == 404:
                raise RepoFetchError(
                    f"Repository {full_name} not found or not accessible — "
                    "for a private repository set GITHUB_TOKEN or install "
                    "the GitHub App")
            if r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0":
                raise RepoFetchError("GitHub API rate limit reached — set "
                                     "GITHUB_TOKEN to raise the limit, or try again later")
            r.raise_for_status()
            buf = io.BytesIO()
            for chunk in r.iter_bytes(1 << 16):
                buf.write(chunk)
                if buf.tell() > MAX_TARBALL_BYTES:
                    raise RepoFetchError(
                        f"Repository tarball exceeds the {MAX_TARBALL_BYTES // (1024 * 1024)} MB "
                        "fetch cap — narrow the indexed paths in repo settings "
                        "or index a smaller repository")
    files: dict[str, str] = {}
    buf.seek(0)
    try:
        tf = tarfile.open(fileobj=buf, mode="r:*")
    except tarfile.TarError as e:
        raise RepoFetchError(f"Could not read the repository tarball: {e}")
    with tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            parts = member.name.split("/", 1)
            path = parts[1] if len(parts) == 2 else parts[0]
            if not path or language_for_path(path) is None:
                continue
            if member.size > MAX_FILE_BYTES:
                continue
            if len(files) >= MAX_FILES:
                break
            f = tf.extractfile(member)
            if f is None:
                continue
            files[path] = f.read().decode("utf-8", errors="replace")
    if not files:
        raise RepoFetchError(
            f"No indexable Python/JavaScript/TypeScript files found in "
            f"{full_name}@{ref} — check the repository contents and the "
            "default branch")
    return files, head_sha

def verify_signature(secret: str, payload: bytes, signature: str | None) -> bool:
    if not secret:
        return False  # no secret configured: refuse, do not accept unsigned webhooks
    if not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

class GitHubClient:
    def __init__(self, token: str | None = None):
        self.token = token or settings.GITHUB_TOKEN
        if not self.token:
            raise RuntimeError("No GitHub token configured (GITHUB_TOKEN / App installation token)")

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"}

    def fetch_repo_files(self, full_name: str, ref: str | None = None,
                         transport=None) -> tuple[dict[str, str], str]:
        """Fetch the repo's indexable files with this client's token."""
        return fetch_repo_files(full_name, ref=ref, token=self.token,
                                transport=transport)

    def get_pr_diff(self, full_name: str, number: int) -> str:
        r = httpx.get(f"{API}/repos/{full_name}/pulls/{number}",
                      headers={**self._headers(), "Accept": "application/vnd.github.diff"},
                      timeout=30)
        r.raise_for_status()
        return r.text

    def get_pr(self, full_name: str, number: int) -> dict:
        r = httpx.get(f"{API}/repos/{full_name}/pulls/{number}", headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def post_review(self, full_name: str, number: int, body: str, event: str = "COMMENT") -> dict:
        r = httpx.post(f"{API}/repos/{full_name}/pulls/{number}/reviews",
                       headers=self._headers(),
                       json={"body": body, "event": event}, timeout=30)
        r.raise_for_status()
        return r.json()

    def create_check_run(self, full_name: str, head_sha: str, name: str = "CodeSentry") -> dict:
        r = httpx.post(f"{API}/repos/{full_name}/check-runs", headers=self._headers(),
                       json={"name": name, "head_sha": head_sha, "status": "in_progress"},
                       timeout=30)
        r.raise_for_status()
        return r.json()

    def update_check_run(self, full_name: str, check_run_id: int, *,
                         status: str, conclusion: str | None, summary: str) -> dict:
        payload = {"status": status, "output": {"title": "CodeSentry review", "summary": summary}}
        if conclusion:
            payload["conclusion"] = conclusion
        r = httpx.patch(f"{API}/repos/{full_name}/check-runs/{check_run_id}",
                        headers=self._headers(), json=payload, timeout=30)
        r.raise_for_status()
        return r.json()

    def list_installation_repos(self, installation_id: int) -> list[dict]:
        r = httpx.get(f"{API}/user/installations/{installation_id}/repositories",
                      headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json().get("repositories", [])
