from __future__ import annotations

import asyncio
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import httpx
from pyproj import CRS, Transformer

from backend.app.main import app
from backend.app.models import BlockDelta, LoadWorkspaceRequest
from backend.app.projection import ecef_to_enu_matrix, geocent_pose_to_map, map_pose_to_geocent
from backend.app.service import Gs3dValidationError, export_document, inspect_document
from backend.app.transform import apply_block_delta, flat_rt
from backend.app.workspace import WorkspaceError, build_scene, export_aligned_workspace, load_workspace
from gpkg_fixture import build_test_gpkg as build_fixture_gpkg

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "shared" / "testdata"
PROJECTION = (
    "+proj=tmerc +lat_0=32.161712444 +lon_0=118.692341598 +k=1 "
    "+x_0=0 +y_0=0 +ellps=WGS84 +units=m +no_defs +type=crs"
)

for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(key, None)
os.environ["NO_PROXY"] = "testserver,127.0.0.1,localhost"

BASE_DOCUMENT = {
    "version": "1.0",
    "depth_test_offset": 3.0,
    "blocks": {
        "0": {
            "RT": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 10, 20, 30, 1],
            "center": [10, 20, 30],
            "scale": 1.0,
            "filename": "asset://demo/a.ply",
            "proj-string": "+proj=geocent",
        },
        "1": {
            "RT": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -5, 2, 8, 1],
            "center": [-5, 2, 8],
            "scale": 0.5,
        },
    },
}


class BackendBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="gs3d-align-test-"))
        self.workspace_path = create_workspace_fixture(self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_inspect_document_lists_all_blocks(self) -> None:
        result = inspect_document(BASE_DOCUMENT)
        self.assertEqual(result.blockCount, 2)
        self.assertEqual([block.blockId for block in result.blocks], ["0", "1"])

    def test_inspect_rejects_invalid_rt_length(self) -> None:
        invalid = {"blocks": {"0": {"RT": [1, 2], "center": [1, 2, 3]}}}
        with self.assertRaises(Gs3dValidationError):
            inspect_document(invalid)

    def test_export_updates_only_selected_block(self) -> None:
        delta = BlockDelta(yaw=90, dx=1, dy=2, dz=3)
        exported = export_document(BASE_DOCUMENT, {"0": delta})
        self.assertEqual(exported["blocks"]["1"], BASE_DOCUMENT["blocks"]["1"])
        self.assertEqual(exported["blocks"]["0"]["center"], [12.0, 19.0, 33.0])

    def test_export_rejects_unknown_block(self) -> None:
        with self.assertRaises(Gs3dValidationError):
            export_document(BASE_DOCUMENT, {"99": BlockDelta()})

    def test_shared_cases_match_expected_numbers(self) -> None:
        payload = json.loads((FIXTURE_DIR / "gs3d_transform_cases.json").read_text())
        for case in payload["cases"]:
            rt, center = apply_block_delta(case["rt"], BlockDelta(**case["delta"]))
            self.assertSequenceAlmostEqual(flat_rt(rt), case["expectedRt"])
            self.assertSequenceAlmostEqual(center.tolist(), case["expectedCenter"])

    def test_workspace_load_discovers_projection_and_initial_map_pose(self) -> None:
        response = load_workspace(LoadWorkspaceRequest(workspacePath=str(self.workspace_path)))
        self.assertEqual(response.meshCount, 1)
        self.assertEqual(response.defaultVisibleLayers, ["RoadReferenceLines", "RoadMarks"])
        self.assertTrue(any(layer.name == "StopLines" and layer.geometryType == "Geometry" for layer in response.layerSummaries))
        self.assertTrue(response.trafficSummary.exists)
        self.assertEqual(response.trafficSummary.routeCount, 1)
        self.assertEqual(response.trafficSummary.referenceLayer, "RoadReferenceLines")
        self.assertEqual(response.trafficSummary.referenceStatus, "fallback")
        self.assertEqual(response.blocks[0].blockId, "0")
        self.assertSequenceAlmostEqual(response.blocks[0].mapPose.center, [0.0, 0.0, 5.0])
        self.assertSequenceAlmostEqual(response.blocks[0].mapPose.rtMatrix[0][:3], [1.0, 0.0, 0.0])
        self.assertSequenceAlmostEqual(response.blocks[0].mapPose.rtMatrix[1][:3], [0.0, 1.0, 0.0])
        self.assertSequenceAlmostEqual(response.blocks[0].mapPose.rtMatrix[2][:3], [0.0, 0.0, 1.0])

    def test_backup_pose_maps_to_identity_orientation(self) -> None:
        rt = json.loads((FIXTURE_DIR / "gs3d_transform_cases.json").read_text())["cases"][1]["rt"]
        map_rt, _ = geocent_pose_to_map(rt, PROJECTION)

        self.assertSequenceAlmostEqual(map_rt[3, :3].tolist(), [0.0, 0.0, 32.1722])
        self.assertSequenceAlmostEqual(map_rt[0, :3].tolist(), [1.0, 0.0, 0.0])
        self.assertSequenceAlmostEqual(map_rt[1, :3].tolist(), [0.0, 1.0, 0.0])
        self.assertSequenceAlmostEqual(map_rt[2, :3].tolist(), [0.0, 0.0, 1.0])

    def test_projection_roundtrips_rotation_and_center(self) -> None:
        source_rt = json.loads((FIXTURE_DIR / "gs3d_transform_cases.json").read_text())["cases"][1]["rt"]
        map_rt, _ = geocent_pose_to_map(source_rt, PROJECTION)
        geocent_rt, _ = map_pose_to_geocent(flat_rt(map_rt), PROJECTION)

        self.assertSequenceAlmostEqual(flat_rt(geocent_rt), source_rt)

    def test_workspace_scene_returns_mesh_and_semantic_layers(self) -> None:
        workspace = load_workspace(LoadWorkspaceRequest(workspacePath=str(self.workspace_path)))
        scene = build_scene(workspace.workspaceId, workspace.defaultVisibleLayers)
        self.assertEqual(len(scene.meshes), 1)
        self.assertEqual([layer.name for layer in scene.layers], ["RoadReferenceLines", "RoadMarks"])
        self.assertEqual(len(scene.trafficRoutes), 1)
        self.assertEqual(scene.trafficRoutes[0].name, "Spline_0_0")
        self.assertEqual(scene.trafficRoutes[0].coordinates[0], [0.0, 0.0, 5.0])

    def test_workspace_load_rejects_invalid_traffic_data(self) -> None:
        (self.workspace_path / "traffic_data.json").write_text(json.dumps({"Splines": [{"Name": "bad"}]}))

        with self.assertRaisesRegex(ValueError, "ControlPoints"):
            load_workspace(LoadWorkspaceRequest(workspacePath=str(self.workspace_path)))

    def test_export_aligned_workspace_roundtrips_to_map_coordinates(self) -> None:
        workspace = load_workspace(LoadWorkspaceRequest(workspacePath=str(self.workspace_path)))
        exported = export_aligned_workspace(workspace.workspaceId, {"0": BlockDelta(dx=2, dy=3, dz=1)})
        aligned_rt, _ = geocent_pose_to_map(exported["blocks"]["0"]["RT"], PROJECTION)
        self.assertSequenceAlmostEqual(aligned_rt[3, :3].tolist(), [2.0, 3.0, 6.0])

    def test_workspace_load_rejects_missing_gpkg(self) -> None:
        broken_workspace = self.temp_dir / "broken"
        broken_workspace.mkdir()
        (broken_workspace / "GeoPackage").mkdir()
        with self.assertRaises(WorkspaceError):
            load_workspace(LoadWorkspaceRequest(workspacePath=str(broken_workspace)))

    def test_workspace_endpoints_flow(self) -> None:
        payload = asyncio.run(self._post_workspace_load(str(self.workspace_path)))
        self.assertEqual(payload.status_code, 200)
        workspace_id = payload.json()["workspaceId"]

        scene = asyncio.run(self._post_workspace_scene(workspace_id, ["RoadReferenceLines"]))
        self.assertEqual(scene.status_code, 200)
        self.assertEqual(scene.json()["layers"][0]["name"], "RoadReferenceLines")

        exported = asyncio.run(self._post_export_aligned(workspace_id))
        self.assertEqual(exported.status_code, 200)
        self.assertIn("attachment", exported.headers["content-disposition"])

    def assertSequenceAlmostEqual(self, left: list[float], right: list[float]) -> None:
        self.assertEqual(len(left), len(right))
        for lhs, rhs in zip(left, right):
            self.assertAlmostEqual(lhs, rhs, places=6)

    async def _post_export_aligned(self, workspace_id: str) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                "/api/gs3d/export-aligned",
                json={"workspaceId": workspace_id, "blockDeltas": {"0": {"dx": 2, "dy": 3, "dz": 1}}},
            )

    async def _post_workspace_load(self, workspace_path: str) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post("/api/workspace/load", json={"workspacePath": workspace_path})

    async def _post_workspace_scene(self, workspace_id: str, layers: list[str]) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post("/api/workspace/scene", json={"workspaceId": workspace_id, "layers": layers})


