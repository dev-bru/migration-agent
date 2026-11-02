"""Check the plain-English guide text that teaches each Python source file."""

import ast
from pathlib import Path

import pytest

SOURCES = sorted((Path(__file__).resolve().parents[1] / "src").rglob("*.py"))


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_module_comments_and_public_docstrings(path):
    """Require an opening comment block and docstrings for public functions."""
    text = path.read_text(encoding="utf-8")
    assert all(line.startswith("#") for line in text.splitlines()[:3]), path
    tree = ast.parse(text)
    assert ast.get_docstring(tree), path
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            assert ast.get_docstring(node), f"{path}:{node.lineno}: {node.name}"
