#!/usr/bin/env python3
"""Demo: index the sample repo and run a real review of PR #42.

Usage:  python scripts/demo_review.py [--reset]
Prints the cited finding(s), CWE, patch and CI gate outcome.
No GitHub credentials needed.
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()
    if args.reset and os.path.exists("codesentry.db"):
        os.remove("codesentry.db")
    from database.session import init_db, SessionLocal
    from database.models import Repository, RepoSettings, PullRequest, Finding
    from indexer.incremental import index_files
    from services.review import run_review
    from apps.api.main import DEMO_DIFF, _demo_files
    init_db()
    db = SessionLocal()
    files = _demo_files()
    repo = db.query(Repository).filter_by(full_name="demo/shop-api").first()
    if not repo:
        repo = Repository(full_name="demo/shop-api", name="shop-api", is_demo=True)
        db.add(repo); db.commit()
        db.add(RepoSettings(repo_id=repo.id)); db.commit()
    stats = index_files(db, repo, files, head_sha="demo-head-42")
    print(f"Indexed: {stats}")
    pr = db.query(PullRequest).filter_by(repo_id=repo.id, number=42).first()
    if not pr:
        pr = PullRequest(repo_id=repo.id, number=42, title="Add order lookup + average price",
                         author="demo-author", base_sha="demo-base",
                         head_sha="demo-head-42", diff_text=DEMO_DIFF)
        db.add(pr); db.commit()
    run = run_review(db, repo, pr, files)
    print(f"\nRun #{run.id}: status={run.status} gate={run.gate_result} "
          f"latency={run.latency_ms}ms tokens={run.tokens_used}")
    print(run.summary)
    for f in db.query(Finding).filter_by(run_id=run.id).order_by(Finding.id).all():
        print(f"\n[{f.severity.upper()}] {f.title} ({f.source}, {f.category})")
        print(f"  {f.file_path}:{f.start_line}-{f.end_line}  CWE={f.cwe_id} "
              f"({f.cwe_title or '-'})  confidence={f.confidence}  state={f.state}"
              + (f"  suppressed: {f.suppressed_reason}" if f.state == "suppressed" else ""))
        print(f"  evidence: {f.evidence!r}")
        if f.patch:
            print(f"  patch (valid={f.patch_valid}):\n{f.patch}")
    db.close()

if __name__ == "__main__":
    main()
