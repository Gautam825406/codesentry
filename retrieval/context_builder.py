"""Graph-first context retrieval (PRD §8.2).

Order, per changed symbol:
  1. the changed symbol itself (always)
  2. direct callers
  3. direct callees
  4. related tests (test files referencing the symbol)
  5. vector-similar symbols (fills remaining budget)
  6. recent file history summary (low priority; recorded, not fetched in v1
     — no git history is stored locally, so this tier is honestly empty)
Per-symbol token budget is enforced; included AND dropped pieces are logged
in the returned provenance so a review is auditable.
"""
from __future__ import annotations
from database.models import Symbol, CallEdge
from retrieval.vector_retriever import similar_symbols

def _tokens(text: str) -> int:
    return max(1, len(text or "") // 4)

def build_context(db, repo_id: int, symbol: Symbol, budget: int = 4000) -> dict:
    pieces: list[dict] = []
    dropped: list[dict] = []
    used = 0

    def _add(kind: str, name: str, text: str, priority: int, path: str = "",
             start_line: int = 0, end_line: int = 0):
        nonlocal used
        cost = _tokens(text)
        item = {"kind": kind, "name": name, "text": text, "tokens": cost,
                "path": path, "start_line": start_line, "end_line": end_line}
        if used + cost <= budget or kind == "changed_symbol":
            pieces.append(item)
            used += cost
        else:
            dropped.append({"kind": kind, "name": name, "tokens": cost,
                            "reason": "token_budget"})

    _add("changed_symbol", symbol.qualified_name, symbol.body or "", 1,
         symbol.path, symbol.start_line, symbol.end_line)
    # callers: edges where this symbol is the callee
    callers = (db.query(CallEdge).filter_by(repo_id=repo_id, callee_id=symbol.id).all())
    for e in callers:
        row = db.query(Symbol).filter_by(id=e.caller_id).first() if e.caller_id else None
        if row:
            _add("caller", row.qualified_name, row.body or "", 2,
                 row.path, row.start_line, row.end_line)
    # callees
    callees = db.query(CallEdge).filter_by(repo_id=repo_id, caller_id=symbol.id).all()
    for e in callees:
        row = db.query(Symbol).filter_by(id=e.callee_id).first() if e.callee_id else None
        if row:
            _add("callee", row.qualified_name, row.body or "", 2,
                 row.path, row.start_line, row.end_line)
        elif not e.resolved:
            dropped.append({"kind": "callee_unresolved", "name": e.callee_name,
                            "tokens": 0, "reason": "unresolved_call"})
    # related tests
    tests = (db.query(Symbol).filter_by(repo_id=repo_id)
             .filter(Symbol.path.like("%test%")).all())
    for t in tests:
        if symbol.qualified_name.split(".")[-1] in (t.body or ""):
            _add("test", t.qualified_name, t.body or "", 3,
                 t.path, t.start_line, t.end_line)
    # vector-similar, fills remaining budget
    seen = {p["name"] for p in pieces}
    for score, row in similar_symbols(db, repo_id, symbol.body or symbol.qualified_name,
                                      limit=5, exclude_names=seen):
        if score > 0.05:
            _add("similar", row.qualified_name, row.body or "", 4,
                 row.path, row.start_line, row.end_line)
    return {"symbol": symbol.qualified_name, "pieces": pieces, "dropped": dropped,
            "tokens_used": used, "budget": budget,
            "history_summary": "No stored git history in v1; file history tier empty by design."}
