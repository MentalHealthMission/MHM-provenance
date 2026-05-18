"""Helpers for generic non-data input references used by operation events."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from .operations import load_operation_event
from .knowledge import ensure_knowledge_snapshot_manifest
from .manifests import document_reference_from_path


def build_input_context_refs(
    *,
    issue_log_snapshot: str = "",
    extract_plan_snapshot: str = "",
    input_knowledge_manifest_paths: Sequence[str] | None = None,
    input_governing_manifest_paths: Sequence[str] | None = None,
    parent_dataset_manifests: Sequence[str] | None = None,
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """Return manifest-backed knowledge and governing input refs."""

    knowledge_refs: List[Dict[str, object]] = []
    governing_refs: List[Dict[str, object]] = []

    for locator, role, default_title in (
        (issue_log_snapshot, "issue_log_snapshot", "Issue log snapshot"),
        (extract_plan_snapshot, "extract_plan_snapshot", "Extract plan snapshot"),
    ):
        if not locator:
            continue
        manifest_path = ensure_knowledge_snapshot_manifest(
            snapshot_path=locator,
            role=role,
            title=default_title,
            parent_manifest_paths=_infer_prior_knowledge_manifests(
                parent_dataset_manifests=parent_dataset_manifests or [],
                role=role,
            ),
        )
        ref = _manifest_ref(
            manifest_path=manifest_path,
            role=role,
            relation="uses",
            default_title=default_title,
            default_node_kind="knowledge_snapshot",
        )
        if ref is not None:
            knowledge_refs.append(ref)

    for locator in input_knowledge_manifest_paths or []:
        ref = _manifest_ref(
            manifest_path=Path(locator).expanduser(),
            role="knowledge_input",
            relation="uses",
            default_title="Knowledge input",
            default_node_kind="knowledge_snapshot",
        )
        if ref is not None:
            knowledge_refs.append(ref)

    for locator in input_governing_manifest_paths or []:
        ref = _manifest_ref(
            manifest_path=Path(locator).expanduser(),
            role="governing_input",
            relation="uses",
            default_title="Governing input",
            default_node_kind="governing_snapshot",
        )
        if ref is not None:
            governing_refs.append(ref)

    return knowledge_refs, governing_refs


def _manifest_ref(
    *,
    manifest_path: Path,
    role: str,
    relation: str,
    default_title: str,
    default_node_kind: str,
) -> Dict[str, object] | None:
    if not manifest_path.exists() or not manifest_path.is_file():
        return None
    ref = document_reference_from_path(str(manifest_path), role=role, relation=relation)
    if ref is None:
        return None
    payload = ref.to_dict()
    manifest_payload = _load_json_document(manifest_path)
    dataset_kind = str(manifest_payload.get("dataset_kind", "")).strip()
    payload["node_kind"] = dataset_kind or default_node_kind
    payload["title"] = (
        str(payload.get("title", "")).strip()
        or str(manifest_payload.get("title", "")).strip()
        or default_title
    )
    payload["dataset_id"] = (
        str(payload.get("dataset_id", "")).strip()
        or str(manifest_payload.get("dataset_id", "")).strip()
    )
    return payload


def _load_json_document(path: Path) -> Dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _infer_prior_knowledge_manifests(
    *,
    parent_dataset_manifests: Sequence[str],
    role: str,
) -> List[str]:
    matches: List[str] = []
    seen: set[str] = set()
    for locator in parent_dataset_manifests:
        if not locator:
            continue
        manifest_path = Path(locator).expanduser()
        if not manifest_path.exists() or not manifest_path.is_file():
            continue
        operation_payload = load_operation_event(manifest_path.parent / "operation_event.json")
        inputs = dict(operation_payload.get("inputs", {}))
        for ref in inputs.get("knowledge", []):
            if not isinstance(ref, dict):
                continue
            ref_locator = str(ref.get("locator", "")).strip()
            if not ref_locator or ref_locator in seen:
                continue
            ref_manifest = _load_json_document(Path(ref_locator).expanduser())
            extra = dict(ref_manifest.get("extra_metadata", {}))
            if str(extra.get("knowledge_role", "")).strip() != role:
                continue
            seen.add(ref_locator)
            matches.append(ref_locator)
    return matches


__all__ = ["build_input_context_refs"]
