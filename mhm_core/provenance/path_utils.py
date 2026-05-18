"""Generic path helpers for provenance manifests."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath


def canonical_relative_locator(path: str | Path) -> str:
    """Render a relative dataset path in a cross-platform canonical form."""

    if isinstance(path, Path):
        parts = path.parts
    else:
        parts = tuple(part for part in str(path).replace("\\", "/").split("/") if part)
    return PurePosixPath(*parts).as_posix() if parts else ""


def relative_locator_to_path(path: str | Path) -> Path:
    """Convert a canonical relative locator back into a local relative Path."""

    canonical = canonical_relative_locator(path)
    if not canonical:
        return Path()
    return Path(*PurePosixPath(canonical).parts)


def normalize_user_path(path: str | Path) -> Path:
    """Return an absolute user path without requiring filesystem resolution."""

    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return candidate.absolute()


def safe_resolve_path(path: str | Path) -> Path:
    """Resolve a path when possible, falling back to lexical absolutization."""

    candidate = Path(path).expanduser()
    try:
        return candidate.resolve()
    except OSError:
        if candidate.is_absolute():
            return candidate
        return candidate.absolute()


def comparable_path_string(path: str | Path) -> str:
    """Return a host-normalized path string suitable for equality checks."""

    try:
        candidate = safe_resolve_path(path)
    except Exception:
        candidate = Path(path).expanduser()
    return os.path.normpath(str(candidate))


def paths_equivalent(left: str | Path, right: str | Path) -> bool:
    return comparable_path_string(left) == comparable_path_string(right)


__all__ = [
    "canonical_relative_locator",
    "comparable_path_string",
    "normalize_user_path",
    "paths_equivalent",
    "relative_locator_to_path",
    "safe_resolve_path",
]
