from __future__ import annotations

import unittest

from connect_summary.provenance.path_model import (
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
from connect_summary.provenance.realization import (
    RealizationResult,
    RealizedBinding,
    realization_result_from_dict,
)
from connect_summary.provenance.surfaces import SurfaceDefinition, surface_definition_from_dict
from mhm_core.provenance.model import LogicalAddress


class ProvenanceSchemaModelTests(unittest.TestCase):
    def test_logical_address_keeps_passive_data_aliases_explicit(self) -> None:
        address = LogicalAddress(
            surface="study",
            domain="passive-data",
            stage="merged",
            site="Cardiff",
            participant_id="participant-1",
            stream="steps",
            artifact="steps.csv.gz",
        )

        self.assertEqual(address.group, "Cardiff")
        self.assertEqual(address.entity_id, "participant-1")
        self.assertEqual(
            address.to_dict(),
            {
                "surface": "study",
                "domain": "passive-data",
                "stage": "merged",
                "site": "Cardiff",
                "group": "Cardiff",
                "participant_id": "participant-1",
                "entity_id": "participant-1",
                "stream": "steps",
                "artifact": "steps.csv.gz",
            },
        )

    def test_concrete_path_round_trip_and_hash_stability(self) -> None:
        path = ConcretePath(
            input_nodes=[
                PathNodeReference(
                    locator="/tmp/example/dataset_manifest.json",
                    node_hash="node-1",
                    dataset_id="study-passive-data",
                )
            ],
            operations=[
                PathOperation(
                    operation_type="apply_exclusions",
                    parameters={"policy": "strict"},
                    linked_nodes=[
                        PathNodeReference(
                            locator="/tmp/example/extract_plan.csv",
                            document_hash="doc-1",
                            node_kind="knowledge_snapshot",
                        )
                    ],
                )
            ],
            selection=PathSelection(streams=["steps", "heart_rate"], sites=["Cardiff"]),
            resolved_state=ResolvedPathState(
                state_mode="sequential_prefix",
                payload={"frontier_document": "/tmp/example/frontier.json"},
            ),
        )

        round_tripped = concrete_path_from_dict(path.to_dict())

        self.assertEqual(path.to_dict(), round_tripped.to_dict())
        self.assertEqual(path.path_hash(), round_tripped.path_hash())

    def test_template_path_supports_variable_inputs(self) -> None:
        template = TemplatePath(
            input_nodes=[
                PathVariableReference(
                    name="start_node",
                    variable_kind="start_node",
                    selector={"surface": "rds_study", "mode": "latest_valid"},
                )
            ],
            operations=[PathOperation(operation_type="merge")],
        )

        round_tripped = template_path_from_dict(template.to_dict())

        self.assertEqual(template.to_dict(), round_tripped.to_dict())
        self.assertEqual(template.path_hash(), round_tripped.path_hash())

    def test_surface_definition_round_trip_and_hash_stability(self) -> None:
        surface = SurfaceDefinition(
            surface_id="rds_study",
            surface_kind="rds_projection",
            role="persistent_study_projection",
            locator_rules={"root_locator": "/Volumes/CONNECT_study_data"},
            allowed_node_classes=["canonical_dataset", "study_slice"],
            realization_modes=["projection", "bind_existing"],
            authority_level="researcher_preferred",
            supports_partial_realization=True,
            verification_policy={"mode": "manifest_bundle"},
            retention_policy={"mode": "persistent"},
            backend_capabilities={"can_compute": False},
        )

        round_tripped = surface_definition_from_dict(surface.to_dict())

        self.assertEqual(surface.to_dict(), round_tripped.to_dict())
        self.assertEqual(surface.surface_hash(), round_tripped.surface_hash())

    def test_realization_result_round_trip_and_hash_stability(self) -> None:
        requested = ConcretePath(
            input_nodes=[PathNodeReference(locator="/tmp/input.json", node_hash="n0")],
            operations=[PathOperation(operation_type="merge")],
        )
        residual = ConcretePath(
            input_nodes=[PathNodeReference(locator="/tmp/intermediate.json", node_hash="n1")],
            operations=[PathOperation(operation_type="redact")],
        )
        result = RealizationResult(
            status="partially_manifested",
            requested_path=requested,
            residual_path=residual,
            resolved_bindings=[
                RealizedBinding(
                    surface_id="rds_study",
                    binding_type="posix_path",
                    locator="/Volumes/CONNECT_study_data/data/study/passive-data/merged-data",
                    verification_status="valid",
                    node_hash="n0",
                )
            ],
            messages=["reused canonical study node from RDS"],
            metadata={"executor": "test"},
        )

        round_tripped = realization_result_from_dict(result.to_dict())

        self.assertEqual(result.to_dict(), round_tripped.to_dict())
        self.assertEqual(result.result_hash(), round_tripped.result_hash())


if __name__ == "__main__":
    unittest.main()
