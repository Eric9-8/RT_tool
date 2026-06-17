from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

GeometryType = Literal["Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "Geometry"]
WorkspaceMode = Literal["full_map", "semantic_only"]


class BlockDelta(BaseModel):
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    dx: float = 0.0
    dy: float = 0.0
    dz: float = 0.0


class PoseView(BaseModel):
    rtMatrix: list[list[float]]
    center: list[float]


class Gs3dBlockView(BaseModel):
    blockId: str
    rtMatrix: list[list[float]]
    center: list[float]
    scale: float = 1.0
    filename: str | None = None
    projString: str | None = None


class GsAlignmentView(BaseModel):
    blockId: str
    scale: float = 1.0
    filename: str | None = None
    projString: str | None = None
    assetUrl: str | None = None
    geocentPose: PoseView
    mapPose: PoseView


class Gs3dInspectResponse(BaseModel):
    version: str | None = None
    depthTestOffset: float | None = None
    blockCount: int
    blocks: list[Gs3dBlockView]


class ExportRequest(BaseModel):
    document: dict[str, Any]
    blockDeltas: dict[str, BlockDelta] = Field(default_factory=dict)


class MapLayerSummary(BaseModel):
    name: str
    geometryType: GeometryType
    featureCount: int
    bounds: list[list[float]] | None = None


class MapFeatureView(BaseModel):
    geometryType: GeometryType
    coordinates: list[Any]


class MapLayerView(MapLayerSummary):
    features: list[MapFeatureView] = Field(default_factory=list)


class TrafficRouteView(BaseModel):
    name: str
    laneId: int | None = None
    drivable: bool
    splineType: str | None = None
    turnSignal: str | None = None
    nextSplines: list[str] = Field(default_factory=list)
    prevSplines: list[str] = Field(default_factory=list)
    coordinates: list[list[float]]


class TrafficDataSummary(BaseModel):
    exists: bool
    routeCount: int = 0
    bounds: list[list[float]] | None = None
    referenceLayer: str | None = None
    referenceStatus: str = "missing"


class MapMeshView(BaseModel):
    name: str
    semanticLabel: str | None = None
    assetUrl: str
    relativePath: str
    bounds: list[list[float]] | None = None


class LoadWorkspaceRequest(BaseModel):
    workspacePath: str


class WorkspaceSceneRequest(BaseModel):
    workspaceId: str
    layers: list[str] = Field(default_factory=list)


class ExportAlignedRequest(BaseModel):
    workspaceId: str
    blockDeltas: dict[str, BlockDelta] = Field(default_factory=dict)


class WorkspaceLoadResponse(BaseModel):
    workspaceId: str
    rootPath: str
    mapName: str
    workspaceMode: WorkspaceMode = "full_map"
    projectionString: str
    meshCount: int
    layerSummaries: list[MapLayerSummary]
    defaultVisibleLayers: list[str]
    trafficSummary: TrafficDataSummary
    blocks: list[GsAlignmentView]
    warnings: list[str] = Field(default_factory=list)


class WorkspaceSceneResponse(BaseModel):
    workspaceId: str
    meshes: list[MapMeshView]
    layers: list[MapLayerView]
    trafficRoutes: list[TrafficRouteView] = Field(default_factory=list)
