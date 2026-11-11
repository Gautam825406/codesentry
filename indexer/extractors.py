"""Symbol extraction from tree-sitter trees (primary) or the stdlib fallback.

Every symbol is a meaningful code unit: qualified name, kind, signature,
docstring, imports, decorators, call expressions and exact line range.
No fixed-size text chunking is used as the primary strategy.
"""
from __future__ import annotations
import hashlib
from indexer.parsers import (SymbolInfo, language_for_path, ts_parse,
                             _py_ast_symbols, _js_regex_symbols, PARSER_BACKEND)

def _node_text(node, code: bytes) -> str:
    return code[node.start_byte:node.end_byte].decode("utf-8", "replace")

def _child_by_type(node, *types):
    for c in node.children:
        if c.type in types:
            return c
    return None

def _extract_py_tree(root, code: bytes) -> list[SymbolInfo]:
    out: list[SymbolInfo] = []
    lines = code.decode("utf-8", "replace").splitlines()

    def calls_in(node):
        calls = []
        stack = [node]
        while stack:
            n = stack.pop()
            if n.type == "call":
                fn = _child_by_type(n, "identifier", "attribute")
                if fn is not None:
                    calls.append((_node_text(fn, code), fn.start_point[0] + 1))
            stack.extend(n.children)
        return calls

    def visit(node, prefix=""):
        for child in node.children:
            if child.type == "function_definition":
                name_node = _child_by_type(child, "identifier")
                name = _node_text(name_node, code) if name_node else "?"
                qn = f"{prefix}{name}" if prefix else name
                params = _child_by_type(child, "parameters")
                sig = f"def {name}{_node_text(params, code) if params else '(...)'}"
                doc = ""
                block = _child_by_type(child, "block")
                if block and block.children:
                    first = block.children[0]
                    if first.type == "expression_statement":
                        s = _child_by_type(first, "string")
                        if s is not None:
                            doc = _node_text(s, code).strip("'\"")
                decorators = [_node_text(d, code) for d in child.children
                              if d.type == "decorator"]
                out.append(SymbolInfo(
                    qualified_name=qn, kind="method" if prefix else "function",
                    language="python", start_line=child.start_point[0] + 1,
                    end_line=child.end_point[0] + 1, signature=sig, docstring=doc,
                    body=_node_text(child, code), calls=calls_in(child),
                    decorators=decorators))
            elif child.type == "class_definition":
                name_node = _child_by_type(child, "identifier")
                name = _node_text(name_node, code) if name_node else "?"
                qn = f"{prefix}{name}" if prefix else name
                out.append(SymbolInfo(
                    qualified_name=qn, kind="class", language="python",
                    start_line=child.start_point[0] + 1,
                    end_line=child.end_point[0] + 1, body=_node_text(child, code)))
                visit(child, prefix=qn + ".")
            else:
                visit(child, prefix=prefix)
    visit(root)
    # imports (module level)
    imports = []
    for child in root.children:
        if child.type in ("import_statement", "import_from_statement"):
            imports.append(_node_text(child, code))
    for s in out:
        s.imports = imports
    return out

def _extract_js_tree(root, code: bytes, language: str) -> list[SymbolInfo]:
    out: list[SymbolInfo] = []
    def calls_in(node):
        calls = []
        stack = [node]
        while stack:
            n = stack.pop()
            if n.type == "call_expression":
                fn = n.child_by_field_name("function")
                if fn is not None:
                    calls.append((_node_text(fn, code), fn.start_point[0] + 1))
            stack.extend(n.children)
        return calls
    def visit(node, prefix=""):
        for child in node.children:
            if child.type in ("function_declaration", "function", "arrow_function",
                              "method_definition", "generator_function_declaration"):
                name_node = child.child_by_field_name("name")
                name = _node_text(name_node, code) if name_node else None
                if name is None:
                    # const foo = () => {}
                    parent = node
                    name = "anonymous"
                qn = f"{prefix}{name}" if prefix else name
                out.append(SymbolInfo(
                    qualified_name=qn, kind="method" if child.type == "method_definition" else "function",
                    language=language, start_line=child.start_point[0] + 1,
                    end_line=child.end_point[0] + 1,
                    signature=_node_text(child, code).split("{")[0].strip()[:200],
                    body=_node_text(child, code), calls=calls_in(child)))
            elif child.type in ("class_declaration", "class"):
                name_node = child.child_by_field_name("name")
                name = _node_text(name_node, code) if name_node else "?"
                qn = f"{prefix}{name}" if prefix else name
                out.append(SymbolInfo(qualified_name=qn, kind="class", language=language,
                    start_line=child.start_point[0] + 1, end_line=child.end_point[0] + 1,
                    body=_node_text(child, code)))
                visit(child, prefix=qn + ".")
            elif child.type == "variable_declarator":
                # const foo = function(){} / () => {}
                name_node = child.child_by_field_name("name")
                val = child.child_by_field_name("value")
                if name_node is not None and val is not None and val.type in ("arrow_function", "function_expression", "function"):
                    name = _node_text(name_node, code)
                    qn = f"{prefix}{name}" if prefix else name
                    out.append(SymbolInfo(qualified_name=qn, kind="function", language=language,
                        start_line=child.start_point[0] + 1, end_line=child.end_point[0] + 1,
                        signature=_node_text(child, code).split("=>")[0].strip()[:200],
                        body=_node_text(child, code), calls=calls_in(val)))
                else:
                    visit(child, prefix=prefix)
            else:
                visit(child, prefix=prefix)
    visit(root)
    imports = []
    for child in root.children:
        if child.type == "import_statement":
            imports.append(_node_text(child, code))
    for s in out:
        s.imports = imports
    return out

def extract_symbols(path: str, source: str) -> list[SymbolInfo]:
    """Parse one file and return its symbols. Raises nothing on bad code:
    an unparseable file yields an empty list (and is recorded as skipped)."""
    lang = language_for_path(path)
    if lang is None:
        return []
    code = source.encode("utf-8", "replace")
    tree = ts_parse(lang, code)
    if tree is not None:
        try:
            if lang == "python":
                syms = _extract_py_tree(tree.root_node, code)
            else:
                syms = _extract_js_tree(tree.root_node, code, lang)
            for s in syms:
                s.path = path
            return syms
        except Exception:
            pass  # fall through to the fallback parser
    if lang == "python":
        syms = _py_ast_symbols(source)
    else:
        syms = _js_regex_symbols(source, lang)
    for s in syms:
        s.path = path
    return syms

def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
