"""Generic provenance operation documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence
import uuid

from .hashing import add_document_hash
from .model import PROVENANCE_SCHEMA_VERSION, utc_now_iso


def build_operation_event(
    *,
    operation_kind: str,
    operation_name: str,
    title: str,
    summary: str = "",
    input_state_refs: Optional[Sequence[Dict[str, object]]] = None,
    input_knowledge_refs: Optional[Sequence[Dict[str, object]]] = None,
    input_governing_refs: Optional[Sequence[Dict[str, object]]] = None,
    output_state_refs: Optional[Sequence[Dict[str, object]]] = None,
    output_knowledge_refs: Optional[Sequence[Dict[str, object]]] = None,
    output_governing_refs: Optional[Sequence[Dict[str, object]]] = None,
    control_documents: Optional[Sequence[Dict[str, object]]] = None,
    parameters: Optional[Dict[str, object]] = None,
    execution_context: Optional[Dict[str, object]] = None,
    metrics: Optional[Dict[str, object]] = None,
    extra_metadata: Optional[Dict[str, object]] = None,
    generated_at: str = "",
    operation_id: str = "",
) -> Dict[str, object]:
    """Build a generic operation-event document."""

    return add_document_hash(
        {
            "manifest_type": "operation_event",
            "schema_version": PROVENANCE_SCHEMA_VERSION,
            "generated_at": generated_at or utc_now_iso(),
            "operation_id": operation_id or str(uuid.uuid4()),
            "operation_kind": operation_kind,
            "operation_name": operation_name,
            "title": title,
            "summary": summary,
            "inputs": {
                "states": list(input_state_refs or []),
                "knowledge": list(input_knowledge_refs or []),
                "governing": list(input_governing_refs or []),
            },
            "outputs": {
                "states": list(output_state_refs or []),
                "knowledge": list(output_knowledge_refs or []),
                "governing": list(output_governing_refs or []),
            },
            "control_documents": list(control_documents or []),
            "parameters": dict(parameters or {}),
            "execution_context": dict(execution_context or {}),
            "metrics": dict(metrics or {}),
            "extra_metadata": dict(extra_metadata or {}),
        }
    )


def write_operation_event(path: Path, payload: Dict[str, object]) -> Path:
    """Write an operation-event document to disk."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_operation_event(path: Path) -> Dict[str, object]:
    """Load an operation-event document if present."""

    if not path.exists() or not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


__all__ = [
    "build_operation_event",
    "load_operation_event",
    "write_operation_event",
]
