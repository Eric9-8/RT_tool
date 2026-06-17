import { DELTA_FIELDS } from "../types";
import { matrixRows, rtConventionInfo } from "../math";
import { TrafficStatus } from "./TrafficStatus";
import type {
  BlockDelta,
  GsAlignmentView,
  LayerVisibilityState,
  MapLayerSummary,
  PreviewPose,
  PoseView,
  SceneAnchorMode,
  TrafficDataSummary
} from "../types";

type ControlPanelProps = {
  block: GsAlignmentView | null;
  delta: BlockDelta;
  preview: PreviewPose | null;
  busy: boolean;
  hasMapBounds: boolean;
  hasMeshLayer: boolean;
  layerSummaries: MapLayerSummary[];
  layerState: LayerVisibilityState;
  sceneAnchorMode: SceneAnchorMode;
  trafficSummary: TrafficDataSummary | null;
  onAnchorModeChange: (mode: SceneAnchorMode) => void;
  onDeltaChange: (field: keyof BlockDelta, value: number) => void;
  onLayerToggle: (layerName: string) => void;
  onMeshToggle: () => void;
  onGsToggle: () => void;
  onTrafficToggle: () => void;
  onOpacityChange: (field: "meshOpacity" | "gsOpacity", value: number) => void;
  onResetBlock: () => void;
  onResetAll: () => void;
  onExport: () => void;
  onExportTopview: () => void;
};

const LABELS: Record<keyof BlockDelta, string> = {
  yaw: "Yaw (deg)",
  pitch: "Pitch (deg)",
  roll: "Roll (deg)",
  dx: "GS Local X (m)",
  dy: "GS Local Y (m)",
  dz: "GS Local Z (m)"
};

export function ControlPanel(props: ControlPanelProps) {
  const {
    block,
    delta,
    preview,
    busy,
    hasMapBounds,
    hasMeshLayer,
    layerSummaries,
    layerState,
    sceneAnchorMode,
    trafficSummary,
    onAnchorModeChange,
    onDeltaChange,
    onLayerToggle,
    onMeshToggle,
    onGsToggle,
    onTrafficToggle,
    onOpacityChange,
    onResetBlock,
    onResetAll,
    onExport,
    onExportTopview
  } = props;

  return (
    <section className="panel control-panel">
      <div className="panel-header">
        <span className="eyebrow">Alignment Deck</span>
        <h2>对齐控制台</h2>
      </div>
      <div className="field-grid">
        {DELTA_FIELDS.map((field) => (
          <label key={field} className="number-field">
            <span>{LABELS[field]}</span>
            <input
              disabled={!block || busy}
              onChange={(event) => onDeltaChange(field, Number(event.target.value))}
              step={0.01}
              type="number"
              value={delta[field]}
            />
          </label>
        ))}
      </div>
      <AnchorModeControls
        hasMapBounds={hasMapBounds}
        onChange={onAnchorModeChange}
        sceneAnchorMode={sceneAnchorMode}
      />
      <div className="button-row">
        <button disabled={!block || busy} onClick={onResetBlock} type="button">
          重置当前 block
        </button>
        <button disabled={busy} onClick={onResetAll} type="button">
          全部清零
        </button>
        <button className="primary-button" disabled={!block || busy} onClick={onExport} type="button">
          导出 gs3d.json
        </button>
        <button disabled={!block || busy} onClick={onExportTopview} type="button">
          导出俯视图 (.zip)
        </button>
      </div>
      <LayerControls
        hasMeshLayer={hasMeshLayer}
        layerState={layerState}
        layerSummaries={layerSummaries}
        onGsToggle={onGsToggle}
        onLayerToggle={onLayerToggle}
        onMeshToggle={onMeshToggle}
        onOpacityChange={onOpacityChange}
        onTrafficToggle={onTrafficToggle}
        trafficSummary={trafficSummary}
      />
      <InfoGrid block={block} preview={preview} />
    </section>
  );
}

function AnchorModeControls(props: {
  hasMapBounds: boolean;
  sceneAnchorMode: SceneAnchorMode;
  onChange: (mode: SceneAnchorMode) => void;
}) {
  const { hasMapBounds, sceneAnchorMode, onChange } = props;

  return (
    <article className="info-card">
      <span className="eyebrow">View Anchor</span>
      <fieldset className="anchor-mode-group">
        <legend>观察模式</legend>
        <label className="toggle-row">
          <input
            checked={sceneAnchorMode === "follow_block"}
            name="scene-anchor-mode"
            onChange={() => onChange("follow_block")}
            type="radio"
          />
          <span>跟随当前 block</span>
        </label>
        <label className="toggle-row">
          <input
            checked={sceneAnchorMode === "map_origin_grounded"}
            disabled={!hasMapBounds}
            name="scene-anchor-mode"
            onChange={() => onChange("map_origin_grounded")}
            type="radio"
          />
          <span>地图固定到原点并贴地</span>
        </label>
      </fieldset>
      <p className="status">该模式只影响显示观察，不会修改导出坐标。</p>
      {!hasMapBounds ? <p className="status status-error">缺少地图范围，无法启用地图固定模式。</p> : null}
    </article>
  );
}

