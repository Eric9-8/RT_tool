import { Matrix4, Vector3 } from "three";

import type {
  BlockDelta,
  Bounds3,
  PoseView,
  PreviewPose,
  RtConventionInfo,
  SceneAnchorMode,
  SceneDisplayTransform,
  WorkspaceSceneResponse
} from "./types";

const FALLBACK_GROUND_Z = -1;

export function rotationMatrix(yawDeg: number, pitchDeg: number, rollDeg: number): number[][] {
  const yaw = toRadians(yawDeg);
  const pitch = toRadians(pitchDeg);
  const roll = toRadians(rollDeg);
  const rz = [
    [Math.cos(yaw), -Math.sin(yaw), 0],
    [Math.sin(yaw), Math.cos(yaw), 0],
    [0, 0, 1]
  ];
  const ry = [
    [Math.cos(pitch), 0, Math.sin(pitch)],
    [0, 1, 0],
    [-Math.sin(pitch), 0, Math.cos(pitch)]
  ];
  const rx = [
    [1, 0, 0],
    [0, Math.cos(roll), -Math.sin(roll)],
    [0, Math.sin(roll), Math.cos(roll)]
  ];
  return multiply3x3(multiply3x3(rz, ry), rx);
}

export function previewPose(pose: PoseView, delta: BlockDelta): PreviewPose {
  const baseRotation = pose.rtMatrix.slice(0, 3).map((row) => row.slice(0, 3));
  const baseTranslation = pose.rtMatrix[3].slice(0, 3);
  const deltaRotation = rotationMatrix(delta.yaw, delta.pitch, delta.roll);
  const nextRotation = multiply3x3(deltaRotation, baseRotation);
  const nextTranslation = add3(baseTranslation, multiplyVectorMatrix([delta.dx, delta.dy, delta.dz], nextRotation));
  return {
    rtMatrix: [
      [...nextRotation[0], 0],
      [...nextRotation[1], 0],
      [...nextRotation[2], 0],
      [...nextTranslation, 1]
    ],
    center: nextTranslation
  };
}

export function toRelativePosition(position: number[], origin: number[]): [number, number, number] {
  return [
    position[0] - origin[0],
    position[1] - origin[1],
    position[2] - origin[2]
  ];
}

export function flattenMatrix(matrix: number[][]): number[] {
  return matrix.flat();
}

export function matrixRows(matrix: number[][]): string[] {
  return matrix.map((row) => row.map((value) => value.toFixed(6)).join("  "));
}

export function sceneMatrixFromPose(pose: PoseView, scale = 1): Matrix4 {
  const rotation = pose.rtMatrix.slice(0, 3).map((row) => row.slice(0, 3));
  const translation = pose.center;
  const matrix = new Matrix4();
  const basis = new Matrix4().makeBasis(
    vector3FromRow(rotation, 0),
    vector3FromRow(rotation, 1),
    vector3FromRow(rotation, 2)
  );
  matrix.copy(basis);
  matrix.scale(new Vector3(scale, scale, scale));
  matrix.setPosition(translation[0], translation[1], translation[2]);
  return matrix;
}

export function rtConventionInfo(pose: PoseView | null): RtConventionInfo | null {
  if (!pose) {
    return null;
  }
  const rotation = pose.rtMatrix.slice(0, 3).map((row) => row.slice(0, 3));
  return {
    yawPitchRoll: rowVectorEulerDegrees(rotation),
    upAxis: tuple3(rotation[2])
  };
}

export function sceneCenter(layersBounds: number[][] | null, poseCenter: number[] | null): [number, number, number] {
  if (poseCenter) {
    return [poseCenter[0], poseCenter[1], poseCenter[2]];
  }
  if (layersBounds) {
    return [
      (layersBounds[0][0] + layersBounds[1][0]) / 2,
      (layersBounds[0][1] + layersBounds[1][1]) / 2,
      (layersBounds[0][2] + layersBounds[1][2]) / 2
    ];
  }
  return [0, 0, 0];
}

export function mapSceneBounds(scene: WorkspaceSceneResponse | null): Bounds3 | null {
  if (!scene) {
    return null;
  }
  const allBounds = [...scene.layers, ...scene.meshes, routeBounds(scene.trafficRoutes)]
    .map((entry) => entry && "bounds" in entry ? entry.bounds : entry)
    .filter(Boolean) as Bounds3[];
  if (!allBounds.length) {
    return null;
  }
  return combineBounds(allBounds);
}

