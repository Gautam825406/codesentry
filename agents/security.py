"""Security agent — injection, auth, deserialisation, traversal, XSS, secrets.

Taint model (heuristic hints, PRD §8.6 — NOT a verified data-flow proof):
  source  = a function parameter / request value in the changed symbol
  taint   = that value interpolated into a string (f-string / + / .format)
  sink    = a dangerous call in the changed symbol, OR in a direct callee
            whose body executes its argument (call-graph context is what
            makes the demo SQL-injection finding possible at all).
A finding is only emitted when source -> taint -> sink is traceable in the
retrieved context; a sink alone, with no tainted input, is not a finding.
"""
from __future__ import annotations
import re
from agents.schemas import FindingDraft
from agents.llm import llm_findings

# sink regex -> (category, cwe, severity, title, confidence)
SINKS = [
    (re.compile(r"\b(?:execute|executemany|executescript)\s*\("), "sql_injection", "CWE-89", "high",
     "SQL query built from unsanitised input reaches a database sink", 0.92),
    (re.compile(r"\.(?:query|raw)\s*\("), "sql_injection", "CWE-89", "high",
     "SQL query built from unsanitised input reaches a database sink", 0.90),
    (re.compile(r"\b(?:os\.system|os\.popen|commands\.getoutput)\s*\("), "command_injection", "CWE-78", "critical",
     "Unsanitised input reaches an OS command sink", 0.92),
    (re.compile(r"subprocess\.(?:call|run|Popen)\s*\([^)]*shell\s*=\s*True"), "command_injection", "CWE-78", "critical",
     "Unsanitised input reaches a shell subprocess", 0.90),
    (re.compile(r"\bpickle\.loads?\s*\("), "unsafe_deserialization", "CWE-502", "high",
     "Untrusted data is deserialised with pickle", 0.90),
    (re.compile(r"\byaml\.load\s*\([^)]*Loader\s*=\s*[^S]"), "unsafe_deserialization", "CWE-502", "high",
     "Untrusted YAML is loaded without a safe loader", 0.85),
    (re.compile(r"\beval\s*\(|\bexec\s*\("), "code_injection", "CWE-94", "critical",
     "Untrusted input is executed as code", 0.90),
    (re.compile(r"\bopen\s*\("), "path_traversal", "CWE-22", "high",
     "User-controlled path is opened without validation", 0.78),
    (re.compile(r"render_template_string\s*\(|innerHTML\s*="), "xss", "CWE-79", "high",
     "Unsanitised input is rendered as HTML", 0.82),
]
def _has_interpolation(text: str) -> bool:
    """f-string / template literal with an interpolated expression.
    (A regex over f-strings breaks on inner quotes, so this is explicit.)"""
    return bool(re.search(r"""f['"]""", text) and "{" in text and "}" in text) \
        or bool(TEMPLATE_LITERAL.search(text))

FSTRING = re.compile(r"""f['"]""")
TEMPLATE_LITERAL = re.compile(r"`[^`]*\$\{[^}]+\}[^`]*`")  # JS/TS ${...}
CONCAT = re.compile(r"[\"'][^\"']*[\"']\s*\+|\+.*[\"']")

def _params(signature: str) -> list[str]:
    m = re.search(r"\(([^)]*)\)", signature or "")
    if not m:
        return []
    return [p.strip().split("=")[0].split(":")[0].strip().lstrip("*")
            for p in m.group(1).split(",") if p.strip() and p.strip() != "self"]

def _tainted_vars(body: str, params: list[str]) -> dict[str, int]:
    """var -> line where it becomes tainted (interpolated with a param)."""
    tainted: dict[str, int] = {}
    for i, line in enumerate(body.splitlines(), 1):
        m = re.match(r"\s*(?:const|let|var)?\s*([A-Za-z_]\w*)\s*=\s*(.+)", line)
        if not m:
            continue
        rhs = m.group(2)
        if any(p in rhs for p in params) and (_has_interpolation(rhs)
                                              or "+" in rhs or ".format(" in rhs):
            tainted[m.group(1)] = i
    return tainted

