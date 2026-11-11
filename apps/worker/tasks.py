"""Celery tasks: indexing + review + dataset build."""
from __future__ import annotations

def _celery():
    from apps.worker.celery_app import celery_app
    if celery_app is None:
        raise RuntimeError("Celery not configured")
    return celery_app

try:
    celery_app = _celery()

    @celery_app.task(name="apps.worker.tasks.review_pr", bind=True, max_retries=3)
    def review_pr(self, pr_id: int):
        from database.session import SessionLocal
        from database.models import PullRequest, Repository
        from services.review import run_review
        from apps.worker.queue import _contents_for_pr
        db = SessionLocal()
        try:
            pr = db.query(PullRequest).filter_by(id=pr_id).first()
            repo = db.query(Repository).filter_by(id=pr.repo_id).first()
            run_review(db, repo, pr, _contents_for_pr(db, repo, pr))
        except Exception as e:
            raise self.retry(exc=e, countdown=2 ** self.request.retries * 10)
        finally:
            db.close()

    @celery_app.task(name="apps.worker.tasks.build_dataset")
    def build_dataset_task(repo_id: int | None = None):
        from database.session import SessionLocal
        from training.dataset_builder import build_dataset
        db = SessionLocal()
        try:
            return str(build_dataset(db, repo_id).version) if build_dataset(db, repo_id) else None
        finally:
            db.close()
except Exception:
    pass  # celery unavailable: thread fallback in apps/worker/queue.py
