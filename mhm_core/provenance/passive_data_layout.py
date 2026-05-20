"""Passive-data layout helpers for provenance manifests.

The generic provenance primitives can describe arbitrary files, but the first
supported MHM dataset layout is the passive-data group/entity/stream tree. The
legacy CONNECT names `site` and `participant_id` remain in persisted manifests
for compatibility; this module makes that layout boundary explicit and adds
neutral aliases for new consumers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Set


PASSIVE_DATA_DOMAIN = "passive-data"
PASSIVE_DATA_LAYOUTS = frozenset(
    {
        "passive_merged_v1",
        "raw_source_v1",
        "site_participant_stream_v1",
        "participant_stream_v1",
    }
)
GROUP_ENTITY_STREAM_LAYOUTS = frozenset(
    {
        "passive_merged_v1",
        "raw_source_v1",
        "site_participant_stream_v1",
    }
)


@dataclass(frozen=True)
class SourceSnapshotPreset:
    """Named defaults for adapting source-state snapshots to a data layout."""

    name: str
    surface: str
    domain: str
    stage: str
    layout: str
    fingerprint_mode: str


PASSIVE_SOURCE_SNAPSHOT_PRESET = SourceSnapshotPreset(
    name="passive-source-state-v1",
    surface="source",
    domain=PASSIVE_DATA_DOMAIN,
    stage="captured",
    layout="raw_source_v1",
    fingerprint_mode="metadata",
)

SOURCE_SNAPSHOT_PRESETS: Dict[str, SourceSnapshotPreset] = {
    PASSIVE_SOURCE_SNAPSHOT_PRESET.name: PASSIVE_SOURCE_SNAPSHOT_PRESET,
    "passive": PASSIVE_SOURCE_SNAPSHOT_PRESET,
    "passive-data": PASSIVE_SOURCE_SNAPSHOT_PRESET,
}


def resolve_source_snapshot_preset(preset: SourceSnapshotPreset | str | None) -> SourceSnapshotPreset:
    """Resolve a source snapshot preset, preserving the passive-data default."""

    if preset is None:
        return PASSIVE_SOURCE_SNAPSHOT_PRESET
    if isinstance(preset, SourceSnapshotPreset):
        return preset
    key = str(preset).strip()
    try:
        return SOURCE_SNAPSHOT_PRESETS[key]
    except KeyError as exc:
        raise ValueError(f"Unknown source snapshot preset: {preset}") from exc


def coverage_with_neutral_aliases(
    *,
    site_summary: Iterable[Mapping[str, object]],
    participant_ids: Set[str],
    stream_ids: Set[str],
    file_count: int,
    total_bytes: int,
) -> Dict[str, object]:
    """Return coverage with neutral names plus legacy CONNECT aliases."""

    rendered_sites = [_normalize_site_row(row) for row in site_summary]
    rendered_groups = [_group_row_from_site_row(row) for row in rendered_sites]
    content_summary: Dict[str, object] = {
        "group_count": len(rendered_groups),
        "entity_count": len(participant_ids),
        "stream_count": len(stream_ids),
        "file_count": int(file_count),
        "total_bytes": int(total_bytes),
        # Compatibility aliases retained for existing CONNECT manifests/tests.
        "site_count": len(rendered_sites),
        "participant_count": len(participant_ids),
    }
    return {
        "content_summary": content_summary,
        "group_summary": rendered_groups,
        "site_summary": rendered_sites,
    }


def _normalize_site_row(row: Mapping[str, object]) -> Dict[str, object]:
    participants = sorted(str(item) for item in row.get("participants", []) if str(item).strip())
    streams = sorted(str(item) for item in row.get("streams", []) if str(item).strip())
    return {
        "site": str(row.get("site", "")).strip(),
        "participant_count": int(row.get("participant_count", len(participants)) or 0),
        "participants": participants,
        "stream_count": int(row.get("stream_count", len(streams)) or 0),
        "streams": streams,
        "file_count": int(row.get("file_count", 0) or 0),
        "total_bytes": int(row.get("total_bytes", 0) or 0),
    }


def _group_row_from_site_row(row: Mapping[str, object]) -> Dict[str, object]:
    participants = [str(item) for item in row.get("participants", []) if str(item).strip()]
    streams = [str(item) for item in row.get("streams", []) if str(item).strip()]
    return {
        "group": str(row.get("site", "")).strip(),
        "entity_count": len(participants),
        "entities": participants,
        "stream_count": len(streams),
        "streams": streams,
        "file_count": int(row.get("file_count", 0) or 0),
        "total_bytes": int(row.get("total_bytes", 0) or 0),
        # Compatibility labels make the aliasing explicit for mixed readers.
        "site": str(row.get("site", "")).strip(),
        "participant_count": len(participants),
        "participants": participants,
    }


def passive_logical_labels(*, site: str = "", participant_id: str = "", stream: str = "") -> Dict[str, str]:
    labels: Dict[str, str] = {}
    if site:
        labels["group"] = site
        labels["site"] = site
    if participant_id:
        labels["entity_id"] = participant_id
        labels["participant_id"] = participant_id
    if stream:
        labels["stream"] = stream
    return labels


def passive_logical_coordinates(*, group: str = "", entity_id: str = "", stream: str = "") -> Dict[str, str]:
    coordinates: Dict[str, str] = {}
    if group:
        coordinates["group"] = group
    if entity_id:
        coordinates["entity_id"] = entity_id
    if stream:
        coordinates["stream"] = stream
    return coordinates


__all__ = [
    "GROUP_ENTITY_STREAM_LAYOUTS",
    "PASSIVE_DATA_DOMAIN",
    "PASSIVE_DATA_LAYOUTS",
    "PASSIVE_SOURCE_SNAPSHOT_PRESET",
    "SOURCE_SNAPSHOT_PRESETS",
    "SourceSnapshotPreset",
    "coverage_with_neutral_aliases",
    "passive_logical_coordinates",
    "passive_logical_labels",
    "resolve_source_snapshot_preset",
]
