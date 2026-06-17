from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from backend.app.gpkg import load_layers, projection_string_from_map_info, summarize_layers
from backend.app.map_mesh import parse_meshes, relative_asset_path
from backend.app.models import (
    BlockDelta,
    GsAlignmentView,
    Gs3dInspectResponse,
    LoadWorkspaceRequest,
    MapLayerSummary,
    PoseView,
    TrafficDataSummary,
    TrafficRouteView,
    WorkspaceMode,
    WorkspaceLoadResponse,
    WorkspaceSceneResponse,
)
from backend.app.projection import geocent_pose_to_map, map_pose_to_geocent
from backend.app.service import inspect_document, parse_json_bytes
from backend.app.traffic import load_traffic_data
from backend.app.transform import apply_block_delta, flat_rt, matrix_to_list


class WorkspaceError(ValueError):
    pass


@dataclass
class WorkspaceContext:
    workspace_id: str
    root_path: Path
    map_name: str
    projection_string: str
    gs3d_document: dict
    gs3d_summary: Gs3dInspectResponse
    blocks: list[GsAlignmentView]
    layer_summaries: list[MapLayerSummary]
    default_visible_layers: list[str]
    meshes: list[MapMeshView]
    gpkg_path: Path
    workspace_mode: WorkspaceMode
    warnings: list[str]
    traffic_summary: TrafficDataSummary
    traffic_routes: list[TrafficRouteView]


WORKSPACES: dict[str, WorkspaceContext] = {}


def load_workspace(request: LoadWorkspaceRequest) -> WorkspaceLoadResponse:
    root_path = _resolve_workspace_path(request.workspacePath)
    workspace_id = uuid.uuid4().hex
    map_name = root_path.name
    gpkg_path = _find_single_file(root_path / "GeoPackage", ".gpkg", "GeoPackage")
    gs3d_path = root_path / "gs3d.json"
    map_json_path = root_path / "map.json"
    workspace_mode: WorkspaceMode = "full_map" if map_json_path.is_file() else "semantic_only"
    warnings: list[str] = []

    if not gs3d_path.is_file():
        raise WorkspaceError("Workspace is missing gs3d.json.")
    if workspace_mode == "semantic_only":
        warnings.append("map.json not found; loaded semantic-only workspace without mesh layer.")

    projection_string = projection_string_from_map_info(gpkg_path)
    layer_summaries, default_visible_layers = summarize_layers(gpkg_path)
    traffic_summary, traffic_routes = load_traffic_data(root_path, layer_summaries)
    gs3d_document = parse_json_bytes(gs3d_path.read_bytes())
    gs3d_summary = inspect_document(gs3d_document)
    blocks, asset_warnings = _build_alignment_blocks(
        gs3d_document, workspace_id, map_name, projection_string, root_path
    )
    warnings.extend(asset_warnings)
    meshes = parse_meshes(map_json_path, workspace_id, map_name) if workspace_mode == "full_map" else []

    context = WorkspaceContext(
        workspace_id=workspace_id,
        root_path=root_path,
        map_name=map_name,
        projection_string=projection_string,
        gs3d_document=gs3d_document,
        gs3d_summary=gs3d_summary,
        blocks=blocks,
        layer_summaries=layer_summaries,
        default_visible_layers=default_visible_layers,
        meshes=meshes,
        gpkg_path=gpkg_path,
        workspace_mode=workspace_mode,
        warnings=warnings,
        traffic_summary=traffic_summary,
        traffic_routes=traffic_routes,
    )
    WORKSPACES[workspace_id] = context
    return WorkspaceLoadResponse(
        workspaceId=workspace_id,
        rootPath=str(root_path),
        mapName=map_name,
        workspaceMode=workspace_mode,
        projectionString=projection_string,
        meshCount=len(meshes),
        layerSummaries=layer_summaries,
        defaultVisibleLayers=default_visible_layers,
        trafficSummary=traffic_summary,
        blocks=blocks,
        warnings=warnings,
    )


def build_scene(workspace_id: str, requested_layers: list[str]) -> WorkspaceSceneResponse:
    context = get_workspace(workspace_id)
    default_z = context.blocks[0].mapPose.center[2] if context.blocks else None
    layers = load_layers(context.gpkg_path, requested_layers, default_z)
    return WorkspaceSceneResponse(
        workspaceId=workspace_id,
        meshes=context.meshes,
        layers=layers,
        trafficRoutes=context.traffic_routes,
    )


def export_aligned_workspace(workspace_id: str, block_deltas: dict[str, BlockDelta]) -> dict:
    context = get_workspace(workspace_id)
    known_ids = {block.blockId for block in context.blocks}
    unknown_ids = sorted(set(block_deltas) - known_ids)
    if unknown_ids:
        raise WorkspaceError(f"Unknown block ids in blockDeltas: {', '.join(unknown_ids)}")

    exported = json.loads(json.dumps(context.gs3d_document))
    for block in context.blocks:
        delta = block_deltas.get(block.blockId)
        if delta is None:
            continue
        map_rt, _ = apply_block_delta(_flatten_pose(block.mapPose), delta)
        geocent_rt, _ = map_pose_to_geocent(flat_rt(map_rt), context.projection_string)
        exported["blocks"][block.blockId]["RT"] = flat_rt(geocent_rt)
        exported["blocks"][block.blockId]["center"] = geocent_rt[3, :3].tolist()
    return exported


