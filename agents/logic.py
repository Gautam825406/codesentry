"""Logic agent — correctness against caller contracts and error paths."""
from __future__ import annotations
import re
from agents.schemas import FindingDraft
from agents.llm import llm_findings

def run_logic(symbol, context: dict, file_lines: dict) -> list[FindingDraft]:
    body = symbol.body or ""
    path, start = symbol.path, symbol.start_line
    findings: list[FindingDraft] = []
    lines = body.splitlines()
    for i, line in enumerate(lines, 1):
        lineno = start + i - 1
        s = line.strip()
        if s == "except:":
            findings.append(FindingDraft(
                source="logic", category="error_handling", severity="medium",
                title="Bare except swallows every error, including KeyboardInterrupt and bugs",
                description="A bare `except:` hides programming errors and makes failures silent. Catch a specific exception type.",
                file_path=path, start_line=lineno, end_line=lineno, evidence=line,
                confidence=0.85, context_provenance={"symbol": symbol.qualified_name}))
        if re.match(r"except\s+(?:Exception|BaseException)\s*:", s):
            nxt = lines[i].strip() if i < len(lines) else ""
            if nxt == "pass":
                findings.append(FindingDraft(
                    source="logic", category="error_handling", severity="medium",
                    title="Exception is caught and silently discarded",
                    description="Catching an exception and doing nothing (`pass`) hides failures from callers and logs.",
                    file_path=path, start_line=lineno, end_line=lineno + 1,
                    evidence="\n".join(lines[i-1:i+1]), confidence=0.88,
                    context_provenance={"symbol": symbol.qualified_name}))
        if re.search(r"/\s*(?:len\s*\(|total|count|\w+)\s*$", s) or re.search(r"/\s*len\(", s):
            # division by a value that can be zero with no guard in the body
            if "if not" not in body and "== 0" not in body and "!= 0" not in body:
                findings.append(FindingDraft(
                    source="logic", category="logic_error", severity="medium",
                    title="Division by a value that can be zero (empty collection / zero divisor)",
                    description="This division has no guard for a zero divisor. An empty input raises ZeroDivisionError at runtime.",
                    file_path=path, start_line=lineno, end_line=lineno, evidence=line,
                    confidence=0.78, context_provenance={"symbol": symbol.qualified_name}))
        m = re.match(r"def\s+\w+\([^)]*=\s*(\[\]|\{\})\s*\)", s)
        if m:
            findings.append(FindingDraft(
                source="logic", category="logic_error", severity="low",
                title="Mutable default argument is shared across calls",
                description="A mutable default (list/dict) is created once and shared between calls; mutations leak into later calls.",
                file_path=path, start_line=lineno, end_line=lineno, evidence=line,
                confidence=0.9, context_provenance={"symbol": symbol.qualified_name}))
        if re.search(r"\bopen\s*\(", s) and "with " not in body.splitlines()[max(0, i - 2):i + 1][0] \
           and not any("with " in l and "open(" in l for l in lines):
            findings.append(FindingDraft(
                source="logic", category="resource_leak", severity="medium",
                title="File opened without a context manager — handle can leak on error",
                description="Use `with open(...) as f:` so the handle is closed even if an exception is raised.",
                file_path=path, start_line=lineno, end_line=lineno, evidence=line,
                confidence=0.8, context_provenance={"symbol": symbol.qualified_name}))
    ctx_text = "\n".join(f"# {p['kind']}: {p['name']}\n{p['text']}" for p in context.get("pieces", []))
    findings.extend(llm_findings("logic", ctx_text, path))
    return findings
