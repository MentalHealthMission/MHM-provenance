"""Helpers for manifest-backed knowledge snapshot nodes."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Sequence

from .manifests import (
    build_artifact_record,
    build_dataset_snapshot_from_inventory,
    document_reference_from_path,
    write_dataset_manifest_bundle,
)
from .model import LogicalAddress
from .operations import build_operation_event, write_operation_event
from .path_utils import normalize_user_path
from .source import artifacts_and_coverage


def ensure_knowledge_snapshot_manifest(
    *,
    snapshot_path: str | Path,
    role: str,
    title: str = "",
    parent_manifest_paths: Sequence[str] | None = None,
) -> Path:
    path = normalize_user_path(snapshot_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Knowledge snapshot not found: {path}")

    manifest_root = _knowledge_manifest_root(path, role=role)
    dataset_id = f"{_slugify(role) or 'knowledge'}-{_slugify(path.stem) or 'snapshot'}"
    address = LogicalAddress(
        surface="knowledge",
        domain="study-metadata",
        stage=role,
        dataset_id=dataset_id,
        artifact=path.name,
    )
    artifact = build_artifact_record(
        file_path=path,
        relative=Path(path.name),
        address=address,
        fingerprint_mode="metadata",
    )
    artifacts, coverage_summary = artifacts_and_coverage([artifact])
    parent_refs = [
        ref.to_dict()
        for locator in (parent_manifest_paths or [])
        if locator
        for ref in [document_reference_from_path(locator, role="prior_knowledge_manifest", relation="updates")]
        if ref is not None
    ]
    snapshot = build_dataset_snapshot_from_inventory(
        data_locator=str(path.parent),
        dataset_kind="knowledge_snapshot",
        logical_root={
            "surface": "knowledge",
            "domain": "study-metadata",
            "stage": role,
            "dataset_id": dataset_id,
        },
        layout="flat_files_v1",
        fingerprint_mode="metadata",
        artifacts=artifacts,
        coverage_summary=coverage_summary,
        dataset_id=dataset_id,
        title=title or _default_knowledge_title(role),
        notes=f"Manifest-backed knowledge snapshot for {path.name}.",
        parents=parent_refs,
        extra_metadata={
            "knowledge_role": role,
            "snapshot_file": str(path),
        },
    )
    write_dataset_manifest_bundle(
        manifest_root=manifest_root,
        snapshot=snapshot,
        history_event={
            "event_type": "snapshot_knowledge_state",
            "generated_at": snapshot["generated_at"],
            "dataset_id": snapshot["dataset_id"],
            "dataset_kind": snapshot["dataset_kind"],
            "data_root": snapshot["data_root"],
            "knowledge_role": role,
            "snapshot_file": str(path),
        },
    )
    output_manifest_path = manifest_root / "dataset_manifest.json"
    output_ref = {
        "locator": str(output_manifest_path),
        "title": snapshot["title"],
        "dataset_id": snapshot["dataset_id"],
        "role": "output_knowledge_manifest",
        "relation": "produces",
        "node_kind": "knowledge_snapshot",
    }
    input_knowledge_refs = [
        ref.to_dict()
        for locator in (parent_manifest_paths or [])
        if locator
        for ref in [document_reference_from_path(locator, role="prior_knowledge_manifest", relation="updates")]
        if ref is not None
    ]
    write_operation_event(
        manifest_root / "operation_event.json",
        build_operation_event(
            operation_kind="update" if input_knowledge_refs else "observe",
            operation_name=role,
            title=f"{'Update' if input_knowledge_refs else 'Record'} {snapshot['title'].lower()}",
            summary=(
                f"{'Updated' if input_knowledge_refs else 'Recorded'} the {snapshot['title'].lower()} "
                "as a manifest-backed knowledge state."
            ),
            input_knowledge_refs=input_knowledge_refs,
            output_knowledge_refs=[output_ref],
            control_documents=[
                {
                    "locator": str(path),
                    "role": role,
                    "relation": "observed_from",
                    "title": path.name,
                }
            ],
            parameters={"knowledge_role": role},
        ),
    )
    return manifest_root / "dataset_manifest.json"


def _knowledge_manifest_root(path: Path, *, role: str) -> Path:
    return path.parent / "_knowledge_manifests" / f"{_slugify(role)}-{_slugify(path.stem)}"


def _default_knowledge_title(role: str) -> str:
    return {
        "issue_log_snapshot": "Issue log snapshot",
        "extract_plan_snapshot": "Extract plan snapshot",
    }.get(role, role.replace("_", " ").title() or "Knowledge snapshot")


def _slugify(value: str) -> str:
    text = value.strip().lower()
    slug = []
    last_dash = False
    for char in text:
        if char.isalnum():
            slug.append(char)
            last_dash = False
            continue
        if last_dash:
            continue
        slug.append("-")
        last_dash = True
    return "".join(slug).strip("-")


__all__ = ["ensure_knowledge_snapshot_manifest"]