def create_workspace_fixture(temp_dir: Path) -> Path:
    workspace = temp_dir / "demo_map"
    (workspace / "GeoPackage").mkdir(parents=True)
    (workspace / "Meshes").mkdir()
    (workspace / "GS3D").mkdir()

    (workspace / "Meshes" / "Road_0.gltf").write_text('{"asset":{"version":"2.0"}}')
    (workspace / "Meshes" / "Road_0.bin").write_bytes(b"mesh")
    (workspace / "GS3D" / "full.ply").write_text("ply\nformat ascii 1.0\nelement vertex 0\nend_header\n")
    (workspace / "map.json").write_text(json.dumps(build_map_json(workspace.name), indent=2))
    (workspace / "traffic_data.json").write_text(json.dumps(build_traffic_data(), indent=2))

    gs3d_document = build_gs3d_document()
    (workspace / "gs3d.json").write_text(json.dumps(gs3d_document, indent=2))

    gpkg_path = workspace / "GeoPackage" / "demo_map.gpkg"
    build_fixture_gpkg(gpkg_path, PROJECTION)
    return workspace


def build_map_json(map_name: str) -> dict:
    return {
        "actors": [
            [
                {"command_type": "Initial", "parameters": {"name": "Road_0"}},
                {
                    "command_type": "AddMeshNode",
                    "mesh_asset": f"asset://maps/{map_name}/Meshes/Road_0.gltf",
                    "semantic_label": "Road",
                },
                {
                    "command_type": "AddAttributes",
                    "attributes": {"bounds": {"min": [0.0, 0.0, 0.0], "max": [10.0, 5.0, 0.0]}},
                },
            ]
        ]
    }


def build_gs3d_document() -> dict:
    to_geocent = Transformer.from_crs(CRS.from_epsg(4979), CRS.from_proj4("+proj=geocent +datum=WGS84 +units=m +no_defs"), always_xy=True)
    lon, lat, height = 118.692341598, 32.161712444, 5.0
    x, y, z = to_geocent.transform(lon, lat, height)
    basis = ecef_to_enu_matrix(lat, lon)
    rotation = basis
    rt = [
        rotation[0, 0], rotation[0, 1], rotation[0, 2], 0.0,
        rotation[1, 0], rotation[1, 1], rotation[1, 2], 0.0,
        rotation[2, 0], rotation[2, 1], rotation[2, 2], 0.0,
        x, y, z, 1.0,
    ]
    return {
        "version": "1.0",
        "depth_test_offset": 3.0,
        "blocks": {
            "0": {
                "RT": rt,
                "center": [x, y, z],
                "scale": 1.0,
                "filename": "asset://maps/demo_map/GS3D/full.ply",
                "proj-string": "+proj=geocent",
            }
        },
    }


def build_traffic_data() -> dict:
    return {
        "creation_date": "2026_06_05",
        "version": "1.0",
        "MeasurementUnit": "Meter",
        "RotationUnit": "Degree",
        "Splines": [
            {
                "LaneId": 0,
                "Name": "Spline_0_0",
                "Drivable": True,
                "SplineType": "TrafficSpline",
                "Type": "GeneralPointList",
                "TurnSignal": "None",
                "NextSplines": [{"Name": "Spline_1_1", "Type": "Primary"}],
                "PrevSplines": [],
                "ControlPoints": [
                    {"X": 0.0, "Y": 0.0, "Z": 5.0},
                    {"X": 10.0, "Y": 5.0, "Z": 5.0},
                ],
            }
        ],
        "TrafficLights": [],
    }


def build_test_gpkg(path: Path) -> None:
    build_fixture_gpkg(path, PROJECTION)


if __name__ == "__main__":
    unittest.main()
