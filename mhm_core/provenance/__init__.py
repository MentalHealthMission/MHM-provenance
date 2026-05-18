"""Reusable MHM provenance kernel."""

from .hashing import add_document_hash, aggregate_hash, canonical_json_bytes, sha256_bytes, sha256_file, sha256_json
from .manifests import (
    build_artifact_record,
    build_dataset_snapshot,
    build_dataset_snapshot_from_inventory,
    dataset_state_summary,
    document_reference_from_path,
    show_lineage,
    verify_manifest_bundle,
    write_dataset_manifest_bundle,
)
from .model import (
    DocumentReference,
    LogicalAddress,
    PhysicalBinding,
    PROVENANCE_SCHEMA_VERSION,
    file_mtime_iso,
    utc_now_iso,
)
from .operations import build_operation_event, load_operation_event, write_operation_event
from .path_model import (
    ConcretePath,
    PathNodeReference,
    PathOperation,
    PathSelection,
    PathVariableReference,
    ResolvedPathState,
    TemplatePath,
    concrete_path_from_dict,
    template_path_from_dict,
)
from .realization import RealizationResult, RealizedBinding, realization_result_from_dict
from .source import snapshot_local_source, snapshot_source_state
from .source_events import create_source_availability_event
from .surfaces import SurfaceDefinition, surface_definition_from_dict

__all__ = [
    "ConcretePath",
    "DocumentReference",
    "LogicalAddress",
    "PROVENANCE_SCHEMA_VERSION",
    "PathNodeReference",
    "PathOperation",
    "PathSelection",
    "PathVariableReference",
    "PhysicalBinding",
    "RealizationResult",
    "RealizedBinding",
    "ResolvedPathState",
    "SurfaceDefinition",
    "TemplatePath",
    "add_document_hash",
    "aggregate_hash",
    "build_artifact_record",
    "build_dataset_snapshot",
    "build_dataset_snapshot_from_inventory",
    "build_operation_event",
    "canonical_json_bytes",
    "concrete_path_from_dict",
    "create_source_availability_event",
    "dataset_state_summary",
    "document_reference_from_path",
    "file_mtime_iso",
    "load_operation_event",
    "realization_result_from_dict",
    "sha256_bytes",
    "sha256_file",
    "sha256_json",
    "show_lineage",
    "snapshot_local_source",
    "snapshot_source_state",
    "surface_definition_from_dict",
    "template_path_from_dict",
    "utc_now_iso",
    "verify_manifest_bundle",
    "write_dataset_manifest_bundle",
    "write_operation_event",
]
