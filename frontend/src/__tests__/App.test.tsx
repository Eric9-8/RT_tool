import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import App from "../App";

const loadWorkspaceMock = vi.fn();
const loadWorkspaceSceneMock = vi.fn();
const exportAlignedMock = vi.fn();

vi.mock("../api", () => ({
  loadWorkspace: (workspacePath: string) => loadWorkspaceMock(workspacePath),
  loadWorkspaceScene: (workspaceId: string, layers: string[]) => loadWorkspaceSceneMock(workspaceId, layers),
  exportAlignedGs3d: (workspaceId: string, deltas: Record<string, unknown>) => exportAlignedMock(workspaceId, deltas)
}));

vi.mock("../components/ScenePanel", () => ({
  ScenePanel: () => <div data-testid="scene-panel">scene</div>
}));

const workspacePayload = {
  workspaceId: "ws-1",
  rootPath: "/tmp/map",
  mapName: "demo-map",
  workspaceMode: "full_map",
  projectionString: "+proj=tmerc",
  meshCount: 1,
  warnings: [],
  trafficSummary: {
    exists: true,
    routeCount: 2,
    bounds: [[0, 0, 0], [10, 5, 0]],
    referenceLayer: "RoadReferenceLines",
    referenceStatus: "fallback"
  },
  defaultVisibleLayers: ["RoadReferenceLines"],
  layerSummaries: [
    { name: "RoadReferenceLines", geometryType: "MultiLineString", featureCount: 1, bounds: [[0, 0, 0], [10, 5, 0]] },
    { name: "RoadMarks", geometryType: "LineString", featureCount: 1, bounds: [[0, 0, 0], [10, 5, 0]] }
  ],
  blocks: [
    {
      blockId: "0",
      scale: 1,
      filename: "asset://maps/demo/GS3D/full.ply",
      projString: "+proj=geocent",
      assetUrl: "/api/workspace/asset/ws-1/GS3D/full.ply",
      geocentPose: {
        rtMatrix: [
          [1, 0, 0, 0],
          [0, 1, 0, 0],
          [0, 0, 1, 0],
          [100, 200, 300, 1]
        ],
        center: [100, 200, 300]
      },
      mapPose: {
        rtMatrix: [
          [1, 0, 0, 0],
          [0, 1, 0, 0],
          [0, 0, 1, 0],
          [10, 20, 30, 1]
        ],
        center: [10, 20, 30]
      }
    },
    {
      blockId: "1",
      scale: 0.5,
      filename: null,
      projString: "+proj=geocent",
      assetUrl: null,
      geocentPose: {
        rtMatrix: [
          [1, 0, 0, 0],
          [0, 1, 0, 0],
          [0, 0, 1, 0],
          [0, 0, 0, 1]
        ],
        center: [0, 0, 0]
      },
      mapPose: {
        rtMatrix: [
          [1, 0, 0, 0],
          [0, 1, 0, 0],
          [0, 0, 1, 0],
          [-5, 2, 8, 1]
        ],
        center: [-5, 2, 8]
      }
    }
  ]
};

const scenePayload = {
  workspaceId: "ws-1",
  meshes: [],
  trafficRoutes: [
    {
      name: "Spline_0_0",
      laneId: 0,
      drivable: true,
      splineType: "TrafficSpline",
      turnSignal: "None",
      nextSplines: ["Spline_1_1"],
      prevSplines: [],
      coordinates: [[0, 0, 0], [10, 5, 0]]
    }
  ],
  layers: [
    {
      name: "RoadReferenceLines",
      geometryType: "MultiLineString",
      featureCount: 1,
      bounds: [[0, 0, 0], [10, 5, 0]],
      features: []
    },
    {
      name: "RoadMarks",
      geometryType: "LineString",
      featureCount: 1,
      bounds: [[0, 0, 0], [10, 5, 0]],
      features: []
    }
  ]
};

const semanticWorkspacePayload = {
  ...workspacePayload,
  workspaceMode: "semantic_only",
  meshCount: 0,
  warnings: ["block 0: asset path references another map; using local GS3D/full.ply."]
};

beforeEach(() => {
  loadWorkspaceMock.mockResolvedValue(workspacePayload);
  loadWorkspaceSceneMock.mockResolvedValue(scenePayload);
  exportAlignedMock.mockResolvedValue(new Blob(["{}"], { type: "application/json" }));
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: vi.fn(() => "blob:mock")
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: vi.fn(() => undefined)
  });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("loads workspace and preserves per-block deltas", async () => {
  render(<App />);

  await userEvent.type(screen.getByLabelText("工作区目录"), "/tmp/map");
  await userEvent.click(screen.getByRole("button", { name: "加载工作区" }));
  await screen.findByRole("button", { name: /Block 0/i });

  await userEvent.clear(screen.getByLabelText("Yaw (deg)"));
  await userEvent.type(screen.getByLabelText("Yaw (deg)"), "90");
  await userEvent.clear(screen.getByLabelText("GS Local X (m)"));
  await userEvent.type(screen.getByLabelText("GS Local X (m)"), "1");
  await userEvent.clear(screen.getByLabelText("GS Local Y (m)"));
  await userEvent.type(screen.getByLabelText("GS Local Y (m)"), "2");
  await userEvent.clear(screen.getByLabelText("GS Local Z (m)"));
  await userEvent.type(screen.getByLabelText("GS Local Z (m)"), "3");

  await waitFor(() => {
    expect(screen.getByText(/12,\s*19,\s*33/)).toBeInTheDocument();
  });

  await userEvent.click(screen.getByRole("button", { name: /Block 1/i }));
  await userEvent.clear(screen.getByLabelText("Yaw (deg)"));
  await userEvent.type(screen.getByLabelText("Yaw (deg)"), "7");
  await userEvent.click(screen.getByRole("button", { name: /Block 0/i }));

  expect(screen.getByLabelText("Yaw (deg)")).toHaveValue(90);
});

