"""Realization result schema objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping

from .hashing import sha256_json
from .model import PROVENANCE_SCHEMA_VERSION
from .path_model import ConcretePath, concrete_path_from_dict


def _sorted_dict(value: Mapping[str, Any] | None) -> Dict[str, Any]:
    if not value:
        return {}
    return {str(key): value[key] for key in sorted(value)}


@dataclass(frozen=True)
class RealizedBinding:
    """Binding that satisfies part or all of a path on a surface."""

    surface_id: str
    binding_type: str
    locator: str
    verification_status: str = ""
    node_hash: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, str]:
        payload = {
            "surface_id": self.surface_id,
            "binding_type": self.binding_type,
            "locator": self.locator,
        }
        if self.verification_status:
            payload["verification_status"] = self.verification_status
        if self.node_hash:
            payload["node_hash"] = self.node_hash
        if self.description:
            payload["description"] = self.description
        return payload


@dataclass(frozen=True)
class RealizationResult:
    """Execution/result view for realizing a concrete path."""

    status: str
    requested_path: ConcretePath
    residual_path: ConcretePath | None = None
    resolved_bindings: List[RealizedBinding] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = PROVENANCE_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "manifest_type": "realization_result",
            "schema_version": self.schema_version,
            "status": self.status,
            "requested_path": self.requested_path.to_dict(),
        }
        if self.residual_path is not None:
            payload["residual_path"] = self.residual_path.to_dict()
        if self.resolved_bindings:
            payload["resolved_bindings"] = [item.to_dict() for item in self.resolved_bindings]
        if self.messages:
            payload["messages"] = [str(item) for item in self.messages if str(item).strip()]
        if self.metadata:
            payload["metadata"] = _sorted_dict(self.metadata)
        return payload

    def result_hash(self) -> str:
        return sha256_json(self.to_dict())


def realization_result_from_dict(data: Mapping[str, Any]) -> RealizationResult:
    requested_path = concrete_path_from_dict(
        data.get("requested_path", {}) if isinstance(data.get("requested_path"), Mapping) else {}
    )
    residual_raw = data.get("residual_path", {})
    residual_path = None
    if isinstance(residual_raw, Mapping) and residual_raw:
        residual_path = concrete_path_from_dict(residual_raw)
    resolved_bindings = []
    for item in data.get("resolved_bindings", []):
        if not isinstance(item, Mapping):
            continue
        resolved_bindings.append(
            RealizedBinding(
                surface_id=str(item.get("surface_id", "")),
                binding_type=str(item.get("binding_type", "")),
                locator=str(item.get("locator", "")),
                verification_status=str(item.get("verification_status", "")),
                node_hash=str(item.get("node_hash", "")),
                description=str(item.get("description", "")),
            )
        )
    return RealizationResult(
        status=str(data.get("status", "")),
        requested_path=requested_path,
        residual_path=residual_path,
        resolved_bindings=resolved_bindings,
        messages=[str(item) for item in data.get("messages", []) if str(item).strip()],
        metadata=dict(data.get("metadata", {}) or {}),
        schema_version=str(data.get("schema_version", PROVENANCE_SCHEMA_VERSION)),
    )


__all__ = [
    "RealizationResult",
    "RealizedBinding",
    "realization_result_from_dict",
]
