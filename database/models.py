"""SQLAlchemy models — PostgreSQL is the system of record; SQLite is the
local fallback. Embeddings are stored as JSON arrays in v1 (see
docs/DATABASE.md: the pgvector migration in database/migrations/versions/
adds a `vector(128)` column on Postgres; SQLite deployments use JSON +
in-memory cosine, which is stated honestly, not hidden)."""
from __future__ import annotations
import datetime as dt
from sqlalchemy import (Boolean, Column, DateTime, Float, ForeignKey, Integer,
                        JSON, String, Text, UniqueConstraint, Index)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def _now():
    return dt.datetime.now(dt.timezone.utc)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    password_salt = Column(String(64), nullable=False)
    name = Column(String(255), default="")
    role = Column(String(32), default="user")  # user | admin | reviewer
    github_login = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=_now)

class Installation(Base):
    __tablename__ = "installations"
    id = Column(Integer, primary_key=True)
    github_installation_id = Column(Integer, unique=True, nullable=False)
    account_login = Column(String(255), default="")
    created_at = Column(DateTime, default=_now)

class Repository(Base):
    __tablename__ = "repositories"
    id = Column(Integer, primary_key=True)
    installation_id = Column(Integer, ForeignKey("installations.id"), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    full_name = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), default="")
    default_branch = Column(String(64), default="main")
    languages = Column(JSON, default=list)
    clone_url = Column(String(512), default="")
    github_repo_id = Column(Integer, nullable=True)
    head_sha = Column(String(64), default="")
    index_status = Column(String(32), default="not_indexed")  # not_indexed|indexing|indexed|failed|paused
    last_indexed_at = Column(DateTime, nullable=True)
    is_demo = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)
    settings = relationship("RepoSettings", back_populates="repo", uselist=False,
                            cascade="all, delete-orphan")

class RepoSettings(Base):
    __tablename__ = "repo_settings"
    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), unique=True, nullable=False)
    enabled_languages = Column(JSON, default=lambda: ["python", "javascript", "typescript"])
    included_paths = Column(JSON, default=lambda: ["**/*.py", "**/*.js", "**/*.ts", "**/*.tsx"])
    excluded_paths = Column(JSON, default=lambda: ["**/node_modules/**", "**/.venv/**", "**/dist/**",
                                                   "**/*.min.js", "**/migrations/**", "**/__pycache__/**"])
    confidence_threshold = Column(Float, default=0.60)
    severity_policy = Column(JSON, default=lambda: {"critical": "block", "high": "block",
                                                    "medium": "info", "low": "info"})
    gate_enabled = Column(Boolean, default=True)
    model_provider = Column(String(32), default="deterministic")
    model_name = Column(String(128), default="deterministic-rules-v1")
    token_budget_per_symbol = Column(Integer, default=4000)
    daily_cost_limit_usd = Column(Float, default=5.0)
    training_opt_in = Column(Boolean, default=False)  # OFF by default (PRD §14/§8.5)
    index_paused = Column(Boolean, default=False)
    repo = relationship("Repository", back_populates="settings")

class IndexedFile(Base):
    __tablename__ = "indexed_files"
    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False, index=True)
    path = Column(String(512), nullable=False)
    language = Column(String(32), default="")
    content_hash = Column(String(64), default="")
    head_sha = Column(String(64), default="")
    generated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_now)
    __table_args__ = (UniqueConstraint("repo_id", "path", name="uq_file_repo_path"),)

class Symbol(Base):
    __tablename__ = "symbols"
    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False, index=True)
    file_id = Column(Integer, ForeignKey("indexed_files.id"), nullable=False)
    qualified_name = Column(String(512), nullable=False, index=True)
    kind = Column(String(32), default="function")  # function|method|class|module
    language = Column(String(32), default="")
    path = Column(String(512), nullable=False)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    signature = Column(Text, default="")
    docstring = Column(Text, default="")
    body = Column(Text, default="")
    content_hash = Column(String(64), default="")
    commit_sha = Column(String(64), default="")
    embedding = Column(JSON, nullable=True)  # list[float], dim 128 in v1
    imports_json = Column("imports", JSON, default=list)
    __table_args__ = (Index("ix_symbol_repo_path_name", "repo_id", "path", "qualified_name"),)

class CallEdge(Base):
    __tablename__ = "call_edges"
    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False, index=True)
    caller_id = Column(Integer, ForeignKey("symbols.id"), nullable=True)
    caller_name = Column(String(512), default="")
    callee_name = Column(String(512), default="")
    callee_id = Column(Integer, ForeignKey("symbols.id"), nullable=True)
    file_path = Column(String(512), default="")
    line = Column(Integer, default=0)
    resolved = Column(Boolean, default=False)