test("exports aligned gs3d and allows layer toggles", async () => {
  render(<App />);

  await userEvent.type(screen.getByLabelText("工作区目录"), "/tmp/map");
  await userEvent.click(screen.getByRole("button", { name: "加载工作区" }));
  await screen.findByRole("button", { name: /Block 0/i });

  await userEvent.click(screen.getByLabelText("RoadMarks"));
  await userEvent.clear(screen.getByLabelText("Yaw (deg)"));
  await userEvent.type(screen.getByLabelText("Yaw (deg)"), "15");
  await userEvent.click(screen.getByLabelText("地图固定到原点并贴地"));
  expect(screen.getByLabelText("Yaw (deg)")).toHaveValue(15);
  await userEvent.click(screen.getByRole("button", { name: "导出 gs3d.json" }));

  await waitFor(() => {
    expect(exportAlignedMock).toHaveBeenCalledTimes(1);
  });
  expect(exportAlignedMock.mock.calls[0][0]).toBe("ws-1");
  expect(exportAlignedMock.mock.calls[0][1]["0"].yaw).toBe(15);
});

test("supports two-decimal delta inputs without rounding export values", async () => {
  render(<App />);

  await userEvent.type(screen.getByLabelText("工作区目录"), "/tmp/map");
  await userEvent.click(screen.getByRole("button", { name: "加载工作区" }));
  await screen.findByRole("button", { name: /Block 0/i });

  expect(screen.getByLabelText("Yaw (deg)")).toHaveAttribute("step", "0.01");
  expect(screen.getByLabelText("GS Local X (m)")).toHaveAttribute("step", "0.01");

  await userEvent.clear(screen.getByLabelText("Yaw (deg)"));
  await userEvent.type(screen.getByLabelText("Yaw (deg)"), "15.25");
  await userEvent.clear(screen.getByLabelText("GS Local X (m)"));
  await userEvent.type(screen.getByLabelText("GS Local X (m)"), "1.75");
  await userEvent.click(screen.getByRole("button", { name: "导出 gs3d.json" }));

  await waitFor(() => {
    expect(exportAlignedMock).toHaveBeenCalledTimes(1);
  });
  expect(exportAlignedMock.mock.calls[0][1]["0"].yaw).toBe(15.25);
  expect(exportAlignedMock.mock.calls[0][1]["0"].dx).toBe(1.75);
});

test("disables grounded anchor mode when scene has no bounds", async () => {
  loadWorkspaceSceneMock.mockResolvedValueOnce({
    workspaceId: "ws-1",
    meshes: [],
    layers: [
      {
        name: "RoadReferenceLines",
        geometryType: "MultiLineString",
        featureCount: 1,
        bounds: null,
        features: []
      }
    ],
    trafficRoutes: []
  });

  render(<App />);

  await userEvent.type(screen.getByLabelText("工作区目录"), "/tmp/map");
  await userEvent.click(screen.getByRole("button", { name: "加载工作区" }));
  await screen.findByRole("button", { name: /Block 0/i });

  expect(screen.getByLabelText("地图固定到原点并贴地")).toBeDisabled();
  expect(screen.getByText("缺少地图范围，无法启用地图固定模式。")).toBeInTheDocument();
});

test("loads semantic-only workspace without mesh controls", async () => {
  loadWorkspaceMock.mockResolvedValueOnce(semanticWorkspacePayload);
  render(<App />);

  await userEvent.type(screen.getByLabelText("工作区目录"), "/tmp/semantic-map");
  await userEvent.click(screen.getByRole("button", { name: "加载工作区" }));
  await screen.findByRole("button", { name: /Block 0/i });

  expect(screen.getAllByText(/轻量语义模式/).length).toBeGreaterThan(0);
  expect(screen.getByText(/using local GS3D\/full\.ply/)).toBeInTheDocument();
  expect(screen.getByLabelText("显示 traffic routes")).toBeChecked();
  expect(screen.getByText(/缺少 Paths，使用可用参考层/)).toBeInTheDocument();
  expect(screen.queryByLabelText("显示地图网格")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("地图网格透明度")).not.toBeInTheDocument();
  expect(screen.getByText("当前目录没有 map.json/Meshes，仅显示 GPKG 语义层与 GS 点云。")).toBeInTheDocument();

  await userEvent.clear(screen.getByLabelText("Yaw (deg)"));
  await userEvent.type(screen.getByLabelText("Yaw (deg)"), "22");
  await userEvent.click(screen.getByRole("button", { name: "导出 gs3d.json" }));

  await waitFor(() => {
    expect(exportAlignedMock).toHaveBeenCalledTimes(1);
  });
  expect(exportAlignedMock.mock.calls[0][1]["0"].yaw).toBe(22);
});
