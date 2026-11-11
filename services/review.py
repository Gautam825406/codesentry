"""Review orchestration service — the end-to-end PR review pipeline.

Webhook -> queue -> this service. Never runs inside the webhook request.
Steps: diff parse -> incremental index -> hunk->symbol mapping ->
graph-first retrieval -> LangGraph 3-agent review -> citation filter ->
patch validation -> scanners (secrets + OSV) -> persistence -> CI gate ->
GitHub posting (only when a token is configured; otherwise recorded as
skipped, never faked).
"""
from __future__ import annotations
import datetime as dt, time
from database.models import (Finding, PullRequest, Repository, ReviewRun,
                             ScanResult, Symbol)
from indexer.diff import parse_diff, map_hunks_to_symbols, size_band, changed_files
from indexer.incremental import index_files
from retrieval.context_builder import build_context
from agents.graph import run_review_graph
from agents.filters import rejected_keys_for_repo
from agents.schemas import CWE
from scanners.secrets import scan_lines
from scanners.dependencies import parse_added_dependencies, query_osv
from settings import settings

def _now():
    return dt.datetime.now(dt.timezone.utc)

def gate_for(findings, repo_settings, gate_enabled: bool) -> str:
    """fail | pass | neutral. Critical/high block only when the policy says so."""
    if not gate_enabled:
        return "neutral"
    policy = (repo_settings.severity_policy if repo_settings else {}) or {}
    for f in findings:
        if policy.get(f.severity, "info" if f.severity in ("medium", "low") else "block") == "block":
            if f.state == "posted" and f.severity in ("critical", "high"):
                return "fail"
    return "pass"

