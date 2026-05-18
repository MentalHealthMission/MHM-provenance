"""Path-oriented provenance schema objects.

These models are additive Milestone 1 schema objects only.
They define path semantics without introducing execution behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Sequence

from .hashing import sha256_json
from .model import PROVENANCE_SCHEMA_VERSION


def _sorted_dict(value: Mapping[str, Any] | None) -> Dict[str, Any]:
    if not value:
        return {}
    return {str(key): value[key] for key in sorted(value)}


@dataclass(frozen=True)
class PathNodeReference:
    """Reference to a concrete manifest-backed node."""

    locator: str
    node_hash: str = ""
    document_hash: str = ""
    node_kind: str = ""
    dataset_id: str = ""
    title: str = ""

    def to_dict(self) -> Dict[str, str]:
        payload: Dict[str, str] = {"locator": self.locator}
        if self.node_hash:
            payload["node_hash"] = self.node_hash
        if self.document_hash:
            payload["document_hash"] = self.document_hash
        if self.node_kind:
            payload["node_kind"] = self.node_kind
        if self.dataset_id:
            payload["dataset_id"] = self.dataset_id
        if self.title:
            payload["title"] = self.title
        return payload


@dataclass(frozen=True)
class PathVariableReference:
    """Variable placeholder used by template paths."""

    name: str
    variable_kind: str
    selector: Dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "name": self.name,
            "variable_kind": self.variable_kind,
        }
        if self.selector:
            payload["selector"] = _sorted_dict(self.selector)
        if self.description:
            payload["description"] = self.description
        return payload


@dataclass(frozen=True)
class PathOperation:
    """Semantic, data-changing operation on a path."""

    operation_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    linked_nodes: List[PathNodeReference] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"operation_type": self.operation_type}
        if self.parameters:
            payload["parameters"] = _sorted_dict(self.parameters)
        if self.linked_nodes:
            payload["linked_nodes"] = [node.to_dict() for node in self.linked_nodes]
        if self.description:
            payload["description"] = self.description
        return payload


@dataclass(frozen=True)
class PathSelection:
    """Optional semantic subset selection."""

    sites: List[str] = field(default_factory=list)
    participants: List[str] = field(default_factory=list)
    streams: List[str] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)
    selector_mode: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if self.sites:
            payload["sites"] = sorted(str(item) for item in self.sites if str(item).strip())
        if self.participants:
            payload["participants"] = sorted(
                str(item) for item in self.participants if str(item).strip()
            )
        if self.streams:
            payload["streams"] = sorted(str(item) for item in self.streams if str(item).strip())
        if self.labels:
            payload["labels"] = {str(key): self.labels[key] for key in sorted(self.labels)}
        if self.selector_mode:
            payload["selector_mode"] = self.selector_mode
        return payload


@dataclass(frozen=True)
class ResolvedPathState:
    """Additional semantic state required to replay a concrete path."""

    state_mode: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    linked_nodes: List[PathNodeReference] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if self.state_mode:
            payload["state_mode"] = self.state_mode
        if self.payload:
            payload["payload"] = _sorted_dict(self.payload)
        if self.linked_nodes:
            payload["linked_nodes"] = [node.to_dict() for node in self.linked_nodes]
        return payload


@dataclass(frozen=True)
class ConcretePath:
    """Fully resolved semantic path between concrete nodes."""

    input_nodes: List[PathNodeReference]
    operations: List[PathOperation]
    selection: PathSelection = field(default_factory=PathSelection)
    resolved_state: ResolvedPathState = field(default_factory=ResolvedPathState)
    schema_version: str = PROVENANCE_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest_type": "concrete_path",
            "schema_version": self.schema_version,
            "input_nodes": [node.to_dict() for node in self.input_nodes],
            "operations": [operation.to_dict() for operation in self.operations],
            "selection": self.selection.to_dict(),
            "resolved_state": self.resolved_state.to_dict(),
        }

    def path_hash(self) -> str:
        return sha256_json(self.to_dict())


@dataclass(frozen=True)
class TemplatePath:
    """Path schema that may contain unresolved node variables."""

    input_nodes: List[PathNodeReference | PathVariableReference]
    operations: List[PathOperation]
    selection: PathSelection = field(default_factory=PathSelection)
    resolved_state: ResolvedPathState = field(default_factory=ResolvedPathState)
    schema_version: str = PROVENANCE_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest_type": "template_path",
            "schema_version": self.schema_version,
            "input_nodes": [
                _path_input_to_dict(item)
                for item in self.input_nodes
            ],
            "operations": [operation.to_dict() for operation in self.operations],
            "selection": self.selection.to_dict(),
            "resolved_state": self.resolved_state.to_dict(),
        }

    def path_hash(self) -> str:
        return sha256_json(self.to_dict())


def _path_input_to_dict(value: PathNodeReference | PathVariableReference) -> Dict[str, Any]:
    if isinstance(value, PathNodeReference):
        payload = value.to_dict()
        payload["reference_type"] = "concrete"
        return payload
    payload = value.to_dict()
    payload["reference_type"] = "variable"
    return payload


def concrete_path_from_dict(data: Mapping[str, Any]) -> ConcretePath:
    return ConcretePath(
        input_nodes=[
            PathNodeReference(
                locator=str(item.get("locator", "")),
                node_hash=str(item.get("node_hash", "")),
                document_hash=str(item.get("document_hash", "")),
                node_kind=str(item.get("node_kind", "")),
                dataset_id=str(item.get("dataset_id", "")),
                title=str(item.get("title", "")),
            )
            for item in data.get("input_nodes", [])
            if isinstance(item, Mapping)
        ],
        operations=_operations_from_items(data.get("operations", [])),
        selection=_selection_from_mapping(data.get("selection", {})),
        resolved_state=_resolved_state_from_mapping(data.get("resolved_state", {})),
        schema_version=str(data.get("schema_version", PROVENANCE_SCHEMA_VERSION)),
    )


def template_path_from_dict(data: Mapping[str, Any]) -> TemplatePath:
    input_nodes: List[PathNodeReference | PathVariableReference] = []
    for item in data.get("input_nodes", []):
        if not isinstance(item, Mapping):
            continue
        ref_type = str(item.get("reference_type", "concrete")).strip().lower()
        if ref_type == "variable":
            input_nodes.append(
                PathVariableReference(
                    name=str(item.get("name", "")),
                    variable_kind=str(item.get("variable_kind", "")),
                    selector=dict(item.get("selector", {}) or {}),
                    description=str(item.get("description", "")),
                )
            )
        else:
            input_nodes.append(
                PathNodeReference(
                    locator=str(item.get("locator", "")),
                    node_hash=str(item.get("node_hash", "")),
                    document_hash=str(item.get("document_hash", "")),
                    node_kind=str(item.get("node_kind", "")),
                    dataset_id=str(item.get("dataset_id", "")),
                    title=str(item.get("title", "")),
                )
            )
    return TemplatePath(
        input_nodes=input_nodes,
        operations=_operations_from_items(data.get("operations", [])),
        selection=_selection_from_mapping(data.get("selection", {})),
        resolved_state=_resolved_state_from_mapping(data.get("resolved_state", {})),
        schema_version=str(data.get("schema_version", PROVENANCE_SCHEMA_VERSION)),
    )


def _operations_from_items(items: Sequence[object]) -> List[PathOperation]:
    operations: List[PathOperation] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        linked_nodes = []
        for linked in item.get("linked_nodes", []):
            if not isinstance(linked, Mapping):
                continue
            linked_nodes.append(
                PathNodeReference(
                    locator=str(linked.get("locator", "")),
                    node_hash=str(linked.get("node_hash", "")),
                    document_hash=str(linked.get("document_hash", "")),
                    node_kind=str(linked.get("node_kind", "")),
                    dataset_id=str(linked.get("dataset_id", "")),
                    title=str(linked.get("title", "")),
                )
            )
        operations.append(
            PathOperation(
                operation_type=str(item.get("operation_type", "")),
                parameters=dict(item.get("parameters", {}) or {}),
                linked_nodes=linked_nodes,
                description=str(item.get("description", "")),
            )
        )
    return operations


def _selection_from_mapping(data: object) -> PathSelection:
    if not isinstance(data, Mapping):
        return PathSelection()
    return PathSelection(
        sites=[str(item) for item in data.get("sites", []) if str(item).strip()],
        participants=[str(item) for item in data.get("participants", []) if str(item).strip()],
        streams=[str(item) for item in data.get("streams", []) if str(item).strip()],
        labels={str(key): str(value) for key, value in dict(data.get("labels", {}) or {}).items()},
        selector_mode=str(data.get("selector_mode", "")),
    )


def _resolved_state_from_mapping(data: object) -> ResolvedPathState:
    if not isinstance(data, Mapping):
        return ResolvedPathState()
    linked_nodes = []
    for item in data.get("linked_nodes", []):
        if not isinstance(item, Mapping):
            continue
        linked_nodes.append(
            PathNodeReference(
                locator=str(item.get("locator", "")),
                node_hash=str(item.get("node_hash", "")),
                document_hash=str(item.get("document_hash", "")),
                node_kind=str(item.get("node_kind", "")),
                dataset_id=str(item.get("dataset_id", "")),
                title=str(item.get("title", "")),
            )
        )
    return ResolvedPathState(
        state_mode=str(data.get("state_mode", "")),
        payload=dict(data.get("payload", {}) or {}),
        linked_nodes=linked_nodes,
    )


__all__ = [
    "ConcretePath",
    "PathNodeReference",
    "PathOperation",
    "PathSelection",
    "PathVariableReference",
    "ResolvedPathState",
    "TemplatePath",
    "concrete_path_from_dict",
    "template_path_from_dict",
]