def get_workspace(workspace_id: str) -> WorkspaceContext:
    try:
        return WORKSPACES[workspace_id]
    except KeyError as exc:
        raise WorkspaceError(f"Workspace '{workspace_id}' is not loaded.") from exc


def resolve_asset_path(workspace_id: str, relative_path: str) -> Path:
    context = get_workspace(workspace_id)
    candidate = (context.root_path / relative_path).resolve()
    if not str(candidate).startswith(str(context.root_path.resolve())):
        raise WorkspaceError("Requested asset path escapes the workspace root.")
    if not candidate.is_file():
        raise WorkspaceError(f"Asset not found: {relative_path}")
    return candidate


def _build_alignment_blocks(
    gs3d_document: dict,
    workspace_id: str,
    map_name: str,
    projection_string: str,
    root_path: Path,
) -> tuple[list[GsAlignmentView], list[str]]:
    blocks = []
    warnings = []
    for block_id, block_data in gs3d_document["blocks"].items():
        map_rt, _ = geocent_pose_to_map(block_data["RT"], projection_string)
        geocent_rt = [block_data["RT"][index:index + 4] for index in range(0, 16, 4)]
        relative_path, warning = _block_asset_path(
            root_path=root_path,
            asset_uri=block_data.get("filename"),
            map_name=map_name,
        )
        if warning:
            warnings.append(f"block {block_id}: {warning}")
        asset_url = _pointcloud_url(workspace_id, relative_path) if relative_path and relative_path.endswith(".ply") else (_asset_url(workspace_id, relative_path) if relative_path else None)
        blocks.append(
            GsAlignmentView(
                blockId=block_id,
                scale=float(block_data.get("scale", 1.0)),
                filename=block_data.get("filename"),
                projString=block_data.get("proj-string"),
                assetUrl=asset_url,
                geocentPose=PoseView(rtMatrix=geocent_rt, center=geocent_rt[3][:3]),
                mapPose=PoseView(rtMatrix=matrix_to_list(map_rt), center=map_rt[3, :3].tolist()),
            )
        )
    return blocks, warnings


def _resolve_workspace_path(workspace_path: str) -> Path:
    candidate = Path(workspace_path).expanduser().resolve()
    if not candidate.is_dir():
        raise WorkspaceError(f"Workspace path is not a directory: {workspace_path}")
    return candidate


def _find_single_file(directory: Path, suffix: str, label: str) -> Path:
    matches = sorted(path for path in directory.glob(f"*{suffix}") if path.is_file())
    if not matches:
        raise WorkspaceError(f"Workspace is missing {label} file: {directory}")
    return matches[0]


def _block_asset_path(
    root_path: Path,
    asset_uri: object,
    map_name: str,
) -> tuple[str | None, str | None]:
    fallback_path = "GS3D/full.ply"
    if isinstance(asset_uri, str):
        asset_map_name = _asset_map_name(asset_uri)
        relative_path = relative_asset_path(asset_uri, map_name)
        if relative_path and _asset_exists(root_path, relative_path):
            if asset_map_name and asset_map_name != map_name:
                return relative_path, _asset_map_warning(asset_uri, relative_path)
            return relative_path, None
        if _asset_exists(root_path, fallback_path):
            return fallback_path, f"asset path '{asset_uri}' not found; using local {fallback_path}."
        return None, f"GS asset not found for filename '{asset_uri}'."
    if _asset_exists(root_path, fallback_path):
        return fallback_path, "filename is missing; using local GS3D/full.ply."
    return None, "filename is missing and local GS3D/full.ply was not found."


def _asset_map_name(asset_uri: str) -> str | None:
    prefix = "asset://maps/"
    if not asset_uri.startswith(prefix):
        return None
    parts = asset_uri.removeprefix(prefix).split("/", 1)
    return parts[0] if parts and parts[0] else None


def _asset_map_warning(asset_uri: str, relative_path: str) -> str:
    return f"asset path '{asset_uri}' references another map; using local {relative_path}."


def _asset_exists(root_path: Path, relative_path: str) -> bool:
    root = root_path.resolve()
    candidate = (root_path / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return candidate.is_file()


def _asset_url(workspace_id: str, relative_path: str) -> str:
    return f"/api/workspace/asset/{workspace_id}/{relative_path}"


def _pointcloud_url(workspace_id: str, relative_path: str) -> str:
    return f"/api/workspace/pointcloud/{workspace_id}/{relative_path}"


def _flatten_pose(pose: PoseView) -> list[float]:
    return [value for row in pose.rtMatrix for value in row]
