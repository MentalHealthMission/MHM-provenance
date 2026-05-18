"""Logical provenance models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


PROVENANCE_SCHEMA_VERSION = "provenance-v1"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def file_mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class LogicalAddress:
    surface: str
    domain: str
    stage: str
    site: str = ""
    participant_id: str = ""
    stream: str = ""
    artifact: str = ""
    dataset_id: str = ""
    slice_name: str = ""
    interval_start: str = ""
    interval_end: str = ""
    labels: Dict[str, str] = field(default_factory=dict)

    @property
    def group(self) -> str:
        """Neutral alias for the passive-data `site` dimension."""
        return self.site

    @property
    def entity_id(self) -> str:
        """Neutral alias for the passive-data `participant_id` dimension."""
        return self.participant_id

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "surface": self.surface,
            "domain": self.domain,
            "stage": self.stage,
        }
        if self.site:
            payload["site"] = self.site
        if self.participant_id:
            payload["participant_id"] = self.participant_id
        if self.stream:
            payload["stream"] = self.stream
        if self.artifact:
            payload["artifact"] = self.artifact
        if self.dataset_id:
            payload["dataset_id"] = self.dataset_id
        if self.slice_name:
            payload["slice_name"] = self.slice_name
        if self.interval_start:
            payload["interval_start"] = self.interval_start
        if self.interval_end:
            payload["interval_end"] = self.interval_end
        if self.labels:
            payload["labels"] = dict(sorted(self.labels.items()))
        return payload

    def display(self) -> str:
        parts = [self.surface, self.domain, self.stage]
        if self.site:
            parts.append(self.site)
        if self.participant_id:
            parts.append(self.participant_id)
        if self.stream:
            parts.append(self.stream)
        if self.artifact:
            parts.append(self.artifact)
        return ":".join(parts)


@dataclass(frozen=True)
class PhysicalBinding:
    binding_type: str
    locator: str
    relative_locator: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, str]:
        payload = {
            "binding_type": self.binding_type,
            "locator": self.locator,
        }
        if self.relative_locator:
            payload["relative_locator"] = self.relative_locator
        if self.description:
            payload["description"] = self.description
        return payload


@dataclass(frozen=True)
class DocumentReference:
    role: str
    locator: str
    document_hash: str
    document_type: str = ""
    dataset_id: str = ""
    title: str = ""
    relation: str = ""

    def to_dict(self) -> dict[str, str]:
        payload = {
            "role": self.role,
            "locator": self.locator,
            "document_hash": self.document_hash,
        }
        if self.document_type:
            payload["document_type"] = self.document_type
        if self.dataset_id:
            payload["dataset_id"] = self.dataset_id
        if self.title:
            payload["title"] = self.title
        if self.relation:
            payload["relation"] = self.relation
        return payload


def normalize_iso_like(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if text.endswith("Z"):
        return text
    if "+" in text[10:] or text.endswith("00:00"):
        return text
    return f"{text}Z"