class PullRequest(Base):
    __tablename__ = "pull_requests"
    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False, index=True)
    number = Column(Integer, nullable=False)
    title = Column(String(512), default="")
    author = Column(String(255), default="")
    base_sha = Column(String(64), default="")
    head_sha = Column(String(64), default="")
    state = Column(String(32), default="open")
    size_band = Column(String(16), default="small")  # small|medium|large|oversized
    diff_text = Column(Text, default="")
    created_at = Column(DateTime, default=_now)
    __table_args__ = (UniqueConstraint("repo_id", "number", name="uq_pr_repo_number"),)

class ReviewRun(Base):
    __tablename__ = "review_runs"
    id = Column(Integer, primary_key=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=False, index=True)
    status = Column(String(32), default="queued")  # queued|running|completed|failed|partial
    model_version = Column(String(128), default="deterministic-rules-v1")
    adapter_version = Column(String(128), nullable=True)
    prompt_version = Column(String(32), default="prompts-v1")
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    tokens_used = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    latency_ms = Column(Integer, default=0)
    coverage = Column(JSON, default=dict)  # {files_reviewed, files_skipped:[{path,reason}], pct}
    files_reviewed = Column(Integer, default=0)
    summary = Column(Text, default="")
    gate_result = Column(String(32), default="")  # pass|fail|neutral|incomplete

class Finding(Base):
    __tablename__ = "findings"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("review_runs.id"), nullable=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False, index=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=True)
    pr_number = Column(Integer, default=0)
    source = Column(String(32), default="security")  # security|logic|style|secret-scanner|dependency-scanner
    category = Column(String(64), default="")
    severity = Column(String(16), default="medium")  # critical|high|medium|low
    title = Column(String(512), default="")
    description = Column(Text, default="")
    file_path = Column(String(512), default="")
    start_line = Column(Integer, default=0)
    end_line = Column(Integer, default=0)
    evidence = Column(Text, default="")
    cwe_id = Column(String(16), nullable=True)
    cwe_title = Column(String(255), nullable=True)
    owasp_ref = Column(String(128), nullable=True)
    confidence = Column(Float, default=0.0)
    patch = Column(Text, nullable=True)
    patch_valid = Column(Boolean, default=False)
    model_version = Column(String(128), default="deterministic-rules-v1")
    prompt_version = Column(String(32), default="prompts-v1")
    context_provenance = Column(JSON, default=dict)
    state = Column(String(32), default="posted")  # posted|suppressed|fixed|dismissed|superseded
    suppressed_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=_now)
    __table_args__ = (Index("ix_finding_repo_pr", "repo_id", "pr_number"),)

class FeedbackEvent(Base):
    __tablename__ = "feedback_events"
    id = Column(Integer, primary_key=True)
    finding_id = Column(Integer, ForeignKey("findings.id"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    actor_name = Column(String(255), default="")
    verdict = Column(String(32), nullable=False)  # accept|fixed|reject_wrong|reject_not_worth_fixing|ignore
    reason = Column(Text, default="")
    created_at = Column(DateTime, default=_now)

class ScanResult(Base):
    __tablename__ = "scan_results"
    id = Column(Integer, primary_key=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False, index=True)
    kind = Column(String(32), default="secret")  # secret|dependency
    package_or_type = Column(String(255), default="")
    advisory_id = Column(String(128), nullable=True)
    severity = Column(String(16), default="medium")
    detail = Column(Text, default="")
    created_at = Column(DateTime, default=_now)

class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=True)
    version = Column(String(64), unique=True, nullable=False)
    train_count = Column(Integer, default=0)
    val_count = Column(Integer, default=0)
    heldout_count = Column(Integer, default=0)
    source = Column(String(255), default="feedback")
    metrics_json = Column("metrics", JSON, default=dict)
    created_at = Column(DateTime, default=_now)

class LoRAAdapter(Base):
    __tablename__ = "lora_adapters"
    id = Column(Integer, primary_key=True)
    dataset_version_id = Column(Integer, ForeignKey("dataset_versions.id"), nullable=True)
    version = Column(String(64), unique=True, nullable=False)
    base_model = Column(String(128), default="Qwen/Qwen2.5-Coder-1.5B")
    status = Column(String(32), default="not_started")  # not_started|training|evaluating|ready|failed|promoted|rolled_back
    metrics_json = Column("metrics", JSON, default=dict)
    promoted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_now)

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True)
    actor = Column(String(255), default="")
    action = Column(String(128), nullable=False)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=True)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_now)

class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    id = Column(Integer, primary_key=True)
    delivery_id = Column(String(128), unique=True, nullable=False, index=True)
    event = Column(String(64), default="")
    repo_full_name = Column(String(255), default="")
    payload = Column(JSON, default=dict)
    status = Column(String(32), default="received")  # received|processed|duplicate|failed|ignored
    created_at = Column(DateTime, default=_now)