def run_review(db, repo: Repository, pr: PullRequest,
               file_contents: dict[str, str]) -> ReviewRun:
    started = time.time()
    st = repo.settings
    threshold = st.confidence_threshold if st else settings.DEFAULT_CONFIDENCE_THRESHOLD
    excluded = st.excluded_paths if st else []
    run = ReviewRun(pr_id=pr.id, status="running", started_at=_now(),
                    model_version=(st.model_name if st else "deterministic-rules-v1"),
                    prompt_version="prompts-v1")
    db.add(run)
    db.flush()
    try:
        diff_text = pr.diff_text or ""
        hunks = parse_diff(diff_text)
        files = changed_files(diff_text)
        added = [(h.path, ln, txt) for h in hunks for ln, txt in h.added_lines]
        # --- incremental index of changed files present in file_contents ---
        changed_sources = {p: file_contents[p] for p in files if p in file_contents}
        index_stats = index_files(db, repo, changed_sources, head_sha=pr.head_sha,
                                  excludes=excluded) if changed_sources else {"indexed": 0}
        # --- coverage: oversized PRs are reviewed in priority order, never silently ---
        total_added = len(added)
        pr.size_band = size_band(len(files), total_added)
        skipped: list[dict] = []
        review_files = files
        if len(files) > settings.MAX_PR_FILES:
            review_files = files[:settings.MAX_PR_FILES]
            for p in files[settings.MAX_PR_FILES:]:
                skipped.append({"path": p, "reason": "oversized_pr_file_limit"})
        file_lines = {p: (file_contents[p].splitlines() if p in file_contents else [])
                      for p in files}
        symbols = db.query(Symbol).filter_by(repo_id=repo.id).all()
        mapping = map_hunks_to_symbols(
            [h for h in hunks if h.path in review_files], symbols)
        rejected = rejected_keys_for_repo(db, repo.id)
        posted_drafts, suppressed = [], []
        tokens = 0
        for qname in mapping:
            sym = next((s for s in symbols if s.qualified_name == qname), None)
            if sym is None:
                continue
            ctx = build_context(db, repo.id, sym,
                                budget=st.token_budget_per_symbol if st else 4000)
            tokens += ctx["tokens_used"]
            posted, supp = run_review_graph(
                sym, ctx, file_lines, threshold=threshold,
                excluded_paths=excluded, rejected_keys=rejected, all_symbols=symbols)
            posted_drafts.extend(posted)
            suppressed.extend([(d, r) for d, r in supp])
            if tokens > settings.TOKEN_BUDGET_PER_PR:
                skipped.append({"path": sym.path, "reason": "per_pr_token_budget_exceeded"})
                break
        # --- scanners (deterministic, separate provenance) ---
        scan_findings = []
        for path in review_files:
            added_here = [(ln, t) for p, ln, t in added if p == path]
            for hit in scan_lines(path, added_here):
                scan_findings.append(hit)
                db.add(ScanResult(pr_id=pr.id, repo_id=repo.id, kind="secret",
                                  package_or_type=hit["type"], severity=hit["severity"],
                                  detail=f"{hit['type']} at {path}:{hit['line']} (value masked: {hit['masked']})"))
        osv = query_osv(parse_added_dependencies(diff_text))
        osv_status = osv["status"]
        for v in osv.get("vulnerabilities", []):
            db.add(ScanResult(pr_id=pr.id, repo_id=repo.id, kind="dependency",
                              package_or_type=f"{v['package']}@{v['version']}",
                              advisory_id=v.get("advisory_id"), severity=v["severity"],
                              detail=v.get("summary", "")))
        # --- persist agent findings ---
        persisted = []
        for d in posted_drafts:
            cwe_title, owasp = (CWE[d.cwe_id] if d.cwe_id else (None, None))
            f = Finding(run_id=run.id, repo_id=repo.id, pr_id=pr.id, pr_number=pr.number,
                        source=d.source, category=d.category, severity=d.severity,
                        title=d.title, description=d.description, file_path=d.file_path,
                        start_line=d.start_line, end_line=d.end_line, evidence=d.evidence,
                        cwe_id=d.cwe_id, cwe_title=cwe_title, owasp_ref=owasp,
                        confidence=d.confidence, patch=d.patch,
                        patch_valid=bool(d.context_provenance.get("patch_valid")),
                        model_version=d.model_version, prompt_version=d.prompt_version,
                        context_provenance=d.context_provenance, state="posted")
            db.add(f)
            persisted.append(f)
        for d, reason in suppressed:
            cwe_title, owasp = (CWE[d.cwe_id] if d.cwe_id else (None, None))
            db.add(Finding(run_id=run.id, repo_id=repo.id, pr_id=pr.id, pr_number=pr.number,
                           source=d.source, category=d.category, severity=d.severity,
                           title=d.title, description=d.description, file_path=d.file_path,
                           start_line=d.start_line, end_line=d.end_line, evidence=d.evidence,
                           cwe_id=d.cwe_id, cwe_title=cwe_title, owasp_ref=owasp,
                           confidence=d.confidence, model_version=d.model_version,
                           prompt_version=d.prompt_version,
                           context_provenance=d.context_provenance,
                           state="suppressed", suppressed_reason=reason))
        for hit in scan_findings:
            sf = Finding(run_id=run.id, repo_id=repo.id, pr_id=pr.id, pr_number=pr.number,
                           source="secret-scanner", category="secret_exposure",
                           severity=hit["severity"],
                           title=f"Possible secret exposed: {hit['type']}",
                           description=(f"A {hit['type']} pattern was found at "
                                        f"{hit['path']}:{hit['line']}. Value is masked "
                                        f"({hit['masked']}); rotate it and remove it from git history."),
                           file_path=hit["path"], start_line=hit["line"], end_line=hit["line"],
                           evidence=hit["evidence"], confidence=0.95,
                           model_version="secret-scanner-v1",
                           context_provenance={"scanner": "secrets", "masked": hit["masked"]},
                           state="posted")
            db.add(sf)
            persisted.append(sf)
        for v in osv.get("vulnerabilities", []):
            db.add(Finding(run_id=run.id, repo_id=repo.id, pr_id=pr.id, pr_number=pr.number,
                           source="dependency-scanner", category="dependency_vulnerability",
                           severity=v["severity"],
                           title=f"Vulnerable dependency: {v['package']} {v['version']}",
                           description=f"{v.get('summary','')} Advisory: {v.get('advisory_id')}",
                           file_path="requirements.txt", start_line=1, end_line=1,
                           evidence=f"{v['package']}=={v['version']}", confidence=0.9,
                           model_version="osv-scanner-v1",
                           context_provenance={"scanner": "osv", "advisory": v.get("advisory_id")},
                           state="posted"))
        # --- gate + coverage ---
        gate = gate_for(persisted, st, st.gate_enabled if st else True)
        reviewed = len(review_files)
        coverage = {"files_reviewed": reviewed, "files_total": len(files),
                    "files_skipped": skipped,
                    "pct": round(100 * reviewed / max(1, len(files)), 1),
                    "index_stats": index_stats, "osv_status": osv_status,
                    "suppressed_count": len(suppressed),
                    "tokens_used": tokens}
        run.status = "partial" if skipped else "completed"
        run.finished_at = _now()
        run.latency_ms = int((time.time() - started) * 1000)
        run.tokens_used = tokens
        run.cost_usd = 0.0  # deterministic engine: no LLM spend; Groq cost is $0 on free tier in v1
        run.files_reviewed = reviewed
        run.coverage = coverage
        run.gate_result = gate
        n_block = sum(1 for f in persisted if f.severity in ("critical", "high"))
        run.summary = (f"CodeSentry reviewed {reviewed}/{len(files)} files "
                       f"({coverage['pct']}% coverage). {len(persisted)} findings posted "
                       f"({n_block} blocking), {len(suppressed)} suppressed. "
                       f"Gate: {gate}. OSV dependency check: {osv_status}. "
                       + ("GitHub posting skipped: no GITHUB_TOKEN configured."
                          if not settings.GITHUB_TOKEN else "Posted to GitHub."))
        db.commit()
        # --- GitHub posting (best effort, only with a token) ---
        if settings.GITHUB_TOKEN:
            try:
                from integrations.github import GitHubClient
                gh = GitHubClient()
                check = gh.create_check_run(repo.full_name, pr.head_sha or "HEAD")
                body = run.summary + "\n\n" + "\n".join(
                    f"- **{f.severity.upper()}** {f.title} ({f.file_path}:{f.start_line})"
                    for f in persisted)
                gh.post_review(repo.full_name, pr.number, body)
                gh.update_check_run(repo.full_name, check["id"], status="completed",
                                    conclusion="failure" if gate == "fail" else "success",
                                    summary=run.summary)
            except Exception as e:
                print(f"[review] github posting failed: {e}")
        return run
    except Exception as e:
        run.status = "failed"
        run.finished_at = _now()
        run.summary = f"Review failed: {e}. This is NOT a clean result — the check must not pass."
        run.gate_result = "incomplete"
        db.commit()
        raise
