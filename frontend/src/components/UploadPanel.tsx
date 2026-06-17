import type { WorkspaceStatus } from "../types";

type UploadPanelProps = {
  busy: boolean;
  error: string | null;
  workspacePath: string;
  onPathChange: (value: string) => void;
  onLoad: () => void;
  loadedPath: string | null;
  workspaceStatus: WorkspaceStatus | null;
};

export function UploadPanel(props: UploadPanelProps) {
  const { busy, error, workspacePath, onPathChange, onLoad, loadedPath, workspaceStatus } = props;
  const modeLabel = workspaceStatus?.mode === "semantic_only" ? "轻量语义模式" : "完整地图模式";

  return (
    <section className="panel upload-panel">
      <div className="panel-header">
        <span className="eyebrow">Workspace Intake</span>
        <h2>加载地图/GS3D 工作区</h2>
      </div>
      <label className="number-field">
        <span>工作区目录</span>
        <input
          disabled={busy}
          onChange={(event) => onPathChange(event.target.value)}
          placeholder="/path/to/map_or_gs3d_workspace"
          type="text"
          value={workspacePath}
        />
      </label>
      <div className="button-row single">
        <button className="primary-button" disabled={busy || !workspacePath.trim()} onClick={onLoad} type="button">
          {busy ? "加载中..." : "加载工作区"}
        </button>
      </div>
      {loadedPath ? <p className="status">当前工作区：{loadedPath}</p> : null}
      {workspaceStatus ? <p className="status">工作区模式：{modeLabel}</p> : null}
      {workspaceStatus?.warnings.map((warning) => (
        <p className="status status-warning" key={warning}>{warning}</p>
      ))}
      {error ? <p className="status status-error">{error}</p> : null}
      <p className="status">支持完整工作区 map.json + Meshes + GeoPackage + gs3d.json，也支持轻量三件套 GS3D + GeoPackage + gs3d.json。</p>
    </section>
  );
}
