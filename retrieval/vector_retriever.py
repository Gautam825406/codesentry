"""Vector retrieval over stored symbol embeddings (cosine, repo-scoped)."""
from __future__ import annotations
from indexer.embeddings import embed, cosine

def similar_symbols(db, repo_id: int, query_text: str, limit: int = 5,
                    exclude_names: set | None = None):
    from database.models import Symbol
    q = embed(query_text)
    rows = db.query(Symbol).filter_by(repo_id=repo_id).all()
    scored = []
    for r in rows:
        if exclude_names and r.qualified_name in exclude_names:
            continue
        if not r.embedding:
            continue
        scored.append((cosine(q, r.embedding), r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:limit]
