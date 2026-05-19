"""Merkle-style provenance manifests over filesystem-backed datasets."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence
import uuid

from .path_utils import canonical_relative_locator, normalize_user_path, safe_resolve_path

from .hashing import add_document_hash, aggregate_hash, canonical_json_bytes, sha256_file, sha256_json
from .model import (
    DocumentReference,
    LogicalAddress,
    PhysicalBinding,
    PROVENANCE_SCHEMA_VERSION,
    file_mtime_iso,
    utc_now_iso,
)
from .passive_data_layout import (
    GROUP_ENTITY_STREAM_LAYOUTS,
    coverage_with_neutral_aliases,
    passive_logical_coordinates,
    passive_logical_labels,
)


def git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def build_dataset_snapshot(
    *,
    data_root: Path,
    dataset_kind: str,
    dataset_id: Optional[str] = None,
    title: str = "",
    source_dataset_manifest: str = "",
    issue_log_snapshot: str = "",
    extract_plan_snapshot: str = "",
    as_of: str = "",
    notes: str = "",
    extra_metadata: Optional[Dict[str, object]] = None,
    surface: str = "",
    domain: str = "",
    stage: str = "",
    layout: str = "",
    slice_name: str = "",
    fingerprint_mode: str = "metadata",
    source_state_manifest: str = "",
    source_state_as_of: str = "",
    knowledge_state_as_of: str = "",
    built_at: str = "",
    source_availability_status: str = "available",
    reproducibility_status: str = "fully_rebuildable",
    reifiability_status: str = "fully_reifiable",
    downstream_action_status: str = "none",
    logical_root_overrides: Optional[Dict[str, object]] = None,
    progress_reporter: Callable[[Dict[str, object]], None] | None = None,
    progress_stage_prefix: str = "pre_run_inventory",
) -> Dict[str, object]:
    data_root = normalize_user_path(data_root)
    dataset_id_value = dataset_id or str(uuid.uuid4())
    logical_root = infer_logical_root(
        data_root=data_root,
        dataset_id=dataset_id_value,
        dataset_kind=dataset_kind,
        surface=surface,
        domain=domain,
        stage=stage,
        slice_name=slice_name,
    )
    if logical_root_overrides:
        logical_root.update(dict(logical_root_overrides))
    layout_name = layout or infer_layout(data_root, logical_root)
    generated_at = utc_now_iso()
    parent_documents = build_parent_document_refs([source_dataset_manifest])
    source_state_documents = build_source_state_document_refs([source_state_manifest])
    resolved_source_state_as_of = source_state_as_of or infer_source_state_as_of(source_state_manifest)
    control_documents = build_control_document_refs(
        issue_log_snapshot=issue_log_snapshot,
        extract_plan_snapshot=extract_plan_snapshot,
    )
    artifacts, coverage_summary = snapshot_artifacts(
        data_root=data_root,
        logical_root=logical_root,
        layout=layout_name,
        fingerprint_mode=fingerprint_mode,
        progress_reporter=progress_reporter,
        progress_stage_prefix=progress_stage_prefix,
    )

    snapshot: Dict[str, object] = {
        "dataset_id": dataset_id_value,
        "dataset_kind": dataset_kind,
        "title": title,
        "generated_at": generated_at,
        "git_sha": git_sha(),
        "data_root": str(data_root),
        "as_of": as_of,
        "state_coordinates": {
            "built_at": built_at or generated_at,
            "dataset_state_as_of": as_of,
            "source_state_as_of": resolved_source_state_as_of,
            "knowledge_state_as_of": knowledge_state_as_of,
        },
        "availability": {
            "source_availability_status": source_availability_status,
            "reproducibility_status": reproducibility_status,
            "reifiability_status": reifiability_status,
            "downstream_action_status": downstream_action_status,
        },
        "notes": notes,
        "logical_root": logical_root,
        "layout": layout_name,
        "fingerprint_mode": fingerprint_mode,
        "data_root_binding": infer_binding(str(data_root)),
        "parents": parent_documents,
        "source_state_documents": source_state_documents,
        "control_documents": control_documents,
        "artifacts": artifacts,
        "coverage_summary": coverage_summary,
        "source_dataset_manifest": source_dataset_manifest,
        "source_state_manifest": source_state_manifest,
        "issue_log_snapshot": issue_log_snapshot,
        "extract_plan_snapshot": extract_plan_snapshot,
    }
    if extra_metadata:
        snapshot["extra_metadata"] = extra_metadata
    return snapshot


def build_dataset_snapshot_from_inventory(
    *,
    data_locator: str,
    dataset_kind: str,
    logical_root: Dict[str, object],
    layout: str,
    fingerprint_mode: str,
    artifacts: Sequence[Dict[str, object]],
    coverage_summary: Dict[str, object],
    dataset_id: Optional[str] = None,
    title: str = "",
    as_of: str = "",
    notes: str = "",
    extra_metadata: Optional[Dict[str, object]] = None,
    parents: Optional[Sequence[Dict[str, object]]] = None,
    control_documents: Optional[Sequence[Dict[str, object]]] = None,
    git_sha_value: Optional[str] = None,
    source_state_documents: Optional[Sequence[Dict[str, object]]] = None,
    source_state_as_of: str = "",
    knowledge_state_as_of: str = "",
    built_at: str = "",
    source_availability_status: str = "available",
    reproducibility_status: str = "fully_rebuildable",
    reifiability_status: str = "fully_reifiable",
    downstream_action_status: str = "none",
) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "dataset_id": dataset_id or str(uuid.uuid4()),
        "dataset_kind": dataset_kind,
        "title": title,
        "generated_at": utc_now_iso(),
        "git_sha": git_sha_value if git_sha_value is not None else git_sha(),
        "data_root": data_locator,
        "data_root_binding": infer_binding(data_locator),
        "as_of": as_of,
        "state_coordinates": {
            "built_at": built_at or utc_now_iso(),
            "dataset_state_as_of": as_of,
            "source_state_as_of": source_state_as_of,
            "knowledge_state_as_of": knowledge_state_as_of,
        },
        "availability": {
            "source_availability_status": source_availability_status,
            "reproducibility_status": reproducibility_status,
            "reifiability_status": reifiability_status,
            "downstream_action_status": downstream_action_status,
        },
        "notes": notes,
        "logical_root": logical_root,
        "layout": layout,
        "fingerprint_mode": fingerprint_mode,
        "parents": list(parents or []),
        "source_state_documents": list(source_state_documents or []),
        "control_documents": list(control_documents or []),
        "artifacts": list(artifacts),
        "coverage_summary": coverage_summary,
        "source_dataset_manifest": "",
        "source_state_manifest": "",
        "issue_log_snapshot": "",
        "extract_plan_snapshot": "",
    }
    if extra_metadata:
        payload["extra_metadata"] = extra_metadata
    return payload


def build_slice_manifest(
    *,
    slice_root: Path,
    slice_name: str,
    source_dataset_manifest: str,
    selection_description: str,
    selection_criteria_path: str = "",
    issue_log_snapshot: str = "",
    extract_plan_snapshot: str = "",
    as_of: str = "",
    notes: str = "",
    source_state_manifest: str = "",
    source_state_as_of: str = "",
    knowledge_state_as_of: str = "",
    source_availability_status: str = "available",
    reproducibility_status: str = "fully_rebuildable",
    reifiability_status: str = "fully_reifiable",
    downstream_action_status: str = "none",
    layout: str = "",
) -> Dict[str, object]:
    return build_dataset_snapshot(
        data_root=slice_root,
        dataset_kind="slice",
        title=slice_name,
        source_dataset_manifest=source_dataset_manifest,
        source_state_manifest=source_state_manifest,
        issue_log_snapshot=issue_log_snapshot,
        extract_plan_snapshot=extract_plan_snapshot,
        as_of=as_of,
        source_state_as_of=source_state_as_of,
        knowledge_state_as_of=knowledge_state_as_of,
        source_availability_status=source_availability_status,
        reproducibility_status=reproducibility_status,
        reifiability_status=reifiability_status,
        downstream_action_status=downstream_action_status,
        layout=layout,
        notes=notes,
        slice_name=slice_name,
        stage="slice",
        extra_metadata={
            "slice_name": slice_name,
            "selection_description": selection_description,
            "selection_criteria_path": selection_criteria_path,
        },
    )


def write_dataset_manifest_bundle(
    *,
    manifest_root: Path,
    snapshot: Dict[str, object],
    history_event: Dict[str, object],
) -> Dict[str, Path]:
    manifest_root.mkdir(parents=True, exist_ok=True)
    artifact_inventory_path = manifest_root / "artifact_inventory.jsonl"
    coverage_summary_path = manifest_root / "coverage_summary.json"
    observed_state_path = manifest_root / "observed_state.json"
    dataset_manifest_path = manifest_root / "dataset_manifest.json"
    history_log_path = manifest_root / "history.jsonl"

    artifacts = list(snapshot.get("artifacts", []))
    write_artifact_inventory(artifact_inventory_path, artifacts)
    artifact_hashes = [str(record.get("artifact_hash", "")) for record in artifacts]
    artifact_inventory_hash = sha256_file(artifact_inventory_path)
    coverage_summary = add_document_hash(
        {
            "manifest_type": "coverage_summary",
            "schema_version": PROVENANCE_SCHEMA_VERSION,
            "generated_at": snapshot["generated_at"],
            "dataset_id": snapshot["dataset_id"],
            "logical_root": snapshot["logical_root"],
            "coverage": snapshot["coverage_summary"],
        }
    )
    coverage_summary_path.write_text(json.dumps(coverage_summary, indent=2, sort_keys=True), encoding="utf-8")

    root_binding = snapshot.get("data_root_binding") or infer_binding(str(snapshot["data_root"]))

    observed_state = add_document_hash(
        {
            "manifest_type": "observed_state",
            "schema_version": PROVENANCE_SCHEMA_VERSION,
            "generated_at": snapshot["generated_at"],
            "dataset_id": snapshot["dataset_id"],
            "logical_root": snapshot["logical_root"],
            "layout": snapshot["layout"],
            "fingerprint_mode": snapshot["fingerprint_mode"],
            "data_root_binding": root_binding,
            "artifact_inventory_file": artifact_inventory_path.name,
            "artifact_inventory_hash": artifact_inventory_hash,
            "artifact_hashes_sha256": aggregate_hash(artifact_hashes),
            "artifact_count": len(artifacts),
            "total_bytes": snapshot["coverage_summary"].get("content_summary", {}).get("total_bytes", 0),
        }
    )
    observed_state_path.write_text(json.dumps(observed_state, indent=2, sort_keys=True), encoding="utf-8")

    dataset_manifest = add_document_hash(
        {
            "manifest_type": "dataset_manifest",
            "schema_version": PROVENANCE_SCHEMA_VERSION,
            "generated_at": snapshot["generated_at"],
            "dataset_id": snapshot["dataset_id"],
            "dataset_kind": snapshot["dataset_kind"],
            "title": snapshot["title"],
            "git_sha": snapshot["git_sha"],
            "as_of": snapshot["as_of"],
            "state_coordinates": snapshot.get("state_coordinates", {}),
            "availability": snapshot.get("availability", {}),
            "notes": snapshot["notes"],
            "logical_root": snapshot["logical_root"],
            "layout": snapshot["layout"],
            "data_root_binding": root_binding,
            "documents": {
                "observed_state": {
                    "locator": observed_state_path.name,
                    "document_hash": observed_state["document_hash"],
                },
                "coverage_summary": {
                    "locator": coverage_summary_path.name,
                    "document_hash": coverage_summary["document_hash"],
                },
                "artifact_inventory": {
                    "locator": artifact_inventory_path.name,
                    "document_hash": artifact_inventory_hash,
                },
            },
            "parents": snapshot.get("parents", []),
            "source_state_documents": snapshot.get("source_state_documents", []),
            "control_documents": snapshot.get("control_documents", []),
            "extra_metadata": snapshot.get("extra_metadata", {}),
        }
    )
    dataset_manifest_path.write_text(json.dumps(dataset_manifest, indent=2, sort_keys=True), encoding="utf-8")

    event_payload = add_document_hash(
        {
            **history_event,
            "schema_version": PROVENANCE_SCHEMA_VERSION,
            "dataset_manifest_hash": dataset_manifest["document_hash"],
        }
    )
    with history_log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event_payload, sort_keys=True) + "\n")

    return {
        "dataset_manifest": dataset_manifest_path,
        "observed_state": observed_state_path,
        "artifact_inventory": artifact_inventory_path,
        "coverage_summary": coverage_summary_path,
        "history_log": history_log_path,
    }


def append_history_event(history_log_path: Path, event_payload: Dict[str, object]) -> Path:
    history_log_path.parent.mkdir(parents=True, exist_ok=True)
    event_document = add_document_hash(
        {
            **event_payload,
            "schema_version": event_payload.get("schema_version", PROVENANCE_SCHEMA_VERSION),
        }
    )
    with history_log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event_document, sort_keys=True) + "\n")
    return history_log_path


def infer_binding(locator: str) -> Dict[str, str]:
    text = (locator or "").strip()
    if text.startswith("s3://"):
        return {
            "binding_type": "s3_prefix",
            "locator": text,
        }
    return {
        "binding_type": "posix_path",
        "locator": text,
    }


def verify_manifest_bundle(manifest_root: Path, *, check_bindings: bool = False) -> Dict[str, object]:
    manifest_root = normalize_user_path(manifest_root)
    dataset_manifest_path = manifest_root / "dataset_manifest.json"
    observed_state_path = manifest_root / "observed_state.json"
    coverage_summary_path = manifest_root / "coverage_summary.json"
    artifact_inventory_path = manifest_root / "artifact_inventory.jsonl"

    errors: List[str] = []
    warnings: List[str] = []

    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    observed_state = json.loads(observed_state_path.read_text(encoding="utf-8"))
    coverage_summary = json.loads(coverage_summary_path.read_text(encoding="utf-8"))
    artifacts = read_jsonl(artifact_inventory_path)

    if add_document_hash(dataset_manifest)["document_hash"] != dataset_manifest.get("document_hash", ""):
        errors.append("dataset_manifest.json hash mismatch")
    if add_document_hash(observed_state)["document_hash"] != observed_state.get("document_hash", ""):
        errors.append("observed_state.json hash mismatch")
    if add_document_hash(coverage_summary)["document_hash"] != coverage_summary.get("document_hash", ""):
        errors.append("coverage_summary.json hash mismatch")

    artifact_inventory_hash = sha256_file(artifact_inventory_path)
    if dataset_manifest.get("documents", {}).get("artifact_inventory", {}).get("document_hash", "") != artifact_inventory_hash:
        errors.append("artifact_inventory.jsonl hash mismatch")
    if observed_state.get("artifact_inventory_hash", "") != artifact_inventory_hash:
        errors.append("observed_state artifact inventory hash mismatch")

    artifact_hashes: List[str] = []
    for index, record in enumerate(artifacts, start=1):
        expected = build_artifact_hash(record)
        actual = str(record.get("artifact_hash", ""))
        if expected != actual:
            errors.append(f"artifact_inventory.jsonl row {index} artifact_hash mismatch")
        artifact_hashes.append(actual)
        if check_bindings:
            binding_error = verify_artifact_binding(record)
            if binding_error:
                errors.append(binding_error)

    aggregate = aggregate_hash(artifact_hashes)
    if observed_state.get("artifact_hashes_sha256", "") != aggregate:
        errors.append("observed_state aggregate artifact hash mismatch")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "dataset_id": dataset_manifest.get("dataset_id", ""),
        "dataset_kind": dataset_manifest.get("dataset_kind", ""),
        "dataset_manifest_hash": dataset_manifest.get("document_hash", ""),
        "artifact_count": len(artifacts),
        "state_coordinates": dataset_manifest.get("state_coordinates", {}),
        "availability": effective_availability(manifest_root),
    }


def show_lineage(manifest_path: Path) -> Dict[str, object]:
    manifest_path = normalize_user_path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_root = manifest_path.parent
    return {
        "dataset_id": manifest.get("dataset_id", ""),
        "dataset_kind": manifest.get("dataset_kind", ""),
        "title": manifest.get("title", ""),
        "logical_root": manifest.get("logical_root", {}),
        "dataset_manifest_hash": manifest.get("document_hash", ""),
        "state_coordinates": manifest.get("state_coordinates", {}),
        "availability": effective_availability(manifest_root),
        "parents": manifest.get("parents", []),
        "source_state_documents": manifest.get("source_state_documents", []),
        "control_documents": manifest.get("control_documents", []),
        "documents": manifest.get("documents", {}),
    }


def dataset_state_summary(manifest_root: Path) -> Dict[str, object]:
    manifest_root = normalize_user_path(manifest_root)
    dataset_manifest_path = manifest_root / "dataset_manifest.json"
    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    state_coordinates = dataset_manifest.get("state_coordinates", {})
    availability = effective_availability(manifest_root)
    return {
        "dataset_id": dataset_manifest.get("dataset_id", ""),
        "dataset_kind": dataset_manifest.get("dataset_kind", ""),
        "title": dataset_manifest.get("title", ""),
        "dataset_manifest_hash": dataset_manifest.get("document_hash", ""),
        "logical_root": dataset_manifest.get("logical_root", {}),
        "state_coordinates": state_coordinates,
        "availability": availability,
        "parents": dataset_manifest.get("parents", []),
        "source_state_documents": dataset_manifest.get("source_state_documents", []),
        "control_documents": dataset_manifest.get("control_documents", []),
    }


def snapshot_artifacts(
    *,
    data_root: Path,
    logical_root: Dict[str, object],
    layout: str,
    fingerprint_mode: str,
    progress_reporter: Callable[[Dict[str, object]], None] | None = None,
    progress_stage_prefix: str = "pre_run_inventory",
) -> tuple[List[Dict[str, object]], Dict[str, object]]:
    artifacts: List[Dict[str, object]] = []
    site_summary: Dict[str, Dict[str, object]] = {}
    all_participants = set()
    all_streams = set()
    file_count = 0
    total_bytes = 0

    for index, file_path in enumerate(
        iter_dataset_files(
            data_root,
            layout,
            progress_reporter=progress_reporter,
            progress_stage=f"{progress_stage_prefix}_walk_progress",
        ),
        start=1,
    ):
        relative = file_path.relative_to(data_root)
        address = logical_address_for_path(relative, logical_root=logical_root, layout=layout)
        record = build_artifact_record(
            file_path=file_path,
            relative=relative,
            address=address,
            fingerprint_mode=fingerprint_mode,
        )
        artifacts.append(record)
        size = int(record["observed"]["size_bytes"])
        site = address.site or ""
        participant_id = address.participant_id or ""
        stream = address.stream or ""

        file_count += 1
        total_bytes += size
        if site:
            bucket = site_summary.setdefault(
                site,
                {
                    "site": site,
                    "participants": set(),
                    "streams": set(),
                    "file_count": 0,
                    "total_bytes": 0,
                },
            )
            bucket["participants"].add(participant_id)
            bucket["streams"].add(stream)
            bucket["file_count"] += 1
            bucket["total_bytes"] += size
        if participant_id:
            all_participants.add(participant_id)
        if stream:
            all_streams.add(stream)
        if progress_reporter is not None:
            progress_reporter(
                {
                    "stage": f"{progress_stage_prefix}_progress",
                    "completed": index,
                    "relative_path": canonical_relative_locator(relative),
                }
            )

    rendered_sites: List[Dict[str, object]] = []
    for site in sorted(site_summary):
        bucket = site_summary[site]
        rendered_sites.append(
            {
                "site": site,
                "participant_count": len(bucket["participants"]),
                "participants": sorted(item for item in bucket["participants"] if item),
                "stream_count": len(bucket["streams"]),
                "streams": sorted(item for item in bucket["streams"] if item),
                "file_count": bucket["file_count"],
                "total_bytes": bucket["total_bytes"],
            }
        )

    artifacts.sort(key=lambda record: (record["logical_address_display"], record["artifact_hash"]))
    return artifacts, coverage_with_neutral_aliases(
        site_summary=rendered_sites,
        participant_ids=all_participants,
        stream_ids=all_streams,
        file_count=file_count,
        total_bytes=total_bytes,
    )


def write_streaming_artifact_inventory(
    *,
    path: Path,
    data_root: Path,
    logical_root: Dict[str, object],
    layout: str,
    fingerprint_mode: str,
    progress_reporter: Callable[[Dict[str, object]], None] | None = None,
) -> Dict[str, int]:
    artifact_count = 0
    with path.open("w", encoding="utf-8") as fh:
        for file_path in iter_dataset_files(data_root, layout, progress_reporter=progress_reporter):
            relative = file_path.relative_to(data_root)
            address = logical_address_for_path(relative, logical_root=logical_root, layout=layout)
            record = build_artifact_record(
                file_path=file_path,
                relative=relative,
                address=address,
                fingerprint_mode=fingerprint_mode,
            )
            fh.write(json.dumps(record, sort_keys=True) + "\n")
            artifact_count += 1
            if progress_reporter is not None:
                progress_reporter(
                    {
                        "stage": "pre_run_inventory_progress",
                        "completed": artifact_count,
                        "relative_path": canonical_relative_locator(relative),
                    }
                )
    return {"artifact_count": artifact_count}


def iter_dataset_files(
    data_root: Path,
    layout: str,
    *,
    progress_reporter: Callable[[Dict[str, object]], None] | None = None,
    progress_stage: str = "pre_run_inventory_walk_progress",
) -> Iterable[Path]:
    if not data_root.exists():
        return []
    directories_visited = 0
    candidate_files_seen = 0
    for root, dir_names, file_names in os.walk(data_root):
        root_path = Path(root)
        try:
            relative_root = root_path.relative_to(data_root)
        except ValueError:
            relative_root = Path(".")
        if relative_root != Path(".") and any(part.startswith("_") for part in relative_root.parts):
            dir_names[:] = []
            continue
        if layout == "flat_files_v1" and relative_root != Path(".") and any(_is_flat_file_control_part(part) for part in relative_root.parts):
            dir_names[:] = []
            continue

        if layout == "flat_files_v1":
            dir_names[:] = sorted(name for name in dir_names if not name.startswith("_") and not _is_flat_file_control_part(name))
        else:
            dir_names[:] = sorted(name for name in dir_names if not name.startswith("_"))
        directories_visited += 1
        if progress_reporter is not None and (directories_visited <= 3 or directories_visited % 100 == 0):
            progress_reporter(
                {
                    "stage": progress_stage,
                    "directories_visited": directories_visited,
                    "candidate_files_seen": candidate_files_seen,
                    "current_directory": (
                        "."
                        if relative_root == Path(".")
                        else canonical_relative_locator(relative_root)
                    ),
                }
            )

        for file_name in sorted(file_names):
            if file_name.startswith("_") or file_name.startswith("."):
                continue
            if layout in {"passive_merged_v1", "site_participant_stream_v1", "participant_stream_v1"} and not file_name.endswith(".csv.gz"):
                continue
            path = root_path / file_name
            relative = path.relative_to(data_root)
            if any(part.startswith("_") for part in relative.parts):
                continue
            candidate_files_seen += 1
            yield path


def _is_flat_file_control_part(name: str) -> bool:
    if name in {"exports", "manifests", "sync-history", "logs"}:
        return True
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$", name))


def logical_address_for_path(relative: Path, *, logical_root: Dict[str, object], layout: str) -> LogicalAddress:
    if layout in GROUP_ENTITY_STREAM_LAYOUTS - {"raw_source_v1"}:
        parts = relative.parts
        if len(parts) < 4:
            raise ValueError(f"Expected site/participant/stream/file layout, got: {relative}")
        site, participant_id, stream = parts[0], parts[1], parts[2]
        artifact = "/".join(parts[3:])
        return LogicalAddress(
            surface=str(logical_root["surface"]),
            domain=str(logical_root["domain"]),
            stage=str(logical_root["stage"]),
            dataset_id=str(logical_root.get("dataset_id", "")),
            slice_name=str(logical_root.get("slice_name", "")),
            site=site,
            participant_id=participant_id,
            stream=stream,
            artifact=artifact,
            coordinates=passive_logical_coordinates(group=site, entity_id=participant_id, stream=stream),
            labels=passive_logical_labels(site=site, participant_id=participant_id, stream=stream),
        )
    if layout == "participant_stream_v1":
        parts = relative.parts
        if len(parts) < 2:
            raise ValueError(f"Expected stream/file layout, got: {relative}")
        stream = parts[0]
        artifact = "/".join(parts[1:])
        return LogicalAddress(
            surface=str(logical_root["surface"]),
            domain=str(logical_root["domain"]),
            stage=str(logical_root["stage"]),
            dataset_id=str(logical_root.get("dataset_id", "")),
            slice_name=str(logical_root.get("slice_name", "")),
            site=str(logical_root.get("site", "")),
            participant_id=str(logical_root.get("participant_id", "")),
            stream=stream,
            artifact=artifact,
            coordinates=passive_logical_coordinates(
                group=str(logical_root.get("group") or logical_root.get("site", "")),
                entity_id=str(logical_root.get("entity_id") or logical_root.get("participant_id", "")),
                stream=stream,
            ),
            labels=passive_logical_labels(
                site=str(logical_root.get("site", "")),
                participant_id=str(logical_root.get("participant_id", "")),
                stream=stream,
            ),
        )
    return LogicalAddress(
        surface=str(logical_root["surface"]),
        domain=str(logical_root["domain"]),
        stage=str(logical_root["stage"]),
        dataset_id=str(logical_root.get("dataset_id", "")),
        slice_name=str(logical_root.get("slice_name", "")),
        artifact=str(relative),
    )


def build_artifact_record(
    *,
    file_path: Path,
    relative: Path,
    address: LogicalAddress,
    fingerprint_mode: str,
) -> Dict[str, object]:
    observed: Dict[str, object] = {
        "fingerprint_mode": fingerprint_mode,
        "size_bytes": file_path.stat().st_size,
        "modified_at": file_mtime_iso(file_path),
    }
    if fingerprint_mode == "content_sha256":
        observed["content_sha256"] = sha256_file(file_path)
    bindings = [
        PhysicalBinding(
            binding_type="posix_path",
            locator=str(file_path),
            relative_locator=canonical_relative_locator(relative),
        ).to_dict()
    ]
    record: Dict[str, object] = {
        "artifact_type": "file",
        "logical_address": address.to_dict(),
        "logical_address_display": address.display(),
        "observed": observed,
        "physical_bindings": bindings,
    }
    record["artifact_hash"] = build_artifact_hash(record)
    return record


def build_artifact_hash(record: Dict[str, object]) -> str:
    payload = {
        "artifact_type": record.get("artifact_type", "file"),
        "logical_address": record.get("logical_address", {}),
        "observed": record.get("observed", {}),
    }
    return sha256_json(payload)


def build_parent_document_refs(locators: Sequence[str]) -> List[Dict[str, str]]:
    refs: List[Dict[str, str]] = []
    for locator in locators:
        ref = document_reference_from_path(locator, role="parent_dataset_manifest", relation="derived_from")
        if ref is not None:
            refs.append(ref.to_dict())
    return refs


def build_source_state_document_refs(locators: Sequence[str]) -> List[Dict[str, str]]:
    refs: List[Dict[str, str]] = []
    for locator in locators:
        ref = document_reference_from_path(locator, role="source_state_manifest", relation="observed_from")
        if ref is not None:
            refs.append(ref.to_dict())
    return refs


def infer_source_state_as_of(locator: str) -> str:
    ref_path = Path(str(locator or "")).expanduser()
    if not str(locator or "").strip() or not ref_path.exists() or not ref_path.is_file():
        return ""
    try:
        payload = json.loads(ref_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    state_coordinates = payload.get("state_coordinates", {})
    if isinstance(state_coordinates, dict) and state_coordinates.get("source_state_as_of"):
        return str(state_coordinates.get("source_state_as_of", ""))
    return str(payload.get("generated_at", ""))


def build_control_document_refs(*, issue_log_snapshot: str, extract_plan_snapshot: str) -> List[Dict[str, str]]:
    refs: List[Dict[str, str]] = []
    if issue_log_snapshot:
        ref = document_reference_from_path(issue_log_snapshot, role="issue_log_snapshot")
        if ref is not None:
            refs.append(ref.to_dict())
    if extract_plan_snapshot:
        ref = document_reference_from_path(extract_plan_snapshot, role="extract_plan_snapshot")
        if ref is not None:
            refs.append(ref.to_dict())
    return refs


def effective_availability(manifest_root: Path) -> Dict[str, object]:
    dataset_manifest_path = manifest_root / "dataset_manifest.json"
    history_log_path = manifest_root / "history.jsonl"
    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    availability = dict(dataset_manifest.get("availability", {}))
    availability.setdefault("source_availability_status", "available")
    availability.setdefault("reproducibility_status", "fully_rebuildable")
    availability.setdefault("reifiability_status", "fully_reifiable")
    availability.setdefault("downstream_action_status", "none")
    availability["current_from_history"] = False
    availability["latest_event_type"] = ""
    availability["latest_event_locator"] = ""

    if history_log_path.exists():
        for event in read_jsonl(history_log_path):
            if str(event.get("event_type", "")) != "source_availability_update":
                continue
            update = event.get("availability_update", {})
            if isinstance(update, dict):
                availability["source_availability_status"] = str(
                    update.get("source_availability_status", availability["source_availability_status"])
                )
                availability["reproducibility_status"] = str(
                    update.get("reproducibility_status", availability["reproducibility_status"])
                )
                if str(update.get("reifiability_status", "")).strip():
                    availability["reifiability_status"] = str(
                        update.get("reifiability_status", availability["reifiability_status"])
                    )
                if str(update.get("downstream_action_status", "")).strip():
                    availability["downstream_action_status"] = str(
                        update.get("downstream_action_status", availability["downstream_action_status"])
                    )
                if update.get("reason"):
                    availability["reason"] = str(update.get("reason", ""))
                if update.get("effective_at"):
                    availability["effective_at"] = str(update.get("effective_at", ""))
                if "checked_artifact_count" in update:
                    availability["checked_artifact_count"] = int(update.get("checked_artifact_count", 0) or 0)
                if "missing_artifact_count" in update:
                    availability["missing_artifact_count"] = int(update.get("missing_artifact_count", 0) or 0)
                if "unchecked_artifact_count" in update:
                    availability["unchecked_artifact_count"] = int(update.get("unchecked_artifact_count", 0) or 0)
            availability["current_from_history"] = True
            availability["latest_event_type"] = str(event.get("event_type", ""))
            availability["latest_event_locator"] = str(event.get("event_locator", ""))
            availability["latest_event_hash"] = str(event.get("event_hash", ""))
    return availability


def document_reference_from_path(locator: str, *, role: str, relation: str = "") -> Optional[DocumentReference]:
    text = (locator or "").strip()
    if not text:
        return None
    path = Path(text).expanduser()
    if path.exists() and path.is_file():
        resolved_path = safe_resolve_path(path)
        document_hash = sha256_file(resolved_path)
        document_type = path.suffix.lstrip(".")
        dataset_id = ""
        title = ""
        if path.name.endswith(".json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                dataset_id = str(payload.get("dataset_id", ""))
                title = str(payload.get("title", ""))
                if payload.get("document_hash"):
                    document_hash = str(payload["document_hash"])
            except Exception:
                pass
        return DocumentReference(
            role=role,
            locator=str(resolved_path),
            document_hash=document_hash,
            document_type=document_type,
            dataset_id=dataset_id,
            title=title,
            relation=relation,
        )
    return DocumentReference(role=role, locator=text, document_hash="", relation=relation)


def infer_logical_root(
    *,
    data_root: Path,
    dataset_id: str,
    dataset_kind: str,
    surface: str,
    domain: str,
    stage: str,
    slice_name: str,
) -> Dict[str, object]:
    parts = {part.lower(): part for part in data_root.parts}
    inferred_surface = surface or (
        "study" if "study" in parts else
        "test" if "test" in parts else
        f"slice:{slice_name or data_root.parent.name}" if dataset_kind == "slice" else
        "analysis" if "analysis" in parts else
        "unknown"
    )
    inferred_domain = domain or (
        "passive-data" if "passive-data" in parts else
        "redcap" if "redcap" in parts else
        "analysis" if "analysis" in parts else
        "unknown"
    )
    inferred_stage = stage or (
        "cleaned" if dataset_kind == "cleaned_extract" else
        "slice" if dataset_kind == "slice" else
        "merged" if "merged-data" in parts else
        "summary" if "summary-data" in parts else
        "dataset"
    )
    address = LogicalAddress(
        surface=inferred_surface,
        domain=inferred_domain,
        stage=inferred_stage,
        dataset_id=dataset_id,
        slice_name=slice_name if dataset_kind == "slice" else "",
    )
    return address.to_dict()


def infer_layout(data_root: Path, logical_root: Dict[str, object]) -> str:
    if str(logical_root.get("stage", "")) in {"merged", "cleaned", "slice"}:
        return "passive_merged_v1"
    return "flat_files_v1"


def write_artifact_inventory(path: Path, records: Sequence[Dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def verify_artifact_binding(record: Dict[str, object]) -> str:
    observed = record.get("observed", {})
    size_expected = int(observed.get("size_bytes", 0) or 0)
    modified_expected = str(observed.get("modified_at", ""))
    content_expected = str(observed.get("content_sha256", ""))
    bindings = record.get("physical_bindings", [])
    if not bindings:
        return "artifact missing physical binding"
    binding = bindings[0]
    if binding.get("binding_type") != "posix_path":
        return ""
    locator = str(binding.get("locator", ""))
    path = Path(locator)
    if not path.exists():
        return f"missing bound file: {locator}"
    if path.stat().st_size != size_expected:
        return f"size mismatch for bound file: {locator}"
    if file_mtime_iso(path) != modified_expected:
        return f"mtime mismatch for bound file: {locator}"
    if content_expected and sha256_file(path) != content_expected:
        return f"content hash mismatch for bound file: {locator}"
    return ""
