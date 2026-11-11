"""Incremental indexing.

Only files whose content hash changed are re-parsed / re-embedded; obsolete
symbols and their call-graph edges are removed; untouched files are never
re-embedded. A full re-index is an explicit admin action (POST reindex).
"""
from __future__ import annotations
import fnmatch, hashlib
from database.models import IndexedFile, Symbol, CallEdge
from indexer.extractors import extract_symbols, content_hash
from indexer.call_graph import build_call_graph
from indexer.embeddings import embed
from indexer.parsers import language_for_path, is_generated_or_minified, PARSER_BACKEND

DEFAULT_EXCLUDES = ["**/node_modules/**", "**/.venv/**", "**/dist/**", "**/build/**",
                    "**/*.min.js", "**/migrations/**", "**/__pycache__/**", "**/.git/**",
                    "**/vendor/**", "**/*.lock", "**/*.map"]

def _excluded(path: str, patterns) -> bool:
    return any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch("/" + path, p)
               for p in patterns)

def index_files(db, repo, files: dict[str, str], head_sha: str = "",
                excludes=None) -> dict:
    """files: {path: source}. Returns stats: indexed/changed/skipped/generated."""
    excludes = excludes if excludes is not None else DEFAULT_EXCLUDES
    stats = {"indexed": 0, "changed": 0, "unchanged": 0, "skipped": 0,
             "generated": 0, "symbols": 0, "parser": PARSER_BACKEND}
    all_symbols = []
    for path, source in sorted(files.items()):
        lang = language_for_path(path)
        if lang is None or _excluded(path, excludes):
            stats["skipped"] += 1
            continue
        if is_generated_or_minified(path, source):
            stats["generated"] += 1
            continue
        h = content_hash(source)
        existing = db.query(IndexedFile).filter_by(repo_id=repo.id, path=path).first()
        if existing and existing.content_hash == h:
            stats["unchanged"] += 1
            for s in db.query(Symbol).filter_by(file_id=existing.id).all():
                all_symbols.append(s)
            continue
        stats["changed"] += 1
        symbols = extract_symbols(path, source)
        if existing:
            db.query(Symbol).filter_by(file_id=existing.id).delete()
            db.query(CallEdge).filter_by(repo_id=repo.id, file_path=path).delete()
            existing.content_hash = h
            existing.head_sha = head_sha
            existing.language = lang
            file_row = existing
        else:
            file_row = IndexedFile(repo_id=repo.id, path=path, language=lang,
                                   content_hash=h, head_sha=head_sha)
            db.add(file_row)
            db.flush()
        for s in symbols:
            emb_text = f"{s.qualified_name}\n{s.signature}\n{s.docstring}\n{s.body}"
            db.add(Symbol(repo_id=repo.id, file_id=file_row.id,
                          qualified_name=s.qualified_name, kind=s.kind,
                          language=lang, path=path, start_line=s.start_line,
                          end_line=s.end_line, signature=s.signature,
                          docstring=s.docstring, body=s.body,
                          content_hash=hashlib.sha256(emb_text.encode()).hexdigest(),
                          commit_sha=head_sha, embedding=embed(emb_text),
                          imports_json=s.imports))
            stats["symbols"] += 1
        stats["indexed"] += 1
    # Rebuild call-graph edges for the whole repo from stored symbols
    # (cheap at v1 scale; edges for unchanged files are re-derived identically).
    db.flush()  # pending Symbol rows must be visible to the rebuild query
    db.query(CallEdge).filter_by(repo_id=repo.id).delete()
    db_symbols = db.query(Symbol).filter_by(repo_id=repo.id).all()
    # SymbolInfo-like view for the graph builder
    class _S:
        def __init__(self, row):
            self.qualified_name = row.qualified_name
            self.path = row.path
            self.imports = row.imports_json or []
            self.calls = _calls_from_body(row.body)
    def _calls_from_body(body: str):
        import re
        # skip the signature/def line: it is not a call (it would create a self-edge)
        lines = (body or "").splitlines()[1:]
        keywords = {"if", "elif", "else", "for", "while", "return", "and", "or", "not",
                    "with", "assert", "raise", "yield", "print", "isinstance", "len",
                    "sum", "str", "int", "list", "dict", "set", "range"}
        return [(m.group(1), 0) for m in re.finditer(r"([A-Za-z_][\w\.]*)\s*\(", "\n".join(lines))
                if m.group(1).split(".")[-1] not in keywords]
    infos = [_S(r) for r in db_symbols]
    name_to_id = {r.qualified_name: r.id for r in db_symbols}
    short_to_id = {}
    for r in db_symbols:
        short_to_id.setdefault(r.qualified_name.split(".")[-1], r.id)
    for e in build_call_graph(infos):
        callee_id = name_to_id.get(e.callee_symbol) if e.callee_symbol else None
        if callee_id is None and e.resolved:
            callee_id = short_to_id.get(e.callee.split(".")[-1])
        caller_id = name_to_id.get(e.caller)
        db.add(CallEdge(repo_id=repo.id, caller_id=caller_id, caller_name=e.caller,
                        callee_name=e.callee, callee_id=callee_id,
                        file_path=e.file_path, line=e.line, resolved=e.resolved))
    db.commit()
    return stats
