from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.models import MapMeshView


class MapMeshError(ValueError):
    pass


def parse_meshes(map_json_path: Path, workspace_id: str, map_name: str) -> list[MapMeshView]:
    try:
        document = json.loads(map_json_path.read_text())
    except json.JSONDecodeError as exc:
        raise MapMeshError(f"Invalid map.json: {exc.msg}") from exc
    return [
        mesh
        for actor_commands in document.get("actors", [])
        if (mesh := _mesh_from_actor(actor_commands, workspace_id, map_name)) is not None
    ]


def relative_asset_path(asset_uri: str, map_name: str) -> str | None:
    marker = f"/maps/{map_name}/"
    if marker in asset_uri:
        return asset_uri.split(marker, 1)[1]
    if asset_uri.startswith("asset://maps/"):
        parts = asset_uri.removeprefix("asset://maps/").split("/", 1)
        return parts[1] if len(parts) == 2 else None
    if asset_uri.startswith("asset://"):
        parts = asset_uri.split(f"{map_name}/", 1)
        if len(parts) == 2:
            return parts[1]
        return asset_uri.removeprefix("asset://")
    candidate = asset_uri.lstrip("/")
    return candidate if candidate else None


def _mesh_from_actor(actor_commands: Any, workspace_id: str, map_name: str) -> MapMeshView | None:
    if not isinstance(actor_commands, list):
        return None
    base_name, semantic_label, mesh_asset, bounds = _actor_values(actor_commands)
    if not base_name or not mesh_asset:
        return None
    relative_path = relative_asset_path(mesh_asset, map_name)
    if not relative_path:
        return None
    return MapMeshView(
        name=base_name,
        semanticLabel=semantic_label,
        assetUrl=f"/api/workspace/asset/{workspace_id}/{relative_path}",
        relativePath=relative_path,
        bounds=bounds,
    )


def _actor_values(actor_commands: list[dict]) -> tuple[str | None, str | None, str | None, list | None]:
    base_name = None
    semantic_label = None
    mesh_asset = None
    bounds = None
    for command in actor_commands:
        if command.get("command_type") == "Initial":
            base_name = command.get("parameters", {}).get("name")
        if command.get("command_type") == "AddMeshNode":
            semantic_label = command.get("semantic_label")
            mesh_asset = command.get("mesh_asset")
        if command.get("command_type") == "AddAttributes":
            bounds_value = command.get("attributes", {}).get("bounds")
            bounds = [bounds_value["min"], bounds_value["max"]] if bounds_value else bounds
    return base_name, semantic_label, mesh_asset, bounds
