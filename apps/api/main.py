"""CodeSentry API — FastAPI application.

Endpoints (PRD §10): webhooks, repos, settings, reindex, PRs, findings
feedback, quality, purge, health, metrics, plus auth, demo, agents,
training, audit and security-center endpoints used by the frontend.
Every repository-scoped read enforces ownership (see apps/api/auth.py).
No endpoint returns hardcoded demo data: metrics are computed from the DB.
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import hashlib, hmac, json
from datetime import datetime, timezone
import httpx
from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from settings import settings
from database.session import get_db, init_db
from database.models import (User, Repository, RepoSettings, PullRequest, ReviewRun,
                             Finding, FeedbackEvent, AuditEvent, WebhookDelivery,
                             ScanResult, DatasetVersion, LoRAAdapter, Symbol)
from apps.api.auth import (hash_password, verify_password, create_token,
                           get_current_user, require_role, can_access_repo,
                           can_admin_repo)
from integrations.github import verify_signature, GitHubClient
from indexer.incremental import index_files
from services.review import run_review, gate_for
from apps.worker.queue import enqueue_review

app = FastAPI(title="CodeSentry", version="1.0.0",
              description="Agentic secure code review + codebase RAG")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
init_db()

# ------------------------------------------------------------------ schemas
class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=8)
    name: str = ""

class LoginIn(BaseModel):
    email: str
    password: str

class RepoIn(BaseModel):
    full_name: str
    default_branch: str = "main"
    clone_url: str = ""

class SettingsIn(BaseModel):
    enabled_languages: list[str] | None = None
    included_paths: list[str] | None = None
    excluded_paths: list[str] | None = None
    confidence_threshold: float | None = None
    severity_policy: dict | None = None
    gate_enabled: bool | None = None
    model_provider: str | None = None
    model_name: str | None = None
    token_budget_per_symbol: int | None = None
    daily_cost_limit_usd: float | None = None
    training_opt_in: bool | None = None
    index_paused: bool | None = None

class FeedbackIn(BaseModel):
    verdict: str  # accept|fixed|reject_wrong|reject_not_worth_fixing|ignore
    reason: str = ""

class PRCreateIn(BaseModel):
    number: int
    title: str = ""
    author: str = ""
    base_sha: str = ""
    head_sha: str = ""
    diff_text: str = ""
    file_contents: dict[str, str] = Field(default_factory=dict)

# ------------------------------------------------------------------ helpers
def _audit(db, actor, action, repo_id=None, payload=None):
    db.add(AuditEvent(actor=actor, action=action, repo_id=repo_id, payload=payload or {}))
    db.commit()

def _repo_or_404(db, repo_id: int) -> Repository:
    repo = db.query(Repository).filter_by(id=repo_id).first()
    if not repo:
        raise HTTPException(404, "Repository not found")
    return repo

def _ensure_settings(db, repo: Repository) -> RepoSettings:
    if not repo.settings:
        repo.settings = RepoSettings(repo_id=repo.id)
        db.add(repo.settings)
        db.commit()
        db.refresh(repo)
    return repo.settings

def repo_out(r: Repository) -> dict:
    return {"id": r.id, "full_name": r.full_name, "name": r.name,
            "default_branch": r.default_branch, "languages": r.languages or [],
            "head_sha": r.head_sha, "index_status": r.index_status,
            "last_indexed_at": r.last_indexed_at.isoformat() if r.last_indexed_at else None,
            "is_demo": r.is_demo, "created_at": r.created_at.isoformat() if r.created_at else None}

def finding_out(f: Finding) -> dict:
    return {"id": f.id, "run_id": f.run_id, "repo_id": f.repo_id, "pr_id": f.pr_id,
            "pr_number": f.pr_number, "source": f.source, "category": f.category,
            "severity": f.severity, "title": f.title, "description": f.description,
            "file_path": f.file_path, "start_line": f.start_line, "end_line": f.end_line,
            "evidence": f.evidence, "cwe_id": f.cwe_id, "cwe_title": f.cwe_title,
            "owasp_ref": f.owasp_ref, "confidence": f.confidence, "patch": f.patch,
            "patch_valid": f.patch_valid, "model_version": f.model_version,
            "prompt_version": f.prompt_version, "context_provenance": f.context_provenance or {},
            "state": f.state, "suppressed_reason": f.suppressed_reason,
            "created_at": f.created_at.isoformat() if f.created_at else None}

# ------------------------------------------------------------------ health
@app.get("/health")
def health():
    return {"status": "ok", "service": "codesentry", "env": settings.ENV,
            "llm_provider": settings.LLM_PROVIDER,
            "embedding_provider": "hash-embedding-v1",
            "parser": __import__("indexer.parsers", fromlist=["PARSER_BACKEND"]).PARSER_BACKEND}

@app.get("/metrics")
def metrics(db: Session = Depends(get_db)):
    return {"repos": db.query(Repository).count(),
            "findings": db.query(Finding).count(),
            "findings_posted": db.query(Finding).filter_by(state="posted").count(),
            "reviews": db.query(ReviewRun).count(),
            "feedback_events": db.query(FeedbackEvent).count(),
            "webhook_deliveries": db.query(WebhookDelivery).count()}

# ------------------------------------------------------------------ auth
@app.post("/api/auth/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(400, "Email already registered")
    h, salt = hash_password(body.password)
    user = User(email=body.email, password_hash=h, password_salt=salt, name=body.name)
    db.add(user)
    db.commit()
    return {"token": create_token(user), "user": {"id": user.id, "email": user.email,
            "name": user.name, "role": user.role}}

@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email).first()
    if not user or not verify_password(body.password, user.password_hash, user.password_salt):
        raise HTTPException(401, "Invalid credentials")
    return {"token": create_token(user), "user": {"id": user.id, "email": user.email,
            "name": user.name, "role": user.role}}

@app.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role,
            "github_login": user.github_login}

@app.get("/api/auth/github/login")
def github_login():
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(501, "GitHub OAuth not configured: set GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET")
    state = hashlib.sha256(os.urandom(32)).hexdigest()
    url = (f"https://github.com/login/oauth/authorize?client_id={settings.GITHUB_CLIENT_ID}"
           f"&scope=repo read:user&state={state}")
    return {"authorize_url": url, "state": state}

@app.get("/api/auth/github/callback")
def github_callback(code: str, db: Session = Depends(get_db)):
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(501, "GitHub OAuth not configured")
    r = httpx.post("https://github.com/login/oauth/access_token",
                   json={"client_id": settings.GITHUB_CLIENT_ID,
                         "client_secret": settings.GITHUB_CLIENT_SECRET, "code": code},
                   headers={"Accept": "application/json"}, timeout=15)
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        raise HTTPException(400, "GitHub did not return an access token")
    u = httpx.get("https://api.github.com/user", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    u.raise_for_status()
    gh = u.json()
    user = db.query(User).filter_by(github_login=gh["login"]).first()
    if not user:
        user = db.query(User).filter_by(email=gh.get("email") or f"{gh['login']}@github.local").first()
    if not user:
        h, salt = hash_password(os.urandom(16).hex())
        user = User(email=gh.get("email") or f"{gh['login']}@github.local",
                    password_hash=h, password_salt=salt, name=gh.get("name") or gh["login"],
                    github_login=gh["login"])
        db.add(user)
        db.commit()
    return {"token": create_token(user), "github_login": gh["login"]}

# ------------------------------------------------------------------ repos
@app.get("/api/repos")
def list_repos(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    repos = db.query(Repository).all()
    visible = [r for r in repos if can_access_repo(user, r)]
    return [repo_out(r) for r in visible]

@app.post("/api/repos")
def create_repo(body: RepoIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.query(Repository).filter_by(full_name=body.full_name).first():
        raise HTTPException(400, "Repository already connected")
    repo = Repository(full_name=body.full_name, name=body.full_name.split("/")[-1],
                      default_branch=body.default_branch, clone_url=body.clone_url,
                      owner_id=user.id)
    db.add(repo)
    db.commit()
    _ensure_settings(db, repo)
    _audit(db, user.email, "repo_connected", repo.id, {"full_name": body.full_name})
    return repo_out(repo)

@app.get("/api/repos/{repo_id}")
def get_repo(repo_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    repo = _repo_or_404(db, repo_id)
    if not can_access_repo(user, repo):
        raise HTTPException(403, "Not authorised for this repository")
    out = repo_out(repo)
    out["symbols"] = db.query(Symbol).filter_by(repo_id=repo.id).count()
    out["settings"] = _settings_out(_ensure_settings(db, repo))
    return out

def _settings_out(s: RepoSettings) -> dict:
    return {"enabled_languages": s.enabled_languages, "included_paths": s.included_paths,
            "excluded_paths": s.excluded_paths, "confidence_threshold": s.confidence_threshold,
            "severity_policy": s.severity_policy, "gate_enabled": s.gate_enabled,
            "model_provider": s.model_provider, "model_name": s.model_name,
            "token_budget_per_symbol": s.token_budget_per_symbol,
            "daily_cost_limit_usd": s.daily_cost_limit_usd,
            "training_opt_in": s.training_opt_in, "index_paused": s.index_paused}

@app.get("/api/repos/{repo_id}/settings")
def get_settings(repo_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    repo = _repo_or_404(db, repo_id)
    if not can_access_repo(user, repo):
        raise HTTPException(403, "Not authorised for this repository")
    return _settings_out(_ensure_settings(db, repo))

@app.patch("/api/repos/{repo_id}/settings")
def patch_settings(repo_id: int, body: SettingsIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    repo = _repo_or_404(db, repo_id)
    if not can_admin_repo(user, repo):
        raise HTTPException(403, "Only a repository admin may change settings")
    s = _ensure_settings(db, repo)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit()
    _audit(db, user.email, "settings_updated", repo.id, body.model_dump(exclude_unset=True))
    return _settings_out(s)

@app.post("/api/repos/{repo_id}/reindex")
def reindex(repo_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user),
            files: dict[str, str] | None = None):
    """Full re-index (admin action). In production the worker clones the repo;
    this endpoint accepts an explicit file map for local/demo use."""
    repo = _repo_or_404(db, repo_id)
    if not can_admin_repo(user, repo):
        raise HTTPException(403, "Only a repository admin may re-index")
    st = _ensure_settings(db, repo)
    if st.index_paused:
        raise HTTPException(409, "Indexing is paused for this repository")
    repo.index_status = "indexing"
    db.commit()
    try:
        stats = index_files(db, repo, files or {}, head_sha=repo.head_sha,
                            excludes=st.excluded_paths)
        repo.index_status = "indexed"
        repo.last_indexed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        repo.index_status = "failed"
        db.commit()
        raise HTTPException(500, f"Re-index failed: {e}")
    _audit(db, user.email, "reindex", repo.id, stats)
    return {"status": "indexed", **stats}

@app.post("/api/repos/{repo_id}/purge")
def purge(repo_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user),
          confirm: bool = False):
    repo = _repo_or_404(db, repo_id)
    if not can_admin_repo(user, repo):
        raise HTTPException(403, "Only a repository admin may purge")
    if not confirm:
        raise HTTPException(400, "Purge requires confirm=true")
    from database.models import IndexedFile, CallEdge
    n_sym = db.query(Symbol).filter_by(repo_id=repo.id).delete()
    n_files = db.query(IndexedFile).filter_by(repo_id=repo.id).delete()
    db.query(CallEdge).filter_by(repo_id=repo.id).delete()
    repo.index_status = "not_indexed"
    repo.head_sha = ""
    db.commit()
    # verify the purge actually removed the data
    remaining = db.query(Symbol).filter_by(repo_id=repo.id).count()
    _audit(db, user.email, "purge", repo.id,
           {"symbols_deleted": n_sym, "files_deleted": n_files, "remaining_symbols": remaining})
    return {"purged": True, "symbols_deleted": n_sym, "files_deleted": n_files,
            "remaining_symbols": remaining, "verified": remaining == 0}

# ------------------------------------------------------------------ PRs
@app.get("/api/repos/{repo_id}/prs")
def list_prs(repo_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user),
             limit: int = Query(50, le=200), offset: int = 0):
    repo = _repo_or_404(db, repo_id)
    if not can_access_repo(user, repo):
        raise HTTPException(403, "Not authorised for this repository")
    prs = (db.query(PullRequest).filter_by(repo_id=repo.id)
           .order_by(PullRequest.id.desc()).offset(offset).limit(limit).all())
    out = []
    for pr in prs:
        run = (db.query(ReviewRun).filter_by(pr_id=pr.id)
               .order_by(ReviewRun.id.desc()).first())
        out.append({"id": pr.id, "number": pr.number, "title": pr.title, "author": pr.author,
                    "base_sha": pr.base_sha, "head_sha": pr.head_sha, "state": pr.state,
                    "size_band": pr.size_band,
                    "run": {"id": run.id, "status": run.status, "gate_result": run.gate_result,
                            "latency_ms": run.latency_ms, "tokens_used": run.tokens_used,
                            "cost_usd": run.cost_usd} if run else None})
    return out

@app.get("/api/repos/{repo_id}/prs/{number}")
def get_pr(repo_id: int, number: int, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    repo = _repo_or_404(db, repo_id)
    if not can_access_repo(user, repo):
        raise HTTPException(403, "Not authorised for this repository")
    pr = db.query(PullRequest).filter_by(repo_id=repo.id, number=number).first()
    if not pr:
        raise HTTPException(404, "Pull request not found")
    runs = db.query(ReviewRun).filter_by(pr_id=pr.id).order_by(ReviewRun.id.desc()).all()
    run_out = []
    for run in runs:
        findings = db.query(Finding).filter_by(run_id=run.id).all()
        run_out.append({"id": run.id, "status": run.status, "gate_result": run.gate_result,
                        "model_version": run.model_version, "adapter_version": run.adapter_version,
                        "prompt_version": run.prompt_version,
                        "started_at": run.started_at.isoformat() if run.started_at else None,
                        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                        "tokens_used": run.tokens_used, "cost_usd": run.cost_usd,
                        "latency_ms": run.latency_ms, "coverage": run.coverage or {},
                        "summary": run.summary,
                        "findings": [finding_out(f) for f in findings]})
    return {"id": pr.id, "number": pr.number, "title": pr.title, "author": pr.author,
            "base_sha": pr.base_sha, "head_sha": pr.head_sha, "state": pr.state,
            "size_band": pr.size_band, "repo_full_name": repo.full_name, "runs": run_out}

@app.post("/api/repos/{repo_id}/prs/{number}/review")
def trigger_review(repo_id: int, number: int, body: PRCreateIn | None = None,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Manual review trigger (used by the demo UI and tests). Runs synchronously
    for local/demo repos; the webhook path is async via the queue."""
    repo = _repo_or_404(db, repo_id)
    if not can_admin_repo(user, repo):
        raise HTTPException(403, "Only a repository admin may trigger a review")
    pr = db.query(PullRequest).filter_by(repo_id=repo.id, number=number).first()
    if not pr:
        if body is None:
            raise HTTPException(404, "Pull request not found; supply diff_text to create it")
        pr = PullRequest(repo_id=repo.id, number=number, title=body.title, author=body.author,
                         base_sha=body.base_sha, head_sha=body.head_sha, diff_text=body.diff_text)
        db.add(pr)
        db.commit()
    contents = (body.file_contents if body else {}) or {}
    if repo.is_demo and not contents:
        import os
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "fixtures", "sample_repo")
        from indexer.diff import changed_files
        for p in changed_files(pr.diff_text or ""):
            fp = os.path.join(base, p)
            if os.path.exists(fp):
                contents[p] = open(fp).read()
    run = run_review(db, repo, pr, contents)
    return {"run_id": run.id, "status": run.status, "gate_result": run.gate_result,
            "summary": run.summary, "coverage": run.coverage}

