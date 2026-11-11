"""Worker queue: Celery + Redis when available, in-process background
threads otherwise. The webhook never waits for a review either way."""
from __future__ import annotations
import threading
from settings import settings

def enqueue_review(pr_id: int) -> str:
    """Returns 'celery' or 'thread' (how the job was queued)."""
    if settings.CELERY_BROKER_URL:
        try:
            from apps.worker.celery_app import celery_app
            celery_app.send_task("apps.worker.tasks.review_pr", args=[pr_id])
            return "celery"
        except Exception as e:
            print(f"[queue] celery enqueue failed, falling back to thread: {e}")
    t = threading.Thread(target=_run_review_thread, args=(pr_id,), daemon=True)
    t.start()
    return "thread"

def _run_review_thread(pr_id: int):
    from database.session import SessionLocal
    from database.models import PullRequest, Repository
    from services.review import run_review
    db = SessionLocal()
    try:
        pr = db.query(PullRequest).filter_by(id=pr_id).first()
        if not pr:
            return
        repo = db.query(Repository).filter_by(id=pr.repo_id).first()
        # file contents: demo/local reviews store them on the PR row is not
        # possible at scale; for local + demo, contents come from the
        # fixtures / a stored snapshot — see scripts/demo_review.py.
        # GitHub-backed reviews fetch contents via the GitHub client.
        contents = _contents_for_pr(db, repo, pr)
        run_review(db, repo, pr, contents)
    except Exception as e:
        print(f"[queue] review {pr_id} failed: {e}")
    finally:
        db.close()

def _contents_for_pr(db, repo, pr) -> dict:
    """Best-effort file contents for a PR. Demo repos ship their files in
    fixtures/sample_repo; GitHub repos are fetched via the API when a token
    exists (contents endpoint, per changed file)."""
    import base64, json
    from indexer.diff import changed_files
    files = changed_files(pr.diff_text or "")
    contents: dict[str, str] = {}
    if repo and repo.is_demo:
        import os
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "fixtures", "sample_repo")
        for p in files:
            fp = os.path.join(base, p)
            if os.path.exists(fp):
                contents[p] = open(fp).read()
        return contents
    if settings.GITHUB_TOKEN:
        try:
            import httpx
            from integrations.github import GitHubClient
            gh = GitHubClient()
            for p in files:
                try:
                    r = httpx.get(
                        f"https://api.github.com/repos/{repo.full_name}/contents/{p}",
                        headers=gh._headers(), params={"ref": pr.head_sha}, timeout=15)
                    if r.status_code == 200:
                        contents[p] = base64.b64decode(r.json()["content"]).decode()
                except Exception:
                    continue
        except Exception:
            pass
    return contents
