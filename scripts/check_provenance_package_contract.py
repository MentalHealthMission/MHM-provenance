#!/usr/bin/env python3
"""Check the rehearsed MHM provenance package import contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "mhm_core" / "provenance"
FORBIDDEN_PREFIXES = ("connect_summary", "mhm_core.pipeline")
LAZY_ONLY_PREFIXES = ("boto3", "botocore")
LAZY_MODULES = {PACKAGE_ROOT / "source.py"}


def main() -> int:
    violations: list[str] = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            violations.append(f"{path}:{exc.lineno}: syntax error: {exc.msg}")
            continue
        for module_name, line_no in _imports(tree):
            if _matches_prefix(module_name, FORBIDDEN_PREFIXES):
                violations.append(f"{path}:{line_no}: forbidden import for mhm-provenance: {module_name}")
            if _matches_prefix(module_name, LAZY_ONLY_PREFIXES) and path not in LAZY_MODULES:
                violations.append(f"{path}:{line_no}: eager optional import for mhm-provenance: {module_name}")
    payload = {
        "contract": "mhm-provenance:kernel",
        "status": "ok" if not violations else "failed",
        "violations": violations,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not violations else 1


def _imports(tree: ast.AST) -> list[tuple[str, int]]:
    imports: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append((node.module or "", node.lineno))
    return imports


def _matches_prefix(module_name: str, prefixes: tuple[str, ...]) -> bool:
    return any(module_name == prefix or module_name.startswith(prefix + ".") for prefix in prefixes)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
