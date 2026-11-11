"""Call-graph construction and retrieval.

Resolution (v1, static only — never invented):
  1. same-file function/method by bare name or Class.method
  2. import-resolved: `from x import foo` / `import x` then `x.foo`
Unresolved calls are recorded with resolved=False and tracked, not guessed.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Edge:
    caller: str
    callee: str
    file_path: str
    line: int
    resolved: bool
    callee_symbol: str | None = None

def _import_map(imports: list[str]) -> dict[str, str]:
    """Map a local name -> dotted source path, from import statements."""
    import re
    m: dict[str, str] = {}
    for imp in imports:
        s = imp.strip().rstrip(";")
        fm = re.match(r"from\s+([\w\.]+)\s+import\s+(.+)", s)
        if fm:
            mod, names = fm.group(1), fm.group(2)
            for n in names.split(","):
                n = n.strip().split(" as ")[0].strip()
                if n and n != "*":
                    m[n] = f"{mod}.{n}"
            continue
        im = re.match(r"import\s+([\w\.]+)(?:\s+as\s+(\w+))?", s)
        if im:
            m[im.group(2) or im.group(1).split(".")[0]] = im.group(1)
    return m

def build_call_graph(symbols) -> list[Edge]:
    """symbols: iterable of SymbolInfo (with .calls, .imports, .qualified_name, .path)."""
    by_name: dict[str, list] = {}
    for s in symbols:
        by_name.setdefault(s.qualified_name.split(".")[-1], []).append(s)
        by_name.setdefault(s.qualified_name, []).append(s)
    edges: list[Edge] = []
    for s in symbols:
        imap = _import_map(getattr(s, "imports", []) or [])
        for callee_name, line in getattr(s, "calls", []) or []:
            short = callee_name.split(".")[-1]
            resolved = None
            # 1. same file, same qualified prefix
            candidates = by_name.get(callee_name) or by_name.get(short) or []
            same_file = [c for c in candidates
                         if getattr(c, "path", None) == getattr(s, "path", None)]
            if same_file:
                resolved = same_file[0]
            elif callee_name in imap:
                # 2. import-resolved: find a symbol whose qualified name ends with the import target
                target = imap[callee_name]
                for c in symbols:
                    if c.qualified_name.endswith(target.split(".")[-1]) and \
                       target.split(".")[-1] == c.qualified_name.split(".")[-1]:
                        resolved = c
                        break
            elif len(candidates) == 1:
                resolved = candidates[0]
            edges.append(Edge(
                caller=s.qualified_name, callee=callee_name,
                file_path=getattr(s, "path", ""), line=line,
                resolved=resolved is not None,
                callee_symbol=resolved.qualified_name if resolved else None))
    return edges
