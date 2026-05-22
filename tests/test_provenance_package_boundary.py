from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


class ProvenancePackageBoundaryTests(unittest.TestCase):
    def test_provenance_package_import_contract(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/check_provenance_package_contract.py"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["violations"], [])

    def test_generic_provenance_kernel_runs_without_project_or_pipeline_imports(self) -> None:
        code = textwrap.dedent(
            r"""
            import json
            import sys
            import tempfile
            from pathlib import Path

            from mhm_core.provenance.manifests import (
                build_dataset_snapshot,
                document_reference_from_path,
                verify_manifest_bundle,
                write_dataset_manifest_bundle,
            )
            from mhm_core.provenance.operations import build_operation_event, load_operation_event, write_operation_event

            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                data_root = root / "data"
                data_root.mkdir()
                (data_root / "example.csv").write_text("id,value\nentity-1,10\n", encoding="utf-8")
                snapshot = build_dataset_snapshot(
                    data_root=data_root,
                    dataset_kind="example_dataset",
                    dataset_id="example-state",
                    title="Example state",
                    surface="example",
                    domain="demo",
                    stage="observed",
                    layout="flat_files_v1",
                    fingerprint_mode="content",
                )
                paths = write_dataset_manifest_bundle(
                    manifest_root=root / "manifest",
                    snapshot=snapshot,
                    history_event={
                        "event_type": "snapshot_example_state",
                        "generated_at": snapshot["generated_at"],
                        "dataset_id": snapshot["dataset_id"],
                    },
                )
                output_ref = document_reference_from_path(
                    str(paths["dataset_manifest"]),
                    role="output_state_manifest",
                    relation="produces",
                )
                operation = build_operation_event(
                    operation_kind="observe",
                    operation_name="snapshot-example",
                    title="Snapshot example state",
                    output_state_refs=[output_ref.to_dict()],
                )
                operation_path = write_operation_event(root / "manifest" / "operation_event.json", operation)
                loaded = sorted(
                    name
                    for name in sys.modules
                    if name.startswith("connect_summary") or name.startswith("mhm_core.pipeline")
                )
                verification = verify_manifest_bundle(root / "manifest")
                print(json.dumps({
                    "loaded": loaded,
                    "manifest_ok": verification["errors"] == [],
                    "operation_kind": load_operation_event(operation_path)["operation_kind"],
                }, sort_keys=True))
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["loaded"], [])
        self.assertTrue(payload["manifest_ok"])
        self.assertEqual(payload["operation_kind"], "observe")

    def test_document_reference_infers_type_for_unresolved_locator(self) -> None:
        from mhm_core.provenance.manifests import document_reference_from_path

        ref = document_reference_from_path(
            "s3://bucket/path/pipeline_spec_manifest.json",
            role="pipeline_spec_manifest",
        )

        self.assertIsNotNone(ref)
        payload = ref.to_dict()  # type: ignore[union-attr]
        self.assertEqual(payload["document_type"], "json")
        self.assertEqual(payload["locator"], "s3://bucket/path/pipeline_spec_manifest.json")

    def test_passive_provenance_addresses_emit_neutral_coordinates_with_legacy_aliases(self) -> None:
        from mhm_core.provenance.source import logical_address_for_source

        address = logical_address_for_source(
            "group-a/entity-1/sleep/part-000.csv.gz",
            logical_root={
                "surface": "run-output",
                "domain": "passive-data",
                "stage": "merged",
                "dataset_id": "run-1",
            },
            layout="site_participant_stream_v1",
        )
        payload = address.to_dict()

        self.assertEqual(payload["group"], "group-a")
        self.assertEqual(payload["entity_id"], "entity-1")
        self.assertEqual(payload["site"], "group-a")
        self.assertEqual(payload["participant_id"], "entity-1")
        self.assertEqual(payload["coordinates"]["group"], "group-a")
        self.assertEqual(payload["coordinates"]["entity_id"], "entity-1")

    def test_source_snapshot_defaults_are_explicit_preset(self) -> None:
        import tempfile

        from mhm_core.provenance.passive_data_layout import (
            PASSIVE_SOURCE_SNAPSHOT_PRESET,
            SourceSnapshotPreset,
        )
        from mhm_core.provenance.source import snapshot_source_state

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root / "source" / "group-a" / "entity-1" / "steps"
            source_root.mkdir(parents=True)
            (source_root / "part-000.csv").write_text("time,value\n2026-01-01,1\n", encoding="utf-8")

            passive = snapshot_source_state(
                source=str(root / "source"),
                manifest_root=root / "passive-manifest",
                source_id="source-passive",
            )["snapshot"]

            flat = snapshot_source_state(
                source=str(root / "source"),
                manifest_root=root / "flat-manifest",
                source_id="source-flat",
                preset=SourceSnapshotPreset(
                    name="flat-demo-v1",
                    surface="source",
                    domain="demo",
                    stage="observed",
                    layout="flat_files_v1",
                    fingerprint_mode="content_sha256",
                ),
            )["snapshot"]

        self.assertEqual(passive["layout"], PASSIVE_SOURCE_SNAPSHOT_PRESET.layout)
        self.assertEqual(passive["logical_root"]["domain"], PASSIVE_SOURCE_SNAPSHOT_PRESET.domain)
        self.assertEqual(passive["extra_metadata"]["source_snapshot_preset"], PASSIVE_SOURCE_SNAPSHOT_PRESET.name)
        self.assertEqual(flat["layout"], "flat_files_v1")
        self.assertEqual(flat["fingerprint_mode"], "content_sha256")
        self.assertIn("content_sha256", flat["artifacts"][0]["observed"])
        self.assertEqual(flat["logical_root"]["domain"], "demo")
        self.assertEqual(flat["logical_root"]["stage"], "observed")
        self.assertEqual(flat["extra_metadata"]["source_snapshot_preset"], "flat-demo-v1")

    def test_source_snapshot_rejects_ambiguous_content_fingerprint_mode(self) -> None:
        from mhm_core.provenance.passive_data_layout import SourceSnapshotPreset
        from mhm_core.provenance.source import snapshot_source_state

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root / "source"
            source_root.mkdir()
            (source_root / "example.csv").write_text("id,value\nentity-1,1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                snapshot_source_state(
                    source=str(source_root),
                    manifest_root=root / "manifest",
                    source_id="source-flat",
                    preset=SourceSnapshotPreset(
                        name="flat-demo-v1",
                        surface="source",
                        domain="demo",
                        stage="observed",
                        layout="flat_files_v1",
                        fingerprint_mode="content",
                    ),
                )


if __name__ == "__main__":
    unittest.main()
