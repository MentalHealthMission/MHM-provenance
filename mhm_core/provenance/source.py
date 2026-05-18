"""Observed source-state snapshot helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
import uuid

from .manifests import build_artifact_hash, build_parent_document_refs, write_dataset_manifest_bundle
from .model import LogicalAddress, PROVENANCE_SCHEMA_VERSION, utc_now_iso
from .passive_data_layout import GROUP_ENTITY_STREAM_LAYOUTS, coverage_with_neutral_aliases


def split_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Expected s3:// URI, got {uri}")
    remainder = uri[len("s3://") :]
    bucket, _, key = remainder.partition("/")
    if not bucket:
        raise ValueError(f"Missing bucket in S3 URI: {uri}")
    return bucket, key


def snapshot_source_state(
    *,
    source: str,
    manifest_root: Path,
    source_id: str = "",
    title: str = "",
    surface: str = "",
    domain: str = "",
    stage: str = "captured",
    layout: str = "raw_source_v1",
    notes: str = "",
    fingerprint_mode: str = "metadata",
    source_dataset_manifest: str = "",
    include_relative_prefixes: Optional[Sequence[str]] = None,
    boto3_session: Optional[Any] = None,
) -> Dict[str, object]:
    source_id_value = source_id or str(uuid.uuid4())
    logical_root = LogicalAddress(
        surface=surface or "source",
        domain=domain or "passive-data",
        stage=stage or "captured",
        dataset_id=source_id_value,
    ).to_dict()
    generated_at = utc_now_iso()

    if source.startswith("s3://"):
        if boto3_session is None:
            import boto3

            boto3_session = boto3.session.Session()
        artifacts, coverage_summary = snapshot_s3_source(
            boto3_session.client("s3"),
            source,
            logical_root=logical_root,
            layout=layout,
            fingerprint_mode=fingerprint_mode,
            include_relative_prefixes=include_relative_prefixes,
        )
        source_binding = {
            "binding_type": "s3_prefix",
            "locator": source,
        }
    else:
        source_path = Path(source).expanduser().resolve()
        artifacts, coverage_summary = snapshot_local_source(
            source_path,
            logical_root=logical_root,
            layout=layout,
            fingerprint_mode=fingerprint_mode,
            include_relative_prefixes=include_relative_prefixes,
        )
        source_binding = {
            "binding_type": "posix_path",
            "locator": str(source_path),
        }

    snapshot: Dict[str, object] = {
        "dataset_id": source_id_value,
        "dataset_kind": "source_state",
        "title": title or f"Observed source state for {source}",
        "generated_at": generated_at,
        "git_sha": "",
        "data_root": source_binding["locator"],
        "as_of": generated_at,
        "state_coordinates": {
            "built_at": generated_at,
            "dataset_state_as_of": generated_at,
            "source_state_as_of": generated_at,
            "knowledge_state_as_of": "",
        },
        "availability": {
            "source_availability_status": "available",
            "reproducibility_status": "fully_rebuildable",
            "reifiability_status": "fully_reifiable",
            "downstream_action_status": "none",
        },
        "notes": notes,
        "logical_root": logical_root,
        "layout": layout,
        "fingerprint_mode": fingerprint_mode,
        "parents": build_parent_document_refs([source_dataset_manifest]),
        "source_state_documents": [],
        "control_documents": [],
        "artifacts": artifacts,
        "coverage_summary": coverage_summary,
        "source_dataset_manifest": source_dataset_manifest,
        "source_state_manifest": "",
        "issue_log_snapshot": "",
        "extract_plan_snapshot": "",
        "extra_metadata": {
            "source_binding": source_binding,
            "source_scope_prefixes": list(_normalize_relative_prefixes(include_relative_prefixes)),
            "schema_version": PROVENANCE_SCHEMA_VERSION,
        },
    }
    paths = write_dataset_manifest_bundle(
        manifest_root=manifest_root,
        snapshot=snapshot,
        history_event={
            "event_type": "snapshot_source_state",
            "generated_at": generated_at,
            "dataset_id": source_id_value,
            "dataset_kind": "source_state",
            "data_root": source_binding["locator"],
            "logical_root": logical_root,
            "layout": layout,
        },
    )
    return {
        "snapshot": snapshot,
        "paths": paths,
    }


def snapshot_s3_source(
    s3_client,
    source_uri: str,
    *,
    logical_root: Dict[str, object],
    layout: str,
    fingerprint_mode: str,
    include_relative_prefixes: Optional[Sequence[str]] = None,
) -> tuple[List[Dict[str, object]], Dict[str, object]]:
    bucket, prefix = split_s3_uri(source_uri)
    artifacts: List[Dict[str, object]] = []
    relative_prefixes = _normalize_relative_prefixes(include_relative_prefixes)
    full_prefixes = _full_s3_scan_prefixes(prefix=prefix, relative_prefixes=relative_prefixes)

    paginator = s3_client.get_paginator("list_objects_v2")
    for scan_prefix in full_prefixes:
        for page in paginator.paginate(Bucket=bucket, Prefix=scan_prefix):
            for obj in page.get("Contents", []):
                key = str(obj.get("Key", ""))
                if not key or key.endswith("/"):
                    continue
                relative_key = key[len(prefix.rstrip("/") + "/") :] if prefix else key
                if relative_prefixes and not any(
                    relative_key == candidate or relative_key.startswith(candidate + "/")
                    for candidate in relative_prefixes
                ):
                    continue
                if any(part.startswith("_") for part in relative_key.split("/")):
                    continue
                address = logical_address_for_source(relative_key, logical_root=logical_root, layout=layout)
                last_modified = obj.get("LastModified")
                modified_at = ""
                if isinstance(last_modified, datetime):
                    if last_modified.tzinfo is None:
                        last_modified = last_modified.replace(tzinfo=timezone.utc)
                    modified_at = last_modified.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                observed = {
                    "fingerprint_mode": fingerprint_mode,
                    "size_bytes": int(obj.get("Size", 0) or 0),
                    "modified_at": modified_at,
                }
                etag = str(obj.get("ETag", "")).strip('"')
                if etag:
                    observed["etag"] = etag
                record = {
                    "artifact_type": "s3_object",
                    "logical_address": address.to_dict(),
                    "logical_address_display": address.display(),
                    "observed": observed,
                    "physical_bindings": [
                        {
                            "binding_type": "s3_object",
                            "locator": f"s3://{bucket}/{key}",
                            "relative_locator": relative_key,
                        }
                    ],
                }
                record["artifact_hash"] = build_artifact_hash(record)
                artifacts.append(record)

    return artifacts_and_coverage(artifacts)


def snapshot_local_source(
    source_root: Path,
    *,
    logical_root: Dict[str, object],
    layout: str,
    fingerprint_mode: str,
    include_relative_prefixes: Optional[Sequence[str]] = None,
) -> tuple[List[Dict[str, object]], Dict[str, object]]:
    artifacts: List[Dict[str, object]] = []
    relative_prefixes = _normalize_relative_prefixes(include_relative_prefixes)
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source_root)
        relative_locator = str(relative).replace("\\", "/")
        if relative_prefixes and not any(
            relative_locator == candidate or relative_locator.startswith(candidate + "/")
            for candidate in relative_prefixes
        ):
            continue
        if any(part.startswith("_") for part in relative.parts):
            continue
        address = logical_address_for_source(relative_locator, logical_root=logical_root, layout=layout)
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        observed = {
            "fingerprint_mode": fingerprint_mode,
            "size_bytes": path.stat().st_size,
            "modified_at": modified_at,
        }
        record = {
            "artifact_type": "file",
            "logical_address": address.to_dict(),
            "logical_address_display": address.display(),
            "observed": observed,
            "physical_bindings": [
                {
                    "binding_type": "posix_path",
                    "locator": str(path),
                    "relative_locator": relative_locator,
                }
            ],
        }
        record["artifact_hash"] = build_artifact_hash(record)
        artifacts.append(record)
    return artifacts_and_coverage(artifacts)


def _normalize_relative_prefixes(include_relative_prefixes: Optional[Sequence[str]]) -> tuple[str, ...]:
    normalized: list[str] = []
    for item in include_relative_prefixes or []:
        candidate = str(item).strip().strip("/")
        if not candidate:
            continue
        if candidate not in normalized:
            normalized.append(candidate)
    return tuple(normalized)


def _full_s3_scan_prefixes(*, prefix: str, relative_prefixes: Sequence[str]) -> tuple[str, ...]:
    base_prefix = prefix.rstrip("/")
    if not relative_prefixes:
        return (base_prefix + "/",) if base_prefix else ("",)
    scan_prefixes: list[str] = []
    for relative_prefix in relative_prefixes:
        full_prefix = "/".join(part for part in [base_prefix, relative_prefix] if part).rstrip("/") + "/"
        if full_prefix not in scan_prefixes:
            scan_prefixes.append(full_prefix)
    return tuple(scan_prefixes)


def logical_address_for_source(relative_locator: str, *, logical_root: Dict[str, object], layout: str) -> LogicalAddress:
    parts = [part for part in relative_locator.split("/") if part]
    if layout in GROUP_ENTITY_STREAM_LAYOUTS and len(parts) >= 4:
        site, participant_id, stream = parts[0], parts[1], parts[2]
        artifact = "/".join(parts[3:])
        return LogicalAddress(
            surface=str(logical_root["surface"]),
            domain=str(logical_root["domain"]),
            stage=str(logical_root["stage"]),
            dataset_id=str(logical_root.get("dataset_id", "")),
            site=site,
            participant_id=participant_id,
            stream=stream,
            artifact=artifact,
        )
    return LogicalAddress(
        surface=str(logical_root["surface"]),
        domain=str(logical_root["domain"]),
        stage=str(logical_root["stage"]),
        dataset_id=str(logical_root.get("dataset_id", "")),
        artifact=relative_locator,
    )


def artifacts_and_coverage(artifacts: Sequence[Dict[str, object]]) -> tuple[List[Dict[str, object]], Dict[str, object]]:
    site_summary: Dict[str, Dict[str, object]] = {}
    participants = set()
    streams = set()
    total_bytes = 0

    for record in artifacts:
        address = record["logical_address"]
        site = str(address.get("site", ""))
        participant_id = str(address.get("participant_id", ""))
        stream = str(address.get("stream", ""))
        size = int(record["observed"].get("size_bytes", 0) or 0)
        total_bytes += size
        if participant_id:
            participants.add(participant_id)
        if stream:
            streams.add(stream)
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
            if participant_id:
                bucket["participants"].add(participant_id)
            if stream:
                bucket["streams"].add(stream)
            bucket["file_count"] += 1
            bucket["total_bytes"] += size

    rendered_sites: List[Dict[str, object]] = []
    for site in sorted(site_summary):
        bucket = site_summary[site]
        rendered_sites.append(
            {
                "site": site,
                "participant_count": len(bucket["participants"]),
                "participants": sorted(bucket["participants"]),
                "stream_count": len(bucket["streams"]),
                "streams": sorted(bucket["streams"]),
                "file_count": bucket["file_count"],
                "total_bytes": bucket["total_bytes"],
            }
        )

    sorted_artifacts = sorted(artifacts, key=lambda item: (item["logical_address_display"], item["artifact_hash"]))
    return sorted_artifacts, coverage_with_neutral_aliases(
        site_summary=rendered_sites,
        participant_ids=participants,
        stream_ids=streams,
        file_count=len(sorted_artifacts),
        total_bytes=total_bytes,
    )
