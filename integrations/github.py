"""GitHub integration: webhook signature verification, REST client,
review comments, check runs. Least-privilege App permissions: contents
read, pull requests read/write, checks write, metadata read.
No token configured -> the client raises, and callers record that
posting was skipped (never a fake 'posted' state).
"""
from __future__ import annotations
import hashlib, hmac
import httpx
from settings import settings

API = "https://api.github.com"

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