def _callee_sinks(context: dict) -> dict[str, list[str]]:
    """callee name -> sink lines in its body (from retrieved callee pieces)."""
    out: dict[str, list[str]] = {}
    for p in context.get("pieces", []):
        if p.get("kind") != "callee":
            continue
        sinks = []
        for line in (p.get("text") or "").splitlines():
            for rx, *_ in SINKS:
                if rx.search(line):
                    sinks.append(line.strip())
        if sinks:
            out[p["name"].split(".")[-1]] = sinks
    return out

def run_security(symbol, context: dict, file_lines: dict) -> list[FindingDraft]:
    body = symbol.body or ""
    path = symbol.path
    params = _params(symbol.signature or "")
    tainted = _tainted_vars(body, params)
    callee_sinks = _callee_sinks(context)
    findings: list[FindingDraft] = []
    lines = body.splitlines()
    start = symbol.start_line
    for i, line in enumerate(lines, 1):
        lineno = start + i - 1
        # direct sink in the changed symbol, fed by a tainted var or f-string
        for rx, cat, cwe, sev, title, conf in SINKS:
            if not rx.search(line):
                continue
            fed = any(v in line for v in tainted) or _has_interpolation(line)
            # deserialisation / code execution: passing the parameter itself
            # IS the vulnerability (no interpolation needed)
            if cat in ("unsafe_deserialization", "code_injection") \
               and any(p in line for p in params):
                fed = True
            if cat == "path_traversal" and not fed:
                continue
            if not fed:
                continue
            findings.append(FindingDraft(
                source="security", category=cat, severity=sev,
                title=title, description=(
                    f"{title}. Evidence line {lineno} in {path} passes "
                    f"unsanitised input to a dangerous sink. Tainted variable(s): "
                    f"{sorted(set(tainted) & set(re.findall(r'[A-Za-z_]\\w*', line))) or params}. "
                    "Fix by using parameterised queries / allow-listing / encoding, never string interpolation."),
                file_path=path, start_line=lineno, end_line=lineno,
                evidence=line, cwe_id=cwe, confidence=conf,
                context_provenance={"symbol": symbol.qualified_name,
                                    "taint_source": params,
                                    "sink": rx.pattern[:40]}))
        # call into a callee that contains a sink, passing tainted data
        for callee, sink_lines in callee_sinks.items():
            if re.search(rf"\b{re.escape(callee)}\s*\(", line):
                args = line[line.index("("):] if "(" in line else ""
                # only flag when a TAINTED variable (interpolated string) or an
                # interpolated literal is passed — a parameterised call such as
                # run_query("... %s", (user_id,)) is safe and must not flag.
                if any(v in args for v in tainted) or _has_interpolation(args):
                    findings.append(FindingDraft(
                        source="security", category="sql_injection" if any("execute" in s for s in sink_lines) else "command_injection",
                        severity="high",
                        cwe_id="CWE-89" if any("execute" in s for s in sink_lines) else "CWE-78",
                        title="Unsanitised input flows through a callee into a dangerous sink",
                        description=(
                            f"Call-graph context: `{symbol.qualified_name}` passes tainted input "
                            f"to callee `{callee}`, whose body executes it: "
                            f"{'; '.join(sink_lines)}. The diff alone does not show the sink — "
                            "only the caller + callee together make this exploitable. "
                            "Fix by parameterising the query in the caller and binding values."),
                        file_path=path, start_line=lineno, end_line=lineno,
                        evidence=line, confidence=0.94,
                        context_provenance={"symbol": symbol.qualified_name,
                                            "callee": callee, "callee_sink": sink_lines,
                                            "retrieval": "call-graph: caller -> callee"}))
    # LLM findings (only when a provider is configured; rules run regardless)
    ctx_text = "\n".join(f"# {p['kind']}: {p['name']}\n{p['text']}" for p in context.get("pieces", []))
    findings.extend(llm_findings("security", ctx_text, path))
    return findings
