"""LangGraph multi-agent review graph (PRD §8.3).

Supervisor fans out to three specialist agent nodes (security, logic,
style) over the same context pack; a filter node validates every finding
against the citation/confidence/CWE contract; a patch node attaches
validated patches only. Agents return findings ONLY through the
Pydantic-validated FindingDraft schema.

Note: parallel nodes write SEPARATE state keys (security_drafts etc.)
because LangGraph merges parallel updates per-key — three nodes writing
one `drafts` key would silently overwrite each other.
"""
from __future__ import annotations
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from agents.security import run_security
from agents.logic import run_logic
from agents.style import run_style
from agents.filters import filter_findings
from agents.patches import generate_patch

class ReviewState(TypedDict, total=False):
    symbol: object
    context: dict
    file_lines: dict
    all_symbols: list
    threshold: float
    excluded_paths: list
    rejected_keys: set
    security_drafts: list
    logic_drafts: list
    style_drafts: list
    posted: list
    suppressed: list

def _security_node(state: ReviewState) -> dict:
    return {"security_drafts": run_security(state["symbol"], state["context"], state["file_lines"])}

def _logic_node(state: ReviewState) -> dict:
    return {"logic_drafts": run_logic(state["symbol"], state["context"], state["file_lines"])}

def _style_node(state: ReviewState) -> dict:
    return {"style_drafts": run_style(state["symbol"], state["context"], state["file_lines"],
                                     state.get("all_symbols"))}

def _filter_node(state: ReviewState) -> dict:
    drafts = (state.get("security_drafts", []) + state.get("logic_drafts", [])
              + state.get("style_drafts", []))
    posted, suppressed = filter_findings(
        drafts, file_lines=state["file_lines"],
        threshold=state.get("threshold", 0.6),
        excluded_paths=state.get("excluded_paths") or [],
        rejected_keys=state.get("rejected_keys") or set())
    return {"posted": posted, "suppressed": suppressed}

def _patch_node(state: ReviewState) -> dict:
    posted = []
    for d in state.get("posted", []):
        patch, ok = generate_patch(d, state["file_lines"].get(d.file_path, []))
        d.patch = patch
        # patch_valid is recorded on the persisted Finding, not the draft
        d.context_provenance = {**d.context_provenance, "patch_valid": bool(ok and patch)}
        posted.append(d)
    return {"posted": posted}

def build_review_graph():
    g = StateGraph(ReviewState)
    g.add_node("security", _security_node)
    g.add_node("logic", _logic_node)
    g.add_node("style", _style_node)
    g.add_node("filter", _filter_node)
    g.add_node("patch", _patch_node)
    g.add_edge(START, "security")
    g.add_edge(START, "logic")
    g.add_edge(START, "style")
    g.add_edge("security", "filter")
    g.add_edge("logic", "filter")
    g.add_edge("style", "filter")
    g.add_edge("filter", "patch")
    g.add_edge("patch", END)
    return g.compile()

def run_review_graph(symbol, context, file_lines, *, threshold=0.6,
                     excluded_paths=None, rejected_keys=None, all_symbols=None):
    graph = build_review_graph()
    result = graph.invoke({
        "symbol": symbol, "context": context, "file_lines": file_lines,
        "all_symbols": all_symbols or [], "threshold": threshold,
        "excluded_paths": excluded_paths or [], "rejected_keys": rejected_keys or set(),
        "security_drafts": [], "logic_drafts": [], "style_drafts": [],
        "posted": [], "suppressed": []})
    return result.get("posted", []), result.get("suppressed", [])
