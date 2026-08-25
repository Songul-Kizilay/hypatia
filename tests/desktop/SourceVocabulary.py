"""Read what a function actually works with, ignoring what it says about itself.

Several panels are guarded by absence: there is no field for a payload, no
control that adjusts a confidence. Those guards are easy to write badly. A
plain text search over the source finds the words in the docstring explaining
that the field is absent, so the check fails on its own explanation — and the
obvious repair, deleting the explanation, makes the code worse to read.

Collected instead are the names the code binds and reads plus the strings it
puts on screen, which is where a field would have to appear in order to exist.
Docstrings are excluded; comments never reach the tree at all.
"""

from __future__ import annotations

import ast


def working_vocabulary(source: str, *function_names: str) -> set[str]:
    """Return every identifier and displayed literal these functions use.

    Raises AssertionError when a named function is absent, so renaming a panel
    breaks the guard rather than quietly switching it off.
    """
    wanted = set(function_names)
    vocabulary: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef) or node.name not in wanted:
            continue
        wanted.discard(node.name)
        docstring = ast.get_docstring(node, clean=False)
        for inner in ast.walk(node):
            match inner:
                case ast.Name(id=name) | ast.Attribute(attr=name):
                    vocabulary.add(name.casefold())
                case ast.arg(arg=name) | ast.keyword(arg=str() as name):
                    vocabulary.add(name.casefold())
                case ast.Constant(value=str() as text) if text != docstring:
                    vocabulary.add(text.casefold())
    if wanted:
        raise AssertionError(f"These functions were not found: {sorted(wanted)}")
    return vocabulary


def mentions(vocabulary: set[str], term: str) -> list[str]:
    """Return the collected words containing this term, for a readable failure."""
    return sorted(word for word in vocabulary if term in word)
