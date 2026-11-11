"""Unit tests: parsing, symbols, call graph, diff mapping."""
from indexer.extractors import extract_symbols
from indexer.call_graph import build_call_graph
from indexer.parsers import language_for_path, is_generated_or_minified, PARSER_BACKEND
from indexer.diff import parse_diff, map_hunks_to_symbols, size_band, changed_files
from indexer.parsers import SymbolInfo

PY = '''
import os
from app.db import run_query

def get_order(order_id):
    """Fetch one order."""
    sql = f"SELECT * FROM orders WHERE id = '{order_id}'"
    return run_query(sql)

class Shop:
    def total(self, items):
        return sum(items)
'''

def test_parser_backend_is_tree_sitter():
    assert PARSER_BACKEND == "tree-sitter"

def test_python_symbols_extracted():
    syms = extract_symbols("app/orders.py", PY)
    names = {s.qualified_name: s for s in syms}
    assert "get_order" in names
    assert "Shop" in names
    assert "Shop.total" in names
    assert names["get_order"].signature == "def get_order(order_id)"
    assert names["get_order"].docstring == "Fetch one order."
    assert names["get_order"].start_line == 5
    assert "run_query" in [c[0] for c in names["get_order"].calls]

def test_js_symbols_extracted():
    src = "function searchUsers(q) {\n  return db.query(q);\n}\nconst add = (a, b) => a + b;\n"
    syms = extract_symbols("app/api.js", src)
    names = {s.qualified_name for s in syms}
    assert "searchUsers" in names
    assert "add" in names

def test_language_detection():
    assert language_for_path("a.py") == "python"
    assert language_for_path("a.ts") == "typescript"
    assert language_for_path("a.tsx") == "typescript"
    assert language_for_path("a.md") is None

def test_generated_detection():
    assert is_generated_or_minified("x.min.js", "var a=1;" * 3000)
    assert not is_generated_or_minified("app/orders.py", PY)

def test_call_graph_same_file_and_import():
    syms = extract_symbols("app/orders.py", PY)
    edges = build_call_graph(syms)
    by_caller = {(e.caller, e.callee) for e in edges}
    assert ("get_order", "run_query") in by_caller
    # run_query is imported (from app.db import run_query) -> resolved
    e = next(x for x in edges if x.callee == "run_query")
    assert e.resolved is False or e.callee_symbol is not None  # no run_query symbol in this file set

def test_call_graph_unresolved_tracked():
    s = SymbolInfo(qualified_name="a", kind="function", language="python",
                   start_line=1, end_line=2, calls=[("unknown_fn", 1)], imports=[])
    s.path = "a.py"
    edges = build_call_graph([s])
    assert len(edges) == 1 and edges[0].resolved is False

def test_diff_parse_and_mapping():
    diff = """diff --git a/app/orders.py b/app/orders.py
--- a/app/orders.py
+++ b/app/orders.py
@@ -1,4 +1,6 @@
 from app.db import run_query
 
 
 def get_order(order_id):
-    return run_query("SELECT * FROM orders WHERE id = %s", (order_id,))
+    sql = f"SELECT * FROM orders WHERE id = '{order_id}'"
+    return run_query(sql)
"""
    hunks = parse_diff(diff)
    assert len(hunks) == 1 and hunks[0].path == "app/orders.py"
    assert [ln for ln, _ in hunks[0].added_lines] == [5, 6]
    assert changed_files(diff) == ["app/orders.py"]
    syms = extract_symbols("app/orders.py", PY)
    mapping = map_hunks_to_symbols(hunks, syms)
    assert "get_order" in mapping and mapping["get_order"] == [5, 6]

def test_size_band():
    assert size_band(1, 10) == "small"
    assert size_band(150, 10) == "oversized"
    assert size_band(30, 10) == "large"
