import { useMemo, useState } from "react";

import { exportAlignedGs3d, exportTopview, loadWorkspace, loadWorkspaceScene } from "./api";
import { mapSceneBounds, previewPose } from "./math";
import { BlockList } from "./components/BlockList";
import { ControlPanel } from "./components/ControlPanel";
import { ScenePanel } from "./components/ScenePanel";
import { UploadPanel } from "./components/UploadPanel";
import type {
  BlockDelta,
  GsAlignmentView,
  LayerVisibilityState,
  SceneAnchorMode,
  WorkspaceLoadResponse,
  WorkspaceSceneResponse
} from "./types";
import { ZERO_DELTA } from "./types";

export default function App() {
  const [workspacePath, setWorkspacePath] = useState("");
  const [workspace, setWorkspace] = useState<WorkspaceLoadResponse | null>(null);
  const [scene, setScene] = useState<WorkspaceSceneResponse | null>(null);
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null);
  const [deltas, setDeltas] = useState<Record<string, BlockDelta>>({});
  const [sceneAnchorMode, setSceneAnchorMode] = useState<SceneAnchorMode>("follow_block");
  const [layerState, setLayerState] = useState<LayerVisibilityState>({
    showMeshes: true,
    showGsAsset: true,
    showTrafficRoutes: true,
    meshOpacity: 0.48,
    gsOpacity: 0.85,
    visibleLayers: {}
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const blocks = workspace?.blocks ?? [];
  const selectedBlock = blocks.find((block) => block.blockId === selectedBlockId) ?? null;
  const selectedDelta = selectedBlockId ? deltas[selectedBlockId] ?? ZERO_DELTA : ZERO_DELTA;
  const preview = selectedBlock ? previewPose(selectedBlock.mapPose, selectedDelta) : null;
  const hasMapBounds = Boolean(mapSceneBounds(scene));
  const hasMeshLayer = workspace ? workspace.meshCount > 0 : (scene?.meshes.length ?? 0) > 0;
  const workspaceModeLabel = workspace?.workspaceMode === "semantic_only" ? "轻量语义模式" : "完整地图模式";
  const visibleLayers = useMemo(
    () =>
      Object.entries(layerState.visibleLayers)
        .filter(([, visible]) => visible)
        .map(([layerName]) => layerName),
    [layerState.visibleLayers]
  );

  async function handleLoadWorkspace() {
    setBusy(true);
    setError(null);
    try {
      const loadedWorkspace = await loadWorkspace(workspacePath.trim());
      const loadedScene = await loadWorkspaceScene(
        loadedWorkspace.workspaceId,
        loadedWorkspace.layerSummaries.map((layer) => layer.name)
      );
      setWorkspace(loadedWorkspace);
      setScene(loadedScene);
      setSelectedBlockId(loadedWorkspace.blocks[0]?.blockId ?? null);
      setSceneAnchorMode("follow_block");
      setDeltas(
        Object.fromEntries(loadedWorkspace.blocks.map((block) => [block.blockId, { ...ZERO_DELTA }]))
      );
      setLayerState({
        showMeshes: loadedWorkspace.meshCount > 0,
        showGsAsset: true,
        showTrafficRoutes: loadedWorkspace.trafficSummary.exists,
        meshOpacity: 0.48,
        gsOpacity: 0.85,
        visibleLayers: Object.fromEntries(
          loadedWorkspace.layerSummaries.map((layer) => [
            layer.name,
            isInitialLayerVisible(layer.name, loadedWorkspace)
          ])
        )
      });
    } catch (caught) {
      setWorkspace(null);
      setScene(null);
      setSelectedBlockId(null);
      setDeltas({});
      setError(caught instanceof Error ? caught.message : "工作区加载失败。");
    } finally {
      setBusy(false);
    }
  }

  function handleDeltaChange(field: keyof BlockDelta, value: number) {
    if (!selectedBlockId) {
      return;
    }
    setDeltas((current) => ({
      ...current,
      [selectedBlockId]: { ...(current[selectedBlockId] ?? ZERO_DELTA), [field]: value }
    }));
  }

  function handleLayerToggle(layerName: string) {
    setLayerState((current) => ({
      ...current,
      visibleLayers: {
        ...current.visibleLayers,
        [layerName]: !current.visibleLayers[layerName]
      }
    }));
  }

  function handleOpacityChange(field: "meshOpacity" | "gsOpacity", value: number) {
    setLayerState((current) => ({ ...current, [field]: value }));
  }

  function resetSelectedBlock() {
    if (!selectedBlockId) {
      return;
    }
    setDeltas((current) => ({ ...current, [selectedBlockId]: { ...ZERO_DELTA } }));
  }

  function resetAllBlocks() {
    setDeltas(Object.fromEntries(blocks.map((block) => [block.blockId, { ...ZERO_DELTA }])));
  }

  function handleSceneAnchorModeChange(nextMode: SceneAnchorMode) {
    if (nextMode === "map_origin_grounded" && !hasMapBounds) {
      setError("缺少地图范围，无法启用地图固定模式。");
      return;
    }
    setError(null);
    setSceneAnchorMode(nextMode);
  }

  async function handleExportTopview() {
    if (!workspace) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const blob = await exportTopview(workspace.workspaceId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${workspace.mapName}_topview.zip`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "俯视图导出失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleExport() {
    if (!workspace) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const blob = await exportAlignedGs3d(workspace.workspaceId, deltas);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${workspace.mapName}_aligned_gs3d.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "导出失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="hero-panel">
        <div>
          <span className="eyebrow">Map-First Alignment Atelier</span>
          <h1>地图对齐可视化</h1>
        </div>
        <p>
          先加载地图工作区，再同时查看地图网格、GPKG 语义层和 GS 资产。所有调整都在地图投影坐标系下进行，
          导出时再自动回写成标准 <code>gs3d.json</code>。
        </p>
      </section>
      <section className="workspace-grid">
        <div className="sidebar-stack">
          <UploadPanel
            busy={busy}
            error={error}
            loadedPath={workspace?.rootPath ?? null}
            onLoad={handleLoadWorkspace}
            onPathChange={setWorkspacePath}
            workspaceStatus={
              workspace ? { mode: workspace.workspaceMode, warnings: workspace.warnings } : null
            }
            workspacePath={workspacePath}
          />
          <BlockList blocks={blocks} onSelect={setSelectedBlockId} selectedBlockId={selectedBlockId} />
        </div>
        <ScenePanel
          blocks={blocks}
          deltas={deltas}
          layerState={layerState}
          scene={scene}
          sceneAnchorMode={sceneAnchorMode}
          selectedBlockId={selectedBlockId}
        />
        <ControlPanel
          block={selectedBlock}
          busy={busy}
          delta={selectedDelta}
          hasMapBounds={hasMapBounds}
          hasMeshLayer={hasMeshLayer}
          layerState={layerState}
          layerSummaries={workspace?.layerSummaries ?? []}
          onAnchorModeChange={handleSceneAnchorModeChange}
          onDeltaChange={handleDeltaChange}
          onExport={handleExport}
          onExportTopview={handleExportTopview}
          onGsToggle={() => setLayerState((current) => ({ ...current, showGsAsset: !current.showGsAsset }))}
          onLayerToggle={handleLayerToggle}
          onMeshToggle={() => setLayerState((current) => ({ ...current, showMeshes: !current.showMeshes }))}
          onOpacityChange={handleOpacityChange}
          onResetAll={resetAllBlocks}
          onResetBlock={resetSelectedBlock}
          onTrafficToggle={() =>
            setLayerState((current) => ({ ...current, showTrafficRoutes: !current.showTrafficRoutes }))
          }
          preview={preview}
          sceneAnchorMode={sceneAnchorMode}
          trafficSummary={workspace?.trafficSummary ?? null}
        />
      </section>
      {workspace ? (
        <section className="footer-strip">
          <span>工作区：{workspace.mapName}</span>
          <span>模式：{workspaceModeLabel}</span>
          <span>投影：{workspace.projectionString}</span>
          <span>当前可见语义层：{visibleLayers.join(", ") || "无"}</span>
        </section>
      ) : null}
    </main>
  );
}

function isInitialLayerVisible(layerName: string, workspace: WorkspaceLoadResponse): boolean {
  return (
    workspace.defaultVisibleLayers.includes(layerName) ||
    workspace.trafficSummary.referenceLayer === layerName
  );
}