# ------------------------------------------------------------------ findings
@app.get("/api/findings")
def list_findings(db: Session = Depends(get_db), user: User = Depends(get_current_user),
                  severity: str | None = None, cwe: str | None = None,
                  category: str | None = None, repo_id: int | None = None,
                  pr_number: int | None = None, agent: str | None = None,
                  state: str | None = None, limit: int = Query(100, le=500),
                  offset: int = 0):
    q = db.query(Finding)
    if repo_id:
        repo = _repo_or_404(db, repo_id)
        if not can_access_repo(user, repo):
            raise HTTPException(403, "Not authorised for this repository")
        q = q.filter_by(repo_id=repo_id)
    else:
        visible = [r.id for r in db.query(Repository).all() if can_access_repo(user, r)]
        q = q.filter(Finding.repo_id.in_(visible))
    if severity: q = q.filter_by(severity=severity)
    if cwe: q = q.filter_by(cwe_id=cwe)
    if category: q = q.filter_by(category=category)
    if pr_number is not None: q = q.filter_by(pr_number=pr_number)
    if agent: q = q.filter_by(source=agent)
    if state: q = q.filter_by(state=state)
    return [finding_out(f) for f in q.order_by(Finding.id.desc()).offset(offset).limit(limit).all()]

@app.get("/api/findings/{finding_id}")
def get_finding(finding_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    f = db.query(Finding).filter_by(id=finding_id).first()
    if not f:
        raise HTTPException(404, "Finding not found")
    repo = db.query(Repository).filter_by(id=f.repo_id).first()
    if repo and not can_access_repo(user, repo):
        raise HTTPException(403, "Not authorised for this repository")
    out = finding_out(f)
    out["feedback"] = [{"actor": fb.actor_name, "verdict": fb.verdict, "reason": fb.reason,
                        "created_at": fb.created_at.isoformat() if fb.created_at else None}
                       for fb in db.query(FeedbackEvent).filter_by(finding_id=f.id).all()]
    return out

@app.post("/api/findings/{finding_id}/feedback")
def post_feedback(finding_id: int, body: FeedbackIn, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    if body.verdict not in ("accept", "fixed", "reject_wrong", "reject_not_worth_fixing", "ignore"):
        raise HTTPException(400, "Invalid verdict")
    f = db.query(Finding).filter_by(id=finding_id).first()
    if not f:
        raise HTTPException(404, "Finding not found")
    repo = db.query(Repository).filter_by(id=f.repo_id).first()
    if repo and not can_access_repo(user, repo):
        raise HTTPException(403, "Not authorised for this repository")
    fb = FeedbackEvent(finding_id=f.id, actor_id=user.id, actor_name=user.email,
                       verdict=body.verdict, reason=body.reason)
    db.add(fb)
    # state transitions + gate: a dismissal by an authorised reviewer lifts the block
    if body.verdict in ("fixed", "accept"):
        f.state = "fixed" if body.verdict == "fixed" else f.state
    if body.verdict in ("reject_wrong", "reject_not_worth_fixing"):
        if user.role not in ("reviewer", "admin") and repo and repo.owner_id != user.id:
            raise HTTPException(403, "Only an authorised reviewer may dismiss a finding")
        f.state = "dismissed"
    db.commit()
    _audit(db, user.email, f"feedback:{body.verdict}", f.repo_id,
           {"finding_id": f.id, "reason": body.reason})
    return {"finding_id": f.id, "verdict": body.verdict, "state": f.state}

# ------------------------------------------------------------------ quality
@app.get("/api/repos/{repo_id}/quality")
def quality(repo_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    repo = _repo_or_404(db, repo_id)
    if not can_access_repo(user, repo):
        raise HTTPException(403, "Not authorised for this repository")
    findings = db.query(Finding).filter_by(repo_id=repo.id).all()
    posted = [f for f in findings if f.state == "posted"]
    feedback = db.query(FeedbackEvent).join(Finding, FeedbackEvent.finding_id == Finding.id)\
        .filter(Finding.repo_id == repo.id).all()
    verdicts = {}
    for fb in feedback:
        verdicts[fb.verdict] = verdicts.get(fb.verdict, 0) + 1
    wrong = verdicts.get("reject_wrong", 0)
    total_fb = len(feedback)
    by_severity, by_cwe, by_agent = {}, {}, {}
    for f in posted:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
        if f.cwe_id:
            by_cwe[f.cwe_id] = by_cwe.get(f.cwe_id, 0) + 1
        by_agent[f.source] = by_agent.get(f.source, 0) + 1
    runs = (db.query(ReviewRun).join(PullRequest, ReviewRun.pr_id == PullRequest.id)
            .filter(PullRequest.repo_id == repo.id).all())
    latencies = sorted(r.latency_ms for r in runs if r.latency_ms)
    costs = [r.cost_usd for r in runs]
    return {"repo_id": repo.id, "full_name": repo.full_name,
            "total_repos": db.query(Repository).count(),
            "prs_reviewed": db.query(PullRequest).filter_by(repo_id=repo.id).count(),
            "total_findings": len(findings), "posted": len(posted),
            "suppressed": len([f for f in findings if f.state == "suppressed"]),
            "by_severity": by_severity, "by_cwe": by_cwe, "by_agent": by_agent,
            "verdicts": verdicts,
            "precision": round(1 - wrong / total_fb, 3) if total_fb else None,
            "false_positive_rate": round(wrong / total_fb, 3) if total_fb else None,
            "feedback_total": total_fb,
            "review_latency_ms_p50": latencies[len(latencies) // 2] if latencies else None,
            "review_latency_ms_p95": latencies[int(len(latencies) * 0.95)] if latencies else None,
            "cost_per_pr_usd": round(sum(costs) / len(costs), 4) if costs else 0.0,
            "note": "All metrics computed from persisted findings/feedback/runs. "
                    "precision is null until feedback exists — no fabricated numbers."}

@app.get("/api/security")
def security_center(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    visible = [r.id for r in db.query(Repository).all() if can_access_repo(user, r)]
    findings = db.query(Finding).filter(Finding.repo_id.in_(visible),
                                        Finding.state == "posted").all()
    sec = [f for f in findings if f.cwe_id]
    return {"critical": len([f for f in sec if f.severity == "critical"]),
            "high": len([f for f in sec if f.severity == "high"]),
            "by_cwe": {c: len([f for f in sec if f.cwe_id == c]) for c in {f.cwe_id for f in sec}},
            "findings": [finding_out(f) for f in sorted(sec, key=lambda x: x.id, reverse=True)[:100]]}

@app.get("/api/agents")
def agents_status():
    from indexer.parsers import PARSER_BACKEND
    from indexer.embeddings import embedding_provider_name
    return {"agents": [
        {"name": "security", "status": "active", "model": settings.LLM_PROVIDER,
         "mandate": "Injection, auth, deserialisation, traversal, XSS, secrets (CWE-mapped)"},
        {"name": "logic", "status": "active", "model": settings.LLM_PROVIDER,
         "mandate": "Correctness, error paths, resource leaks, caller contracts"},
        {"name": "style", "status": "active", "model": settings.LLM_PROVIDER,
         "mandate": "Opted-in maintainability only"},
    ], "graph": "langgraph StateGraph: fan-out security/logic/style -> filter -> patch",
     "parser": PARSER_BACKEND, "embeddings": embedding_provider_name(),
     "llm_provider": settings.LLM_PROVIDER}

# ------------------------------------------------------------------ training
@app.get("/api/training/datasets")
def list_datasets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [{"id": d.id, "version": d.version, "train": d.train_count, "val": d.val_count,
             "heldout": d.heldout_count, "source": d.source,
             "metrics": d.metrics_json or {}} for d in db.query(DatasetVersion).all()]

@app.post("/api/training/datasets/build")
def build_dataset_ep(repo_id: int | None = None, db: Session = Depends(get_db),
                     user: User = Depends(require_role("admin", "reviewer"))):
    from training.dataset_builder import build_dataset
    ds = build_dataset(db, repo_id)
    if ds is None:
        return {"built": False, "reason": "No eligible feedback: need authorised-reviewer "
                "correctness verdicts on a repository with training_opt_in=True."}
    return {"built": True, "version": ds.version, "train": ds.train_count,
            "val": ds.val_count, "heldout": ds.heldout_count, "metrics": ds.metrics_json}

@app.get("/api/training/adapters")
def list_adapters(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [{"id": a.id, "version": a.version, "base_model": a.base_model,
             "status": a.status, "promoted": a.promoted, "metrics": a.metrics_json or {}}
            for a in db.query(LoRAAdapter).all()]

@app.post("/api/training/adapters/{adapter_id}/promote")
def promote_adapter(adapter_id: int, db: Session = Depends(get_db),
                    user: User = Depends(require_role("admin"))):
    from training.lora import promote
    try:
        a = promote(db, adapter_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    _audit(db, user.email, "adapter_promoted", None, {"adapter": a.version})
    return {"id": a.id, "version": a.version, "promoted": True}

@app.post("/api/training/adapters/{adapter_id}/rollback")
def rollback_adapter(adapter_id: int, db: Session = Depends(get_db),
                     user: User = Depends(require_role("admin"))):
    from training.lora import rollback
    a = rollback(db, adapter_id)
    _audit(db, user.email, "adapter_rolled_back", None, {"adapter": a.version})
    return {"id": a.id, "version": a.version, "promoted": False, "status": a.status}

@app.post("/api/training/datasets/{dataset_id}/train")
def train_adapter_ep(dataset_id: int, db: Session = Depends(get_db),
                     user: User = Depends(require_role("admin"))):
    from training.lora import start_training
    a = start_training(db, dataset_id)
    return {"adapter_id": a.id, "version": a.version, "status": a.status,
            "metrics": a.metrics_json or {}}

# ------------------------------------------------------------------ audit
@app.get("/api/audit")
def audit_log(db: Session = Depends(get_db), user: User = Depends(get_current_user),
              limit: int = Query(100, le=500)):
    events = db.query(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit).all()
    return [{"id": e.id, "actor": e.actor, "action": e.action, "repo_id": e.repo_id,
             "payload": e.payload or {},
             "created_at": e.created_at.isoformat() if e.created_at else None} for e in events]

# ------------------------------------------------------------------ webhooks
@app.post("/webhooks/github")
async def github_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    delivery_id = request.headers.get("X-GitHub-Delivery", "")
    event = request.headers.get("X-GitHub-Event", "")
    if not verify_signature(settings.GITHUB_WEBHOOK_SECRET, payload,
                            request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(401, "Invalid webhook signature")
    if db.query(WebhookDelivery).filter_by(delivery_id=delivery_id).first():
        return {"status": "duplicate", "delivery_id": delivery_id}
    try:
        data = json.loads(payload)
    except Exception:
        raise HTTPException(400, "Invalid JSON payload")
    repo_name = (data.get("repository") or {}).get("full_name", "")
    record = WebhookDelivery(delivery_id=delivery_id, event=event,
                             repo_full_name=repo_name, payload=data, status="received")
    db.add(record)
    db.commit()
    if event == "ping":
        record.status = "processed"
        db.commit()
        return {"status": "ok", "event": "ping"}
    if event in ("pull_request", "push"):
        repo = db.query(Repository).filter_by(full_name=repo_name).first()
        if not repo:
            record.status = "ignored"
            db.commit()
            return {"status": "ignored", "reason": "repository not connected"}
        if event == "push":
            record.status = "processed"
            db.commit()
            return {"status": "queued", "note": "push indexing is queued via reindex"}
        action = data.get("action")
        if action not in ("opened", "synchronize", "reopened"):
            record.status = "ignored"
            db.commit()
            return {"status": "ignored", "reason": f"action {action} not handled"}
        pr_data = data.get("pull_request") or {}
        pr = db.query(PullRequest).filter_by(repo_id=repo.id,
                                             number=pr_data.get("number")).first()
        if not pr:
            pr = PullRequest(repo_id=repo.id, number=pr_data.get("number", 0),
                             title=pr_data.get("title", ""), author=(pr_data.get("user") or {}).get("login", ""),
                             base_sha=(pr_data.get("base") or {}).get("sha", ""),
                             head_sha=pr_data.get("head_sha", ""))
            db.add(pr)
            db.commit()
        else:
            pr.head_sha = pr_data.get("head_sha", pr.head_sha)
            db.commit()
        # fetch diff + enqueue (never review inside the webhook request)
        try:
            gh = GitHubClient()
            pr.diff_text = gh.get_pr_diff(repo_name, pr.number)
            db.commit()
        except Exception as e:
            record.status = "failed"
            db.commit()
            return {"status": "error", "reason": f"could not fetch PR diff: {e}"}
        enqueue_review(pr.id)
        record.status = "processed"
        db.commit()
        return {"status": "queued", "pr": pr.number}
    record.status = "ignored"
    db.commit()
    return {"status": "ignored", "event": event}

# ------------------------------------------------------------------ demo
DEMO_DIFF = """diff --git a/app/orders.py b/app/orders.py
--- a/app/orders.py
+++ b/app/orders.py
@@ -1,4 +1,11 @@
 from app.db import run_query
 
 
 def get_order(order_id):
-    return run_query("SELECT * FROM orders WHERE id = %s", (order_id,))
+    sql = f"SELECT * FROM orders WHERE id = '{order_id}'"
+    return run_query(sql)
+
+
+def average_price(prices):
+    total = sum(prices)
+    return total / len(prices)
"""

def _demo_files() -> dict[str, str]:
    import os
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "fixtures", "sample_repo")
    out = {}
    for root, _dirs, files in os.walk(base):
        for fn in files:
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, base)
            out[rel] = open(fp).read()
    return out

@app.post("/api/demo/seed")
def demo_seed(db: Session = Depends(get_db)):
    """Seed the labelled demo: demo user + demo repo + index + PR #42 +
    a real end-to-end review. No GitHub credentials needed."""
    user = db.query(User).filter_by(email="demo@codesentry.dev").first()
    if not user:
        h, salt = hash_password("demo1234")
        user = User(email="demo@codesentry.dev", password_hash=h, password_salt=salt,
                    name="Demo Reviewer", role="reviewer")
        db.add(user)
        db.commit()
    repo = db.query(Repository).filter_by(full_name="demo/shop-api").first()
    if not repo:
        repo = Repository(full_name="demo/shop-api", name="shop-api", owner_id=user.id,
                          is_demo=True, languages=["python", "javascript"])
        db.add(repo)
        db.commit()
        _ensure_settings(db, repo)
    files = _demo_files()
    st = _ensure_settings(db, repo)
    repo.index_status = "indexing"
    db.commit()
    stats = index_files(db, repo, files, head_sha="demo-head-42", excludes=st.excluded_paths)
    repo.index_status = "indexed"
    repo.head_sha = "demo-head-42"
    repo.last_indexed_at = datetime.now(timezone.utc)
    db.commit()
    pr = db.query(PullRequest).filter_by(repo_id=repo.id, number=42).first()
    if not pr:
        pr = PullRequest(repo_id=repo.id, number=42, title="Add order lookup + average price",
                         author="demo-author", base_sha="demo-base", head_sha="demo-head-42",
                         diff_text=DEMO_DIFF)
        db.add(pr)
        db.commit()
    existing = db.query(ReviewRun).filter_by(pr_id=pr.id, status="completed").first()
    if existing:
        run = existing
    else:
        run = run_review(db, repo, pr, files)
    findings = db.query(Finding).filter_by(run_id=run.id).all()
    return {"token": create_token(user), "demo_login": "demo@codesentry.dev",
            "demo_password": "demo1234", "repo_id": repo.id, "pr_number": 42,
            "index_stats": stats, "run_id": run.id, "status": run.status,
            "gate_result": run.gate_result, "summary": run.summary,
            "findings": [finding_out(f) for f in findings]}
