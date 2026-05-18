"""Surface schema objects for path realization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping

from .hashing import sha256_json
from .model import PROVENANCE_SCHEMA_VERSION


def _sorted_dict(value: Mapping[str, Any] | None) -> Dict[str, Any]:
    if not value:
        return {}
    return {str(key): value[key] for key in sorted(value)}


@dataclass(frozen=True)
class SurfaceDefinition:
    """Declarative description of a realization surface."""

    surface_id: str
    surface_kind: str
    role: str
    locator_rules: Dict[str, Any] = field(default_factory=dict)
    allowed_node_classes: List[str] = field(default_factory=list)
    realization_modes: List[str] = field(default_factory=list)
    authority_level: str = ""
    supports_partial_realization: bool = False
    verification_policy: Dict[str, Any] = field(default_factory=dict)
    retention_policy: Dict[str, Any] = field(default_factory=dict)
    backend_capabilities: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = PROVENANCE_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "manifest_type": "surface_definition",
            "schema_version": self.schema_version,
            "surface_id": self.surface_id,
            "surface_kind": self.surface_kind,
            "role": self.role,
        }
        if self.locator_rules:
            payload["locator_rules"] = _sorted_dict(self.locator_rules)
        if self.allowed_node_classes:
            payload["allowed_node_classes"] = sorted(
                str(item) for item in self.allowed_node_classes if str(item).strip()
            )
        if self.realization_modes:
            payload["realization_modes"] = sorted(
                str(item) for item in self.realization_modes if str(item).strip()
            )
        if self.authority_level:
            payload["authority_level"] = self.authority_level
        payload["supports_partial_realization"] = bool(self.supports_partial_realization)
        if self.verification_policy:
            payload["verification_policy"] = _sorted_dict(self.verification_policy)
        if self.retention_policy:
            payload["retention_policy"] = _sorted_dict(self.retention_policy)
        if self.backend_capabilities:
            payload["backend_capabilities"] = _sorted_dict(self.backend_capabilities)
        return payload

    def surface_hash(self) -> str:
        return sha256_json(self.to_dict())


def surface_definition_from_dict(data: Mapping[str, Any]) -> SurfaceDefinition:
    return SurfaceDefinition(
        surface_id=str(data.get("surface_id", "")),
        surface_kind=str(data.get("surface_kind", "")),
        role=str(data.get("role", "")),
        locator_rules=dict(data.get("locator_rules", {}) or {}),
        allowed_node_classes=[
            str(item) for item in data.get("allowed_node_classes", []) if str(item).strip()
        ],
        realization_modes=[
            str(item) for item in data.get("realization_modes", []) if str(item).strip()
        ],
        authority_level=str(data.get("authority_level", "")),
        supports_partial_realization=bool(data.get("supports_partial_realization", False)),
        verification_policy=dict(data.get("verification_policy", {}) or {}),
        retention_policy=dict(data.get("retention_policy", {}) or {}),
        backend_capabilities=dict(data.get("backend_capabilities", {}) or {}),
        schema_version=str(data.get("schema_version", PROVENANCE_SCHEMA_VERSION)),
    )


__all__ = ["SurfaceDefinition", "surface_definition_from_dict"]
