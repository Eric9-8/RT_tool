from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.app.models import BlockDelta, LoadWorkspaceRequest
from backend.app.workspace import WorkspaceError, build_scene, export_aligned_workspace, load_workspace
from test_backend import build_gs3d_document, build_test_gpkg, create_workspace_fixture


class WorkspaceModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="gs3d-workspace-mode-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_workspace_keeps_mesh_layer(self) -> None:
        workspace_path = create_workspace_fixture(self.temp_dir)
        loaded = load_workspace(LoadWorkspaceRequest(workspacePath=str(workspace_path)))

        self.assertEqual(loaded.workspaceMode, "full_map")
        self.assertEqual(loaded.meshCount, 1)
        self.assertEqual(loaded.warnings, [])

    def test_semantic_only_workspace_loads_without_map_json(self) -> None:
        workspace_path = self.create_semantic_workspace()
        loaded = load_workspace(LoadWorkspaceRequest(workspacePath=str(workspace_path)))
        scene = build_scene(loaded.workspaceId, loaded.defaultVisibleLayers)

        self.assertEqual(loaded.workspaceMode, "semantic_only")
        self.assertEqual(loaded.meshCount, 0)
        self.assertEqual(scene.meshes, [])
        self.assertIn("GS3D/full.ply", loaded.blocks[0].assetUrl or "")
        self.assertTrue(any("using local GS3D/full.ply" in item for item in loaded.warnings))

    def test_semantic_only_workspace_exports_standard_gs3d(self) -> None:
        workspace_path = self.create_semantic_workspace()
        loaded = load_workspace(LoadWorkspaceRequest(workspacePath=str(workspace_path)))

        exported = export_aligned_workspace(loaded.workspaceId, {"0": BlockDelta(dz=1)})

        block = exported["blocks"]["0"]
        self.assertEqual(len(block["RT"]), 16)
        self.assertEqual(len(block["center"]), 3)
        self.assertEqual(block["center"], block["RT"][12:15])

    def test_semantic_only_workspace_rejects_missing_gs3d(self) -> None:
        workspace = self.temp_dir / "missing_gs3d"
        (workspace / "GeoPackage").mkdir(parents=True)
        build_test_gpkg(workspace / "GeoPackage" / "semantic_map.gpkg")

        with self.assertRaisesRegex(WorkspaceError, "gs3d.json"):
            load_workspace(LoadWorkspaceRequest(workspacePath=str(workspace)))

    def create_semantic_workspace(self) -> Path:
        workspace = self.temp_dir / "semantic_map"
        (workspace / "GeoPackage").mkdir(parents=True)
        (workspace / "GS3D").mkdir()
        (workspace / "GS3D" / "full.ply").write_text("ply\nformat ascii 1.0\nelement vertex 0\nend_header\n")
        document = build_gs3d_document()
        document["blocks"]["0"]["filename"] = "asset://maps/other_map/GS3D/full.ply"
        (workspace / "gs3d.json").write_text(json.dumps(document, indent=2))
        build_test_gpkg(workspace / "GeoPackage" / "semantic_map.gpkg")
        return workspace


if __name__ == "__main__":
    unittest.main()