export function sceneDisplayTransform(
  bounds: Bounds3 | null,
  poseCenter: number[] | null,
  mode: SceneAnchorMode
): SceneDisplayTransform {
  if (mode === "map_origin_grounded") {
    if (!bounds) {
      throw new Error("缺少地图范围，无法启用地图固定模式。");
    }
    const centerX = (bounds[0][0] + bounds[1][0]) / 2;
    const centerY = (bounds[0][1] + bounds[1][1]) / 2;
    const spanZ = bounds[1][2] - bounds[0][2];
    return {
      offset: [-centerX, -centerY, -bounds[0][2]],
      orbitTarget: [0, 0, spanZ / 2],
      groundZ: 0
    };
  }

  const center = sceneCenter(bounds, poseCenter);
  const groundZ = bounds ? bounds[0][2] - center[2] : FALLBACK_GROUND_Z;
  return {
    offset: [-center[0], -center[1], -center[2]],
    orbitTarget: [0, 0, 0],
    groundZ
  };
}

export function gridSpec(bounds: Bounds3 | null): { size: number; divisions: number } {
  if (!bounds) {
    return { size: 220, divisions: 22 };
  }
  const spanX = bounds[1][0] - bounds[0][0];
  const spanY = bounds[1][1] - bounds[0][1];
  const maxSpan = Math.max(spanX, spanY, 120);
  const snappedSize = Math.ceil(maxSpan / 20) * 20;
  return {
    size: snappedSize,
    divisions: Math.max(12, Math.round(snappedSize / 10))
  };
}

function multiply3x3(left: number[][], right: number[][]): number[][] {
  return left.map((row) =>
    right[0].map((_, columnIndex) =>
      row.reduce((sum, value, valueIndex) => sum + value * right[valueIndex][columnIndex], 0)
    )
  );
}

function multiplyMatrixVector(matrix: number[][], vector: number[]): number[] {
  return matrix.map((row) => row.reduce((sum, value, index) => sum + value * vector[index], 0));
}

function multiplyVectorMatrix(vector: number[], matrix: number[][]): number[] {
  return matrix[0].map((_, columnIndex) =>
    vector.reduce((sum, value, rowIndex) => sum + value * matrix[rowIndex][columnIndex], 0)
  );
}

function add3(left: number[], right: number[]): number[] {
  return left.map((value, index) => value + right[index]);
}

function combineBounds(boundsList: Bounds3[]): Bounds3 {
  return [
    [
      Math.min(...boundsList.map((bounds) => bounds[0][0])),
      Math.min(...boundsList.map((bounds) => bounds[0][1])),
      Math.min(...boundsList.map((bounds) => bounds[0][2] ?? 0))
    ],
    [
      Math.max(...boundsList.map((bounds) => bounds[1][0])),
      Math.max(...boundsList.map((bounds) => bounds[1][1])),
      Math.max(...boundsList.map((bounds) => bounds[1][2] ?? 0))
    ]
  ];
}

function routeBounds(routes: WorkspaceSceneResponse["trafficRoutes"]): Bounds3 | null {
  const points = routes.flatMap((route) => route.coordinates);
  if (!points.length) {
    return null;
  }
  return [
    [
      Math.min(...points.map((point) => point[0])),
      Math.min(...points.map((point) => point[1])),
      Math.min(...points.map((point) => point[2] ?? 0))
    ],
    [
      Math.max(...points.map((point) => point[0])),
      Math.max(...points.map((point) => point[1])),
      Math.max(...points.map((point) => point[2] ?? 0))
    ]
  ];
}

function toRadians(degrees: number): number {
  return (degrees * Math.PI) / 180;
}

function rowVectorEulerDegrees(rotation: number[][]): [number, number, number] {
  const pitch = Math.asin(clamp(-rotation[2][0], -1, 1));
  const cosPitch = Math.cos(pitch);
  const yaw = Math.atan2(rotation[1][0], rotation[0][0]);
  const roll = Math.abs(cosPitch) < 1e-9 ? 0 : Math.atan2(rotation[2][1], rotation[2][2]);
  return [toDegrees(yaw), toDegrees(pitch), toDegrees(roll)];
}

function vector3FromRow(matrix: number[][], rowIndex: number): Vector3 {
  return new Vector3(matrix[rowIndex][0], matrix[rowIndex][1], matrix[rowIndex][2]);
}

function tuple3(vector: number[]): [number, number, number] {
  return [vector[0], vector[1], vector[2]];
}

function clamp(value: number, minValue: number, maxValue: number): number {
  return Math.min(Math.max(value, minValue), maxValue);
}

function toDegrees(radians: number): number {
  return (radians * 180) / Math.PI;
}
