"""Unit tests: retrieval order + token budget; incremental indexing."""
import os
from database.session import SessionLocal
from database.models import Repository, RepoSettings, Symbol
from indexer.incremental import index_files
from retrieval.context_builder import build_context

def _repo_with_fixtures(db):
    repo = db.query(Repository).filter_by(full_name="test/shop-api").first()
    if not repo:
        repo = Repository(full_name="test/shop-api", name="shop-api", is_demo=True)
        db.add(repo); db.commit()
        db.add(RepoSettings(repo_id=repo.id)); db.commit()
        files = {}
        base = "fixtures/sample_repo"
        for root, _d, fns in os.walk(base):
            for fn in fns:
                fp = os.path.join(root, fn)
                files[os.path.relpath(fp, base)] = open(fp).read()
        index_files(db, repo, files, head_sha="test")
    return repo

def test_retrieval_order_graph_first():
    db = SessionLocal()
    repo = _repo_with_fixtures(db)
    sym = db.query(Symbol).filter_by(repo_id=repo.id, qualified_name="get_order").first()
    ctx = build_context(db, repo.id, sym, budget=4000)
    kinds = [p["kind"] for p in ctx["pieces"]]
    assert kinds[0] == "changed_symbol"
    # callers and callees come before vector-similar pieces
    assert "callee" in kinds and "caller" in kinds
    assert kinds.index("callee") < kinds.index("similar") if "similar" in kinds else True
    assert any(p["name"] == "run_query" for p in ctx["pieces"] if p["kind"] == "callee")
    assert any(p["kind"] == "test" for p in ctx["pieces"])

def test_token_budget_drops_low_priority():
    db = SessionLocal()
    repo = _repo_with_fixtures(db)
    sym = db.query(Symbol).filter_by(repo_id=repo.id, qualified_name="get_order").first()
    ctx = build_context(db, repo.id, sym, budget=30)  # tiny budget
    assert ctx["tokens_used"] <= 60  # changed symbol is always included
    assert len(ctx["dropped"]) > 0
    assert all(d["reason"] == "token_budget" for d in ctx["dropped"])

def test_incremental_only_changed_files():
    db = SessionLocal()
    repo = _repo_with_fixtures(db)
    files = {}
    base = "fixtures/sample_repo"
    for root, _d, fns in os.walk(base):
        for fn in fns:
            fp = os.path.join(root, fn)
            files[os.path.relpath(fp, base)] = open(fp).read()
    stats = index_files(db, repo, files, head_sha="test")
    assert stats["unchanged"] == 5 and stats["changed"] == 0
    files["app/orders.py"] = files["app/orders.py"].replace("average_price", "avg_price")
    stats = index_files(db, repo, files, head_sha="test2")
    assert stats["changed"] == 1 and stats["unchanged"] == 4
    # restore
    files["app/orders.py"] = open(os.path.join(base, "app/orders.py")).read()
    index_files(db, repo, files, head_sha="test")
