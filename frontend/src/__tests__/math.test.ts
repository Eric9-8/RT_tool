import { describe, expect, test } from "vitest";
import { Vector3 } from "three";

import cases from "../../../shared/testdata/gs3d_transform_cases.json";

import { flattenMatrix, mapSceneBounds, previewPose, rtConventionInfo, sceneDisplayTransform, sceneMatrixFromPose } from "../math";
import type { PoseView } from "../types";

function buildPose(rt: number[]): PoseView {
  return {
    rtMatrix: [rt.slice(0, 4), rt.slice(4, 8), rt.slice(8, 12), rt.slice(12, 16)],
    center: rt.slice(12, 15)
  };
}

describe("previewPose", () => {
  test.each(cases.cases)("matches shared transform case $name", (entry) => {
    const pose = previewPose(buildPose(entry.rt), entry.delta);
    expect(flattenMatrix(pose.rtMatrix)).toHaveLength(16);
    flattenMatrix(pose.rtMatrix).forEach((value, index) => {
      expect(value).toBeCloseTo(entry.expectedRt[index], 9);
    });
    pose.center.forEach((value, index) => {
      expect(value).toBeCloseTo(entry.expectedCenter[index], 9);
    });
  });
});

describe("sceneMatrixFromPose", () => {
  test("renders row-vector RT rows as local axes in Three.js", () => {
    const pose = buildPose([
      0, -1, 0, 0,
      1, 0, 0, 0,
      0, 0, 1, 0,
      10, 20, 30, 1
    ]);
    const matrix = sceneMatrixFromPose(pose);
    const origin = new Vector3(0, 0, 0).applyMatrix4(matrix);
    const xAxis = new Vector3(1, 0, 0).applyMatrix4(matrix).sub(origin);
    const yAxis = new Vector3(0, 1, 0).applyMatrix4(matrix).sub(origin);

    expect(origin.toArray()).toEqual([10, 20, 30]);
    expect(xAxis.toArray()).toEqual([0, -1, 0]);
    expect(yAxis.toArray()).toEqual([1, 0, 0]);
  });
});

describe("rtConventionInfo", () => {
  test("reports row-vector yaw and up axis", () => {
    const info = rtConventionInfo(buildPose([
      0, -1, 0, 0,
      1, 0, 0, 0,
      0, 0, 1, 0,
      10, 20, 30, 1
    ]));

    expect(info?.yawPitchRoll[0]).toBeCloseTo(90, 9);
    expect(info?.upAxis).toEqual([0, 0, 1]);
  });
});

describe("sceneDisplayTransform", () => {
  test("follows selected block in follow_block mode", () => {
    const transform = sceneDisplayTransform(
      [[0, 0, 2], [10, 20, 8]],
      [4, 5, 6],
      "follow_block"
    );

    expect(transform.offset).toEqual([-4, -5, -6]);
    expect(transform.orbitTarget).toEqual([0, 0, 0]);
    expect(transform.groundZ).toBe(-4);
  });

  test("anchors map at origin and grounds min z", () => {
    const transform = sceneDisplayTransform(
      [[0, 0, 2], [10, 20, 8]],
      [99, 88, 77],
      "map_origin_grounded"
    );

    expect(transform.offset).toEqual([-5, -10, -2]);
    expect(transform.orbitTarget).toEqual([0, 0, 3]);
    expect(transform.groundZ).toBe(0);
  });

  test("throws when grounded mode lacks map bounds", () => {
    expect(() => sceneDisplayTransform(null, [1, 2, 3], "map_origin_grounded")).toThrow(
      "缺少地图范围，无法启用地图固定模式。"
    );
  });
});

describe("mapSceneBounds", () => {
  test("combines mesh and semantic layer bounds", () => {
    const bounds = mapSceneBounds({
      workspaceId: "ws-1",
      meshes: [{ name: "mesh", semanticLabel: null, assetUrl: "/mesh", relativePath: "Meshes/map.gltf", bounds: [[5, 6, 2], [12, 15, 9]] }],
      layers: [{ name: "RoadReferenceLines", geometryType: "LineString", featureCount: 1, bounds: [[-3, 1, 0], [8, 18, 4]], features: [] }],
      trafficRoutes: []
    });

    expect(bounds).toEqual([[-3, 1, 0], [12, 18, 9]]);
  });
});
