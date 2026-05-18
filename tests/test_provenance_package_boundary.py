from __future__ import annotations

import json
import ast
import subprocess
import sys
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

    def test_connect_summary_provenance_paths_are_thin_compatibility_wrappers(self) -> None:
        from connect_summary.provenance.hashing import sha256_json as compat_sha256_json
        from connect_summary.provenance.manifests import build_dataset_snapshot as compat_snapshot
        from mhm_core.provenance.hashing import sha256_json
        from mhm_core.provenance.manifests import build_dataset_snapshot

        self.assertIs(compat_sha256_json, sha256_json)
        self.assertIs(compat_snapshot, build_dataset_snapshot)

    def test_moved_connect_summary_paths_do_not_define_business_logic(self) -> None:
        wrapper_paths = [
            Path("connect_summary/provenance") / f"{module_name}.py"
            for module_name in (
                "context_refs",
                "governance",
                "hashing",
                "knowledge",
                "manifests",
                "model",
                "operations",
                "path_model",
                "realization",
                "source",
                "source_events",
                "surfaces",
            )
        ]
        for path in wrapper_paths:
            with self.subTest(path=str(path)):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                logic_nodes = [
                    node
                    for node in ast.walk(tree)
                    if isinstance(
                        node,
                        (
                            ast.FunctionDef,
                            ast.AsyncFunctionDef,
                            ast.ClassDef,
                            ast.Assign,
                            ast.AnnAssign,
                            ast.AugAssign,
                        ),
                    )
                ]
                self.assertEqual(logic_nodes, [])


if __name__ == "__main__":
    unittest.main()
