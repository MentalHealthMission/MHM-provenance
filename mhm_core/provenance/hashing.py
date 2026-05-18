"""Canonical hashing helpers for provenance manifests."""

from __future__ import annotations

from datetime import date, datetime, time
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


def prune_empty(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        pruned = {str(key): prune_empty(item) for key, item in value.items()}
        return {
            key: item
            for key, item in pruned.items()
            if item not in ("", None, [], {})
        }
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        pruned_items = [prune_empty(item) for item in value]
        return [item for item in pruned_items if item not in ("", None, [], {})]
    return value


def canonical_json_bytes(value: Any) -> bytes:
    pruned = prune_empty(value)
    payload = json.dumps(
        pruned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return payload.encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def add_document_hash(document: Mapping[str, Any], *, field_name: str = "document_hash") -> dict[str, Any]:
    payload = dict(document)
    payload.pop(field_name, None)
    payload[field_name] = sha256_json(payload)
    return payload


def aggregate_hash(values: Iterable[str]) -> str:
    joined = "\n".join(sorted(value for value in values if value))
    return sha256_bytes(joined.encode("utf-8"))
