"""Unified-diff parsing and hunk-to-symbol mapping."""
from __future__ import annotations
import re
from dataclasses import dataclass, field

@dataclass
class Hunk:
    path: str
    old_start: int = 0
    new_start: int = 0
    added_lines: list = field(default_factory=list)  # [(new_line_no, text)]
    removed_lines: list = field(default_factory=list)
    is_new_file: bool = False
    is_deleted: bool = False

_DIFF_FILE = re.compile(r"^\+\+\+ b/(.+)$")
_HUNK_HDR = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")

def parse_diff(diff_text: str) -> list[Hunk]:
    hunks: list[Hunk] = []
    cur: Hunk | None = None
    new_no = old_no = 0
    for line in (diff_text or "").splitlines():
        m = _DIFF_FILE.match(line)
        if line.startswith("diff --git"):
            cur = None
            continue
        if m:
            cur = Hunk(path=m.group(1).strip())
            hunks.append(cur)
            continue
        if line.startswith("--- ") or line.startswith("+++ "):
            continue
        hm = _HUNK_HDR.match(line)
        if hm and cur is not None:
            old_no, new_no = int(hm.group(1)), int(hm.group(2))
            continue
        if cur is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            cur.added_lines.append((new_no, line[1:]))
            new_no += 1
        elif line.startswith("-") and not line.startswith("---"):
            cur.removed_lines.append((old_no, line[1:]))
            old_no += 1
        elif line.startswith(" "):
            new_no += 1
            old_no += 1
        elif line.startswith("\\"):
            continue
    return hunks

def changed_files(diff_text: str) -> list[str]:
    return list(dict.fromkeys(h.path for h in parse_diff(diff_text)))

def map_hunks_to_symbols(hunks, symbols) -> dict:
    """Return {symbol_qualified_name: [added line numbers]} for symbols whose
    line range contains an added line. Symbols = objects with path,
    start_line, end_line, qualified_name."""
    by_path: dict[str, list] = {}
    for s in symbols:
        by_path.setdefault(s.path, []).append(s)
    mapping: dict[str, list[int]] = {}
    for h in hunks:
        for sym in by_path.get(h.path, []):
            for ln, _text in h.added_lines:
                if sym.start_line <= ln <= sym.end_line:
                    mapping.setdefault(sym.qualified_name, []).append(ln)
    return mapping

def size_band(n_files: int, n_added: int) -> str:
    if n_files > 100 or n_added > 5000:
        return "oversized"
    if n_files > 20 or n_added > 1000:
        return "large"
    if n_files > 5 or n_added > 200:
        return "medium"
    return "small"
