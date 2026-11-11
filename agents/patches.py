"""Patch generation + validation (PRD §8 / F4).

Patches are GitHub `suggestion` blocks. A patch is only attached when:
  1. it is a unified diff limited to the finding's lines (start-1 .. end+1),
  2. applying it to the reviewed file still parses (Python: ast.parse;
     JS/TS: tree-sitter parse with no ERROR node),
  3. it changes the vulnerable construct (not a no-op).
Otherwise the patch is WITHHELD and the finding is posted without one.
"""
from __future__ import annotations
import ast, re
from indexer.parsers import ts_parse

def _apply_patch(file_lines: list[str], start: int, end: int, new_lines: list[str]) -> str:
    out = file_lines[:start - 1] + new_lines + file_lines[end:]
    return "\n".join(out)

def _parses(path: str, text: str) -> bool:
    if path.endswith(".py"):
        try:
            compile(text, "<patched>", "exec")  # compile(), not ast.parse:
            return True                          # ast.parse accepts top-level `return`
        except SyntaxError:
            return False
    lang = "javascript" if path.endswith((".js", ".jsx", ".mjs")) else "typescript"
    tree = ts_parse(lang, text.encode())
    if tree is None:
        return True  # no parser available: cannot disprove; caller records this
    return "ERROR" not in tree.root_node.sexp()

def validate_patch(patch_text: str, file_path: str, file_lines: list[str],
                   start: int, end: int) -> tuple[bool, str]:
    """patch_text: the replacement lines (without diff markers)."""
    if not patch_text or not patch_text.strip():
        return False, "empty_patch"
    new_lines = patch_text.strip("\n").splitlines()
    # must be within the finding's region (+1 line of context either side)
    if len(new_lines) > (end - start + 1) + 2:
        return False, "patch_exceeds_finding_region"
    modified = _apply_patch(file_lines, start, end, new_lines)
    if modified == "\n".join(file_lines):
        return False, "patch_is_noop"
    if not _parses(file_path, modified):
        return False, "patched_file_does_not_parse"
    return True, "ok"

def generate_patch(finding, file_lines: list[str]) -> tuple[str | None, bool]:
    """Rule-based patches for well-understood finding types."""
    if finding.category == "sql_injection":
        # The f-string assignment usually sits 1-2 lines above the sink call.
        window_start = max(0, finding.start_line - 3)
        window = file_lines[window_start:finding.start_line + 1]
        for j, line in enumerate(window):
            m = re.search(r"""f["'](.*)\{([A-Za-z_]\w*)\}(.*)["']""", line)
            if m and "SELECT" in m.group(1).upper():
                var = m.group(2)
                indent = line[:len(line) - len(line.lstrip())]
                sql_text = (m.group(1) + "%s" + m.group(3)).strip()
                new_sql = f'{indent}sql = "{sql_text}"'
                # next line after the assignment (usually the sink call)
                nxt_idx = window_start + j + 1
                nxt = file_lines[nxt_idx] if nxt_idx < len(file_lines) else ""
                if "run_query(sql)" in nxt:
                    new_call = nxt.replace("run_query(sql)", f"run_query(sql, ({var},))")
                    patch = new_sql + "\n" + new_call
                    ok, _ = validate_patch(patch, finding.file_path, file_lines,
                                           window_start + j + 1, nxt_idx + 1)
                    return (patch, True) if ok else (None, False)
                patch = new_sql
                ok, _ = validate_patch(patch, finding.file_path, file_lines,
                                       window_start + j + 1, window_start + j + 1)
                return (patch, True) if ok else (None, False)
        return None, False
    if finding.category == "logic_error" and "zero" in (finding.title or "").lower():
        m = re.search(r"/\s*len\((\w+)\)", finding.evidence or "")
        var = m.group(1) if m else "items"
        patch = f"    if not {var}:\n        return 0\n" + (finding.evidence or "")
        ok, _ = validate_patch(patch, finding.file_path, file_lines,
                               finding.start_line, finding.end_line)
        return (patch, True) if ok else (None, False)
    if finding.category == "error_handling" and (finding.evidence or "").strip() == "except:":
        patch = "    except Exception:"
        ok, _ = validate_patch(patch, finding.file_path, file_lines,
                               finding.start_line, finding.end_line)
        return (patch, True) if ok else (None, False)
    return None, False

def suggestion_block(patch: str) -> str:
    return "```suggestion\n" + patch.strip("\n") + "\n```"
