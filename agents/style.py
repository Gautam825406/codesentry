"""Style agent — only opted-in maintainability issues with real cost.
Deliberately narrow: no meaningless style comments (PRD §6)."""
from __future__ import annotations
import hashlib
from agents.schemas import FindingDraft
from agents.llm import llm_findings

def run_style(symbol, context: dict, file_lines: dict, all_symbols=None) -> list[FindingDraft]:
    body = symbol.body or ""
    path, start = symbol.path, symbol.start_line
    findings: list[FindingDraft] = []
    n_lines = symbol.end_line - symbol.start_line + 1
    if n_lines > 60:
        findings.append(FindingDraft(
            source="style", category="maintainability", severity="low",
            title=f"Function is {n_lines} lines long — consider splitting it",
            description="Long functions are harder to test and review. Split at a natural seam (one responsibility per function).",
            file_path=path, start_line=start, end_line=symbol.end_line,
            evidence=(body.splitlines()[0] if body else ""), confidence=0.65,
            context_provenance={"symbol": symbol.qualified_name}))
    if all_symbols:
        norm = " ".join((body or "").split())
        h = hashlib.sha256(norm.encode()).hexdigest()
        for other in all_symbols:
            if other.qualified_name == symbol.qualified_name:
                continue
            if hashlib.sha256(" ".join((other.body or "").split()).encode()).hexdigest() == h \
               and len(norm) > 80:
                findings.append(FindingDraft(
                    source="style", category="duplication", severity="low",
                    title=f"Duplicated logic — identical body to `{other.qualified_name}`",
                    description=f"This function duplicates `{other.qualified_name}` ({other.path}). Extract a shared helper instead of maintaining two copies.",
                    file_path=path, start_line=start, end_line=symbol.end_line,
                    evidence=(body.splitlines()[0] if body else ""), confidence=0.72,
                    context_provenance={"symbol": symbol.qualified_name,
                                        "duplicate_of": other.qualified_name}))
                break
    if (body or "").strip().endswith("pass") and len(body.splitlines()) <= 3:
        findings.append(FindingDraft(
            source="style", category="dead_code", severity="low",
            title="Stub function with only `pass` — dead code introduced by this change",
            description="A function that does nothing was added. Remove it or implement it.",
            file_path=path, start_line=start, end_line=symbol.end_line,
            evidence=(body.splitlines()[0] if body else ""), confidence=0.7,
            context_provenance={"symbol": symbol.qualified_name}))
    ctx_text = "\n".join(f"# {p['kind']}: {p['name']}\n{p['text']}" for p in context.get("pieces", []))
    findings.extend(llm_findings("style", ctx_text, path))
    return findings
