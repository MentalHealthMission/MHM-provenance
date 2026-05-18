"""Helpers for manifest-backed governing-state nodes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from .manifests import build_artifact_record, build_dataset_snapshot_from_inventory, document_reference_from_path, write_dataset_manifest_bundle
from .model import LogicalAddress
from .operations import build_operation_event, write_operation_event
from .source import artifacts_and_coverage


def create_governing_snapshot_manifest(
    *,
    event_path: str | Path,
    event_payload: dict[str, object],
    parent_manifest_paths: Sequence[str] | None = None,
) -> Path:
    path = Path(event_path).expanduser()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Governing event not found: {path}")

    event_kind = str(event_payload.get("event_kind", "")).strip() or "other"
    availability = dict(event_payload.get("availability_update", {}))
    target_ref = dict(event_payload.get("target_dataset_manifest", {}))
    source_ref = dict(event_payload.get("source_state_manifest", {}))

    manifest_root = path.parent / "governing-state"
    dataset_id = f"governing-{_slugify(event_kind) or 'update'}"
    title = f"{event_kind.replace('_', ' ').title()} governing state"
    address = LogicalAddress(
        surface="governance",
        domain="compliance",
        stage=event_kind,
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
        for ref in [document_reference_from_path(locator, role="prior_governing_manifest", relation="updates")]
        if ref is not None
    ]
    snapshot = build_dataset_snapshot_from_inventory(
        data_locator=str(path.parent),
        dataset_kind="governing_snapshot",
        logical_root={
            "surface": "governance",
            "domain": "compliance",
            "stage": event_kind,
            "dataset_id": dataset_id,
        },
        layout="flat_files_v1",
        fingerprint_mode="metadata",
        artifacts=artifacts,
        coverage_summary=coverage_summary,
        dataset_id=dataset_id,
        title=title,
        notes="Manifest-backed governing state derived from a source availability/compliance event.",
        parents=parent_refs,
        extra_metadata={
            "governing_event_path": str(path),
            "event_kind": event_kind,
            "source_availability_status": str(availability.get("source_availability_status", "")),
            "reproducibility_status": str(availability.get("reproducibility_status", "")),
            "reifiability_status": str(availability.get("reifiability_status", "")),
            "downstream_action_status": str(availability.get("downstream_action_status", "")),
        },
    )
    write_dataset_manifest_bundle(
        manifest_root=manifest_root,
        snapshot=snapshot,
        history_event={
            "event_type": "snapshot_governing_state",
            "generated_at": snapshot["generated_at"],
            "dataset_id": snapshot["dataset_id"],
            "dataset_kind": snapshot["dataset_kind"],
            "data_root": snapshot["data_root"],
            "event_kind": event_kind,
            "governing_event_path": str(path),
        },
    )

    source_locator = str(source_ref.get("locator", "")).strip()
    input_state_refs = []
    if source_locator:
        source_doc = document_reference_from_path(source_locator, role="source_state_manifest", relation="affects")
        if source_doc is not None:
            input_state_refs.append(source_doc.to_dict())
    input_governing_refs = [
        ref.to_dict()
        for locator in (parent_manifest_paths or [])
        if locator
        for ref in [document_reference_from_path(locator, role="prior_governing_manifest", relation="updates")]
        if ref is not None
    ]

    control_documents = [
        {
            "locator": str(path),
            "role": "source_availability_event",
            "relation": "documents",
            "title": path.name,
        }
    ]
    target_locator = str(target_ref.get("locator", "")).strip()
    if target_locator:
        target_doc = document_reference_from_path(target_locator, role="target_dataset_manifest", relation="governs")
        if target_doc is not None:
            control_documents.append(target_doc.to_dict())

    output_manifest_path = manifest_root / "dataset_manifest.json"
    write_operation_event(
        manifest_root / "operation_event.json",
        build_operation_event(
            operation_kind="govern",
            operation_name=event_kind,
            title=f"{'Update' if input_governing_refs else 'Record'} {event_kind.replace('_', ' ')} update",
            summary="Recorded a governing-state update that affects downstream validity or realization.",
            input_state_refs=input_state_refs,
            input_governing_refs=input_governing_refs,
            output_governing_refs=[
                {
                    "locator": str(output_manifest_path),
                    "title": title,
                    "dataset_id": dataset_id,
                    "role": "output_governing_manifest",
                    "relation": "produces",
                    "node_kind": "governing_snapshot",
                }
            ],
            control_documents=control_documents,
            parameters={
                "source_availability_status": str(availability.get("source_availability_status", "")),
                "reproducibility_status": str(availability.get("reproducibility_status", "")),
                "reifiability_status": str(availability.get("reifiability_status", "")),
                "downstream_action_status": str(availability.get("downstream_action_status", "")),
            },
        ),
    )
    return output_manifest_path


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


__all__ = ["create_governing_snapshot_manifest"]