function LayerControls(props: {
  hasMeshLayer: boolean;
  layerState: LayerVisibilityState;
  layerSummaries: MapLayerSummary[];
  trafficSummary: TrafficDataSummary | null;
  onLayerToggle: (layerName: string) => void;
  onMeshToggle: () => void;
  onGsToggle: () => void;
  onTrafficToggle: () => void;
  onOpacityChange: (field: "meshOpacity" | "gsOpacity", value: number) => void;
}) {
  const {
    hasMeshLayer,
    layerState,
    layerSummaries,
    trafficSummary,
    onLayerToggle,
    onMeshToggle,
    onGsToggle,
    onTrafficToggle,
    onOpacityChange
  } = props;

  return (
    <div className="layer-controls">
      <article className="info-card">
        <span className="eyebrow">Layer Switches</span>
        {hasMeshLayer ? (
          <label className="toggle-row">
            <input checked={layerState.showMeshes} onChange={onMeshToggle} type="checkbox" />
            <span>显示地图网格</span>
          </label>
        ) : <p className="status">当前目录没有 map.json/Meshes，仅显示 GPKG 语义层与 GS 点云。</p>}
        <label className="toggle-row">
          <input checked={layerState.showGsAsset} onChange={onGsToggle} type="checkbox" />
          <span>显示 GS 点云</span>
        </label>
        {trafficSummary?.exists ? (
          <label className="toggle-row">
            <input checked={layerState.showTrafficRoutes} onChange={onTrafficToggle} type="checkbox" />
            <span>显示 traffic routes</span>
          </label>
        ) : null}
        {layerSummaries.map((layer) => (
          <label key={layer.name} className="toggle-row">
            <input
              checked={layerState.visibleLayers[layer.name] ?? false}
              onChange={() => onLayerToggle(layer.name)}
              type="checkbox"
            />
            <span>{layer.name}</span>
          </label>
        ))}
        <TrafficStatus trafficSummary={trafficSummary} />
      </article>
      <article className="info-card">
        <span className="eyebrow">Opacity</span>
        {hasMeshLayer ? (
          <label className="number-field">
            <span>地图网格透明度</span>
            <input
              max={1}
              min={0.1}
              onChange={(event) => onOpacityChange("meshOpacity", Number(event.target.value))}
              step={0.05}
              type="range"
              value={layerState.meshOpacity}
            />
          </label>
        ) : null}
        <label className="number-field">
          <span>GS 点云透明度</span>
          <input
            max={1}
            min={0.1}
            onChange={(event) => onOpacityChange("gsOpacity", Number(event.target.value))}
            step={0.05}
            type="range"
            value={layerState.gsOpacity}
          />
        </label>
      </article>
    </div>
  );
}

function InfoGrid(props: { block: GsAlignmentView | null; preview: PreviewPose | null }) {
  const { block, preview } = props;
  const currentPose = preview ?? block?.mapPose ?? null;

  return (
    <div className="info-grid">
      <RtConventionCard pose={currentPose} />
      <PoseCard label="Geocent 原始位姿" pose={block?.geocentPose ?? null} />
      <PoseCard label="地图系自动初始位姿" pose={block?.mapPose ?? null} />
      <PoseCard label="地图系当前预览位姿" pose={currentPose} />
    </div>
  );
}

function RtConventionCard(props: { pose: PoseView | null }) {
  const info = rtConventionInfo(props.pose);

  return (
    <article className="info-card">
      <span className="eyebrow">RT Convention</span>
      <p className="status">aiSim row-vector：旋转行是局部轴方向，平移在最后一行，center = RT[3][0:3]。</p>
      <pre>{info ? `yaw/pitch/roll: ${formatTuple(info.yawPitchRoll)}\nup axis: ${formatTuple(info.upAxis)}` : "暂无姿态诊断"}</pre>
    </article>
  );
}

function PoseCard(props: { label: string; pose: PoseView | null }) {
  const { label, pose } = props;

  return (
    <article className="info-card">
      <span className="eyebrow">{label}</span>
      <pre>{pose ? JSON.stringify(pose.center.map((value) => Number(value.toFixed(6))), null, 2) : "暂无数据"}</pre>
      <pre>{pose ? matrixRows(pose.rtMatrix).join("\n") : "暂无矩阵"}</pre>
    </article>
  );
}

function formatTuple(values: [number, number, number]): string {
  return `[${values.map((value) => value.toFixed(3)).join(", ")}]`;
}
