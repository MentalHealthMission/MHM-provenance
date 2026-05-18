"""Source-availability and withdrawal provenance events."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Sequence

from .governance import create_governing_snapshot_manifest
from .hashing import add_document_hash
from .manifests import append_history_event, document_reference_from_path
from .model import PROVENANCE_SCHEMA_VERSION, utc_now_iso


SOURCE_AVAILABILITY_EVENT_KINDS = {
    "withdrawal",
    "removal",
    "restoration",
    "correction",
    "other",
}

SOURCE_AVAILABILITY_STATUSES = {
    "available",
    "partially_withdrawn",
    "unavailable",
    "restored",
}

REPRODUCIBILITY_STATUSES = {
    "fully_rebuildable",
    "historically_observed_only",
    "not_rebuildable_from_live_source",
    "restored_rebuildability",
}

REIFIABILITY_STATUSES = {
    "fully_reifiable",
    "partially_reifiable",
    "not_reifiable_from_live_bindings",
}

DOWNSTREAM_ACTION_STATUSES = {
    "none",
    "review_required",
    "removal_required",
    "removed",
}


def create_source_availability_event(
    *,
    event_path: Path,
    source_state_manifest: str = "",
    target_dataset_manifest: str = "",
    event_kind: str,
    source_availability_status: str,
    reproducibility_status: str,
    reifiability_status: str = "",
    downstream_action_status: str = "",
    actor: str = "",
    effective_at: str = "",
    observed_at: str = "",
    reason: str = "",
    notes: str = "",
    affected_scopes: Sequence[str] | None = None,
    checked_artifact_count: int = 0,
    missing_artifact_count: int = 0,
    unchecked_artifact_count: int = 0,
    append_target_history: bool = False,
) -> Dict[str, object]:
    kind = event_kind.strip().lower()
    if kind not in SOURCE_AVAILABILITY_EVENT_KINDS:
        raise ValueError(f"Unsupported source availability event_kind: {event_kind!r}")
    source_status = source_availability_status.strip().lower()
    if source_status not in SOURCE_AVAILABILITY_STATUSES:
        raise ValueError(f"Unsupported source_availability_status: {source_availability_status!r}")
    repro_status = reproducibility_status.strip()
    if repro_status not in REPRODUCIBILITY_STATUSES:
        raise ValueError(f"Unsupported reproducibility_status: {reproducibility_status!r}")
    reify_status = reifiability_status.strip()
    if reify_status and reify_status not in REIFIABILITY_STATUSES:
        raise ValueError(f"Unsupported reifiability_status: {reifiability_status!r}")
    downstream_status = downstream_action_status.strip()
    if downstream_status and downstream_status not in DOWNSTREAM_ACTION_STATUSES:
        raise ValueError(f"Unsupported downstream_action_status: {downstream_action_status!r}")

    event_path = event_path.expanduser().resolve()
    event_path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = utc_now_iso()
    previous_governing_manifest = _latest_governing_manifest_for_target(target_dataset_manifest)

    source_ref = document_reference_from_path(
        source_state_manifest,
        role="source_state_manifest",
        relation="affects",
    )
    target_ref = document_reference_from_path(
        target_dataset_manifest,
        role="target_dataset_manifest",
        relation="changes_rebuildability_of",
    )

    payload = add_document_hash(
        {
            "manifest_type": "source_availability_event",
            "schema_version": PROVENANCE_SCHEMA_VERSION,
            "event_type": "source_availability_update",
            "generated_at": generated_at,
            "event_kind": kind,
            "actor": actor,
            "source_state_manifest": source_ref.to_dict() if source_ref is not None else {},
            "target_dataset_manifest": target_ref.to_dict() if target_ref is not None else {},
            "availability_update": {
                "source_availability_status": source_status,
                "reproducibility_status": repro_status,
                "reifiability_status": reify_status,
                "downstream_action_status": downstream_status,
                "effective_at": effective_at or generated_at,
                "observed_at": observed_at or generated_at,
                "reason": reason,
                "checked_artifact_count": int(checked_artifact_count or 0),
                "missing_artifact_count": int(missing_artifact_count or 0),
                "unchecked_artifact_count": int(unchecked_artifact_count or 0),
            },
            "affected_scopes": list(affected_scopes or []),
            "notes": notes,
        }
    )
    event_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    governing_manifest_path = create_governing_snapshot_manifest(
        event_path=event_path,
        event_payload=payload,
        parent_manifest_paths=[previous_governing_manifest] if previous_governing_manifest else [],
    )
    governing_ref = document_reference_from_path(
        str(governing_manifest_path),
        role="governing_state_manifest",
        relation="governs",
    )

    history_log_path = ""
    if append_target_history and target_dataset_manifest:
        target_manifest_path = Path(target_dataset_manifest).expanduser().resolve()
        if target_manifest_path.exists() and target_manifest_path.is_file():
            history_log = target_manifest_path.parent / "history.jsonl"
            append_history_event(
                history_log,
                {
                    "event_type": "source_availability_update",
                    "generated_at": generated_at,
                    "event_locator": str(event_path),
                    "event_hash": payload["document_hash"],
                    "event_kind": kind,
                    "source_state_manifest": source_ref.to_dict() if source_ref is not None else {},
                    "target_dataset_manifest": target_ref.to_dict() if target_ref is not None else {},
                    "governing_state_manifest": governing_ref.to_dict() if governing_ref is not None else {},
                    "availability_update": payload["availability_update"],
                    "affected_scopes": list(affected_scopes or []),
                    "notes": notes,
                },
            )
            history_log_path = str(history_log)

    return {
        "event_document": payload,
        "event_path": str(event_path),
        "governing_manifest_path": str(governing_manifest_path),
        "history_log_path": history_log_path,
    }


def _latest_governing_manifest_for_target(target_dataset_manifest: str) -> str:
    locator = str(target_dataset_manifest).strip()
    if not locator:
        return ""
    target_manifest_path = Path(locator).expanduser().resolve()
    history_log = target_manifest_path.parent / "history.jsonl"
    if not history_log.exists():
        return ""
    try:
        rows = [json.loads(line) for line in history_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return ""
    for row in reversed(rows):
        if str(row.get("event_type", "")).strip() != "source_availability_update":
            continue
        governing_ref = dict(row.get("governing_state_manifest", {}))
        governing_locator = str(governing_ref.get("locator", "")).strip()
        if governing_locator:
            return governing_locator
    return ""
