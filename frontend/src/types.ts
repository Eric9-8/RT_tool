export type Matrix3 = number[][];
export type Matrix4 = number[][];
export type Bounds3 = [number[], number[]];

export type BlockDelta = {
  yaw: number;
  pitch: number;
  roll: number;
  dx: number;
  dy: number;
  dz: number;
};

export type PoseView = {
  rtMatrix: Matrix4;
  center: number[];
};

export type Gs3dBlockView = {
  blockId: string;
  rtMatrix: Matrix4;
  center: number[];
  scale: number;
  filename: string | null;
  projString: string | null;
};

export type GsAlignmentView = {
  blockId: string;
  scale: number;
  filename: string | null;
  projString: string | null;
  assetUrl: string | null;
  geocentPose: PoseView;
  mapPose: PoseView;
};

export type InspectResponse = {
  version: string | null;
  depthTestOffset: number | null;
  blockCount: number;
  blocks: Gs3dBlockView[];
};

export type GeometryType = "Point" | "MultiPoint" | "LineString" | "MultiLineString" | "Polygon" | "Geometry";

export type MapLayerSummary = {
  name: string;
  geometryType: GeometryType;
  featureCount: number;
  bounds: number[][] | null;
};

export type MapFeatureView = {
  geometryType: GeometryType;
  coordinates: number[][] | number[][][];
};

export type MapLayerView = MapLayerSummary & {
  features: MapFeatureView[];
};

export type TrafficRouteView = {
  name: string;
  laneId: number | null;
  drivable: boolean;
  splineType: string | null;
  turnSignal: string | null;
  nextSplines: string[];
  prevSplines: string[];
  coordinates: number[][];
};

export type TrafficDataSummary = {
  exists: boolean;
  routeCount: number;
  bounds: number[][] | null;
  referenceLayer: string | null;
  referenceStatus: "preferred" | "fallback" | "missing";
};

export type MapMeshView = {
  name: string;
  semanticLabel: string | null;
  assetUrl: string;
  relativePath: string;
  bounds: number[][] | null;
};

export type WorkspaceLoadResponse = {
  workspaceId: string;
  rootPath: string;
  mapName: string;
  workspaceMode: WorkspaceMode;
  projectionString: string;
  meshCount: number;
  layerSummaries: MapLayerSummary[];
  defaultVisibleLayers: string[];
  trafficSummary: TrafficDataSummary;
  blocks: GsAlignmentView[];
  warnings: string[];
};

export type WorkspaceSceneResponse = {
  workspaceId: string;
  meshes: MapMeshView[];
  layers: MapLayerView[];
  trafficRoutes: TrafficRouteView[];
};

export type Gs3dDocument = Record<string, unknown>;

export type PreviewPose = PoseView;

export type SceneAnchorMode = "follow_block" | "map_origin_grounded";
export type WorkspaceMode = "full_map" | "semantic_only";

export type SceneDisplayTransform = {
  offset: [number, number, number];
  orbitTarget: [number, number, number];
  groundZ: number;
};

export type RtConventionInfo = {
  yawPitchRoll: [number, number, number];
  upAxis: [number, number, number];
};

export type LayerVisibilityState = {
  showMeshes: boolean;
  showGsAsset: boolean;
  showTrafficRoutes: boolean;
  meshOpacity: number;
  gsOpacity: number;
  visibleLayers: Record<string, boolean>;
};

export type WorkspaceStatus = {
  mode: WorkspaceMode;
  warnings: string[];
};

export const ZERO_DELTA: BlockDelta = {
  yaw: 0,
  pitch: 0,
  roll: 0,
  dx: 0,
  dy: 0,
  dz: 0
};

export const DELTA_FIELDS: Array<keyof BlockDelta> = [
  "yaw",
  "pitch",
  "roll",
  "dx",
  "dy",
  "dz"
];
